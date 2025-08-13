"""
Summarization utilities using OpenAI-compatible Chat Completions.
- Model: settings.SUMMARY_MODEL (default: o3-mini)
- Ensures single summary per (user, session) and one global (via code dedupe).
"""
from __future__ import annotations
import json
import logging
from datetime import timedelta
from typing import Dict, List, Optional

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from chatbot.models import ChatSession, ChatSummary

logger = logging.getLogger(__name__)

API_URL = f"{settings.OPENAI_BASE_URL}/chat/completions"
API_KEY = settings.OPENAI_API_KEY
TIMEOUT = (settings.OPENAI_TIMEOUT_CONNECT, settings.OPENAI_TIMEOUT_READ)
MODEL = getattr(settings, "SUMMARY_MODEL", "o3-mini")

GLOBAL_TTL_MIN = 60 * 6   # 6h
SESSION_TTL_MIN = 30      # 30m

def _headers():
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

def _serialize_conversation(sessions: List[ChatSession]) -> str:
    lines: List[str] = []
    for s in sessions:
        for m in s.messages.select_related("user").order_by("created_at"):
            role = "USER" if not m.is_bot else "BOT "
            ts = m.created_at.strftime("%Y-%m-%d %H:%M")
            lines.append(f"[{ts}] {role}: {m.message}")
    return "\n".join(lines)

def _call_llm_for_summary(raw_text: str) -> Dict[str, str]:
    """
    Returns dict: {"rewritten": str, "structured": dict}
    """
    system = (
        "بازنویسی مختصر و رسمی مکالمهٔ پزشکی فارسی. سپس استخراج ساختاریافته:\n"
        "- history: سابقه و شرح حال\n- symptoms: علائم\n- medications: داروها/دوز\n- recommendations: توصیه‌ها\n"
        "خروجی دقیق و کوتاه باشد."
    )
    user_prompt = f"متن مکالمات:\n{raw_text}"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]
    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": 800,
        "temperature": 0.2,
        # مدل‌های reasoning ممکن است این پارامتر را پشتیبانی کنند:
        "reasoning": {"effort": "medium"},
    }
    try:
        r = requests.post(API_URL, data=json.dumps(payload), headers=_headers(), timeout=TIMEOUT)
        if not r.ok:
            logger.warning("Summary http %s: %s", r.status_code, r.text[:200])
            text = r.text or ""
            return {"rewritten": text[:1000], "structured": {}}
        data = r.json() or {}
        content = ""
        try:
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
        except Exception:
            content = ""
        rewritten = content.strip()[:20000]

        structured = _simple_medical_extract(rewritten)
        return {"rewritten": rewritten, "structured": structured}
    except Exception as exc:
        logger.exception("Summary API failed: %s", exc)
        return {"rewritten": raw_text[:20000], "structured": {}}

def _simple_medical_extract(text: str) -> Dict:
    sections = {"history": [], "symptoms": [], "medications": [], "recommendations": []}
    for line in text.splitlines():
        t = line.strip()
        if any(k in t for k in ("سابقه", "تاریخچه", "شرح حال")):
            sections["history"].append(t)
        if any(k in t for k in ("دارو", "mg", "میلی‌گرم", "قرص", "دوز")):
            sections["medications"].append(t)
        if any(k in t for k in ("درد", "تب", "سرفه", "تنگی نفس", "تهوع", "خستگی")):
            sections["symptoms"].append(t)
        if any(k in t for k in ("پیشنهاد", "توصیه", "پیگیری", "درمان")):
            sections["recommendations"].append(t)
    return {k: "\n".join(v) for k, v in sections.items()}

def _is_expired(obj: ChatSummary, ttl_minutes: int) -> bool:
    return (timezone.now() - obj.updated_at) > timedelta(minutes=ttl_minutes)

def _ensure_single_summary(user, session: Optional[ChatSession]) -> Optional[ChatSummary]:
    """
    Dedup summaries for (user, session). Keeps the latest one, deletes others.
    """
    qs = ChatSummary.objects.filter(user=user, session=session).order_by("-updated_at")
    summaries = list(qs)
    if not summaries:
        return None
    keep = summaries[0]
    to_delete = [s.id for s in summaries[1:]]
    if to_delete:
        ChatSummary.objects.filter(id__in=to_delete).delete()
    return keep

def summarize_user_chats(user, *, limit_sessions: int | None = None) -> ChatSummary:
    qs = ChatSession.objects.filter(user=user).order_by("-started_at")
    if limit_sessions:
        qs = qs[:limit_sessions]
    sessions = list(qs)
    if not sessions:
        raise ValueError("No chat sessions found for user.")
    raw = _serialize_conversation(sessions)
    result = _call_llm_for_summary(raw)
    with transaction.atomic():
        existing = _ensure_single_summary(user, None)
        if existing:
            existing.model_used = MODEL
            existing.raw_text = raw
            existing.rewritten_text = result["rewritten"]
            existing.structured_json = result["structured"]
            existing.save(update_fields=["model_used","raw_text","rewritten_text","structured_json","updated_at"])
            return existing
        return ChatSummary.objects.create(
            user=user,
            session=None,
            model_used=MODEL,
            raw_text=raw,
            rewritten_text=result["rewritten"],
            structured_json=result["structured"],
        )

def get_or_create_global_summary(user) -> ChatSummary:
    summary = _ensure_single_summary(user, None)
    if summary and not _is_expired(summary, GLOBAL_TTL_MIN):
        return summary
    return summarize_user_chats(user)

def get_or_update_session_summary(session: ChatSession) -> ChatSummary:
    summary = _ensure_single_summary(session.user, session)
    if summary and not _is_expired(summary, SESSION_TTL_MIN):
        return summary
    raw = _serialize_conversation([session])
    result = _call_llm_for_summary(raw)
    with transaction.atomic():
        if summary:
            summary.model_used = MODEL
            summary.raw_text = raw
            summary.rewritten_text = result["rewritten"]
            summary.structured_json = result["structured"]
            summary.save(update_fields=["model_used","raw_text","rewritten_text","structured_json","updated_at"])
            return summary
        return ChatSummary.objects.create(
            user=session.user,
            session=session,
            model_used=MODEL,
            raw_text=raw,
            rewritten_text=result["rewritten"],
            structured_json=result["structured"],
        )
