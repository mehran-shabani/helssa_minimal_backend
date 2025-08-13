# chatbot/utils/text_summary.py
# خلاصه مکالمات با OpenAI-compatible SDK (GapGPT) - مدل پیش‌فرض: o3-mini
from __future__ import annotations

import json
import logging
import re
from datetime import timedelta
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from chatbot.models import ChatSession, ChatSummary

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except Exception as exc:
    OpenAI = None
    logger.error("openai library not installed: %s", exc)

CLIENT = None
def _get_client():
    global CLIENT
    if CLIENT is None:
        if not OpenAI:
            raise RuntimeError("openai library missing. `pip install openai`")
        base_url = getattr(settings, "GAPGPT_BASE_URL", "https://api.gapgpt.app/v1")
        api_key  = getattr(settings, "GAPGPT_API_KEY", None)
        if not api_key:
            raise RuntimeError("GAPGPT_API_KEY is missing in settings/env.")
        CLIENT = OpenAI(base_url=base_url, api_key=api_key)
    return CLIENT

# TTL
GLOBAL_TTL_MIN = 60 * 6
SESSION_TTL_MIN = 30

RAW_CLIP_CHARS = 50_000
SUMMARY_CLIP_CHARS = int(getattr(settings, "SUMMARY_CLIP_CHARS", 4_000))

_JSON_BLOCK_RE = re.compile(r"\{(?:[^{}]|(?:\{[^{}]*\}))*\}", re.S)

def _ensure_text(x) -> str:
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    try:
        return json.dumps(x, ensure_ascii=False)
    except Exception:
        return str(x)

def _clip(s: str, n: int) -> str:
    s = _ensure_text(s).strip()
    if len(s) <= n:
        return s
    return s[: max(0, n - 1)] + "…"

def _serialize_conversation(sessions: List[ChatSession]) -> str:
    lines: List[str] = []
    for s in sessions:
        for m in s.messages.select_related("user").order_by("created_at"):
            role = "USER" if not m.is_bot else "ASSISTANT"
            ts = m.created_at.strftime("%Y-%m-%d %H:%M")
            lines.append(f"[{ts}] {role}: {m.message}")
    return _clip("\n".join(lines), RAW_CLIP_CHARS)

def _extract_text_from_resp(resp) -> str:
    try:
        # openai-python SDK object
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return ""

def _find_json_in_text(text: str) -> Optional[dict]:
    try:
        m = _JSON_BLOCK_RE.search(text or "")
        if not m:
            return None
        return json.loads(m.group(0))
    except Exception:
        return None

def _simple_medical_extract(text: str) -> Dict:
    sections = {"history": [], "symptoms": [], "medications": [], "recommendations": []}
    for line in (text or "").splitlines():
        t = line.strip()
        if any(k in t for k in ("سابقه", "تاریخچه")):
            sections["history"].append(t)
        if any(k in t for k in ("دارو", "mg", "میلی‌گرم", "قرص")):
            sections["medications"].append(t)
        if any(k in t for k in ("درد", "تب", "سرفه", "تهوع", "استفراغ")):
            sections["symptoms"].append(t)
        if any(k in t for k in ("پیشنهاد", "توصیه", "درمان", "ارجاع")):
            sections["recommendations"].append(t)
    return {k: "\n".join(v) for k, v in sections.items()}

def _build_summary_prompt() -> str:
    return (
        "تو یک پزشک باتجربه هستی. مکالمهٔ بیمار/دستیار را خلاصه کن.\n"
        "- فارسی، دقیق، کوتاه.\n"
        "- در پایان فقط یک JSON با کلیدهای history/symptoms/medications/recommendations بده.\n"
        "- اگر داده‌ای نیست، مقدار هر کلید خالی باشد. توضیح اضافه نده."
    )

def _call_summarizer(text: str) -> Tuple[str, Dict]:
    model = getattr(settings, "SUMMARY_MODEL_NAME", "o3-mini")
    max_tokens = int(getattr(settings, "SUMMARY_MAX_TOKENS", 900))
    try:
        client = _get_client()
        system_prompt = _build_summary_prompt()
        user_content = f"Conversation:\n{text}"
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            max_tokens=max_tokens,
            temperature=0.2,
            top_p=0.9,
        )
        content = _extract_text_from_resp(resp)
        if not content:
            logger.warning("Summarizer empty content.")
            return _clip(text, SUMMARY_CLIP_CHARS), _simple_medical_extract(text)
        js = _find_json_in_text(content) or _simple_medical_extract(content)
        return _clip(content, SUMMARY_CLIP_CHARS), js
    except Exception as exc:
        logger.exception("Summarizer failed: %s", exc)
        return _clip(text, SUMMARY_CLIP_CHARS), _simple_medical_extract(text)

def _is_expired(obj: ChatSummary, ttl_minutes: int) -> bool:
    return (timezone.now() - obj.updated_at) > timedelta(minutes=ttl_minutes)

def _dedup_keep_latest(user, session) -> Optional[ChatSummary]:
    qs = ChatSummary.objects.filter(user=user, session=session).order_by("-updated_at")
    items = list(qs)
    if not items:
        return None
    keep = items[0]
    if len(items) > 1:
        ChatSummary.objects.filter(id__in=[x.id for x in items[1:]]).delete()
        logger.warning("Dedup summaries for user=%s session=%s kept=%s deleted=%s",
                       user.id, getattr(session, "id", None), keep.id, [x.id for x in items[1:]])
    return keep

# -------- Public API --------
def summarize_user_chats(user, *, limit_sessions: int | None = None) -> ChatSummary:
    qs = ChatSession.objects.filter(user=user).order_by("-started_at")
    if limit_sessions:
        qs = qs[:limit_sessions]
    sessions = list(qs)
    if not sessions:
        raise ValueError("No chat sessions found for user.")

    raw = _serialize_conversation(sessions)
    summary_text, json_struct = _call_summarizer(raw)

    with transaction.atomic():
        keep = _dedup_keep_latest(user, None)
        if keep:
            keep.model_used = getattr(settings, "SUMMARY_MODEL_NAME", "o3-mini")
            keep.raw_text = raw
            keep.rewritten_text = summary_text
            keep.structured_json = json_struct
            keep.save(update_fields=["model_used","raw_text","rewritten_text","structured_json","updated_at"])
            return keep
        return ChatSummary.objects.create(
            user=user,
            session=None,
            model_used=getattr(settings, "SUMMARY_MODEL_NAME", "o3-mini"),
            raw_text=raw,
            rewritten_text=summary_text,
            structured_json=json_struct,
        )

def get_or_create_global_summary(user) -> ChatSummary:
    keep = _dedup_keep_latest(user, None)
    if keep and not _is_expired(keep, GLOBAL_TTL_MIN):
        return keep
    return summarize_user_chats(user)

def get_or_update_session_summary(session) -> ChatSummary:
    user = session.user
    with transaction.atomic():
        keep = _dedup_keep_latest(user, session)
        if keep and not _is_expired(keep, SESSION_TTL_MIN):
            return keep

        raw = _serialize_conversation([session])
        summary_text, json_struct = _call_summarizer(raw)

        if keep:
            keep.model_used = getattr(settings, "SUMMARY_MODEL_NAME", "o3-mini")
            keep.raw_text = raw
            keep.rewritten_text = summary_text
            keep.structured_json = json_struct
            keep.save(update_fields=["model_used","raw_text","rewritten_text","structured_json","updated_at"])
            return keep
        return ChatSummary.objects.create(
            user=user,
            session=session,
            model_used=getattr(settings, "SUMMARY_MODEL_NAME", "o3-mini"),
            raw_text=raw,
            rewritten_text=summary_text,
            structured_json=json_struct,
        )