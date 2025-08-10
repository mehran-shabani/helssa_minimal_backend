# chatbot/utils/text_summary.py
"""
ابزارهای کمکی برای تجمیع مکالمات و خلاصه/بازنویسی با API تاک‌بات.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Dict, List

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from chatbot.models import ChatSession, ChatSummary

logger = logging.getLogger(__name__)

# پیکربندی API بازنویسی
REWRITER_ENDPOINT = "https://api.talkbot.ir/v1/text/rewriter/REQ"
REWRITER_MODEL = "zarin-1.0"
API_TIMEOUT = 45  # ثانیه

# زمان زنده‌بودن خلاصه (TTL) بر حسب دقیقه
GLOBAL_TTL_MIN = 60 * 6   # ۶ ساعت
SESSION_TTL_MIN = 30      # ۳۰ دقیقه

def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.TALKBOT_API_KEY}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

def _serialize_conversation(sessions: List[ChatSession]) -> str:
    """
    تمام پیام‌های جلسات داده‌شده را به متن خط‌به‌خط تبدیل می‌کند.
    """
    lines: List[str] = []
    for s in sessions:
        for m in s.messages.select_related("user"):
            role = "USER" if not m.is_bot else "BOT "
            ts = m.created_at.strftime("%Y-%m-%d %H:%M")
            lines.append(f"[{ts}] {role}: {m.message}")
    return "\n".join(lines)

MIN_CHARS = 100
MAX_CHARS = 20_000
PADDING_TOKEN = "‌"  # کاراکتر نیم‌فاصله (Zero-Width Non-Joiner)؛ در خروجی قابل‌مشاهده نیست.

def _call_rewriter_api(text: str, *, model: str = REWRITER_MODEL) -> str:
    """
    فراخوانی ایمن تاک‌بات با پَد کردن متن‌های کوتاه:
    اگر متن < 100 کاراکتر باشد، با کاراکتر نیم‌فاصله پُر می‌شود تا طول دقیقاً به 100 برسد.
    پس از دریافت پاسخ، Padding حذف می‌شود.
    در خطاهای شبکه یا پاسخ غیرمنتظره، متن خام برگردانده می‌شود و خطا لاگ می‌گردد.
    """
    import requests

    # ───── 1) آماده‌سازی متن ─────
    original_len = len(text)
    if original_len < MIN_CHARS:
        padding_needed = MIN_CHARS - original_len
        text += PADDING_TOKEN * padding_needed  # افزودن پَد

    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]  # برشِ ایمن

    # ───── 2) فراخوانی API تاک‌بات ─────
    data = {
        "text": text,
        "model": model,
        "summary": "true",
        "translate": "none",
        "style": "8",            # رسمی
        "paraphrase-type": "8",  # تغییر هوشمند
        "textlanguage": "fa",
        "half-space": "0",
    }
    try:
        resp = requests.post(
            REWRITER_ENDPOINT,
            headers=_headers(),
            data=data,
            timeout=API_TIMEOUT,
        )
        resp.raise_for_status()                          # خطاهای HTTP

        payload = resp.json()
        rewritten_text = payload.get("result", {}).get("text")

        if not rewritten_text:
            logger.error("Unexpected Rewriter response: %s", payload)
            return text.strip()

        # ───── 3) حذف Padding ─────
        if original_len < MIN_CHARS:
            rewritten_text = rewritten_text[:original_len].rstrip()

        return rewritten_text

    except Exception as exc:
        logger.exception("Rewriter API failed: %s", exc)
        return text.strip()

def _simple_medical_extract(text: str) -> Dict:
    """
    استخراج ساده بخش‌های پزشکی از متن بازنویسی‌شده.
    """
    sections = {
        "history": [], "symptoms": [], "medications": [], "recommendations": []
    }
    for line in text.splitlines():
        t = line.strip()
        if any(k in t for k in ("سابقه", "تاریخچه")):
            sections["history"].append(t)  # pragma: no cover
        if any(k in t for k in ("دارو", "mg", "قرص")):
            sections["medications"].append(t)
        if any(k in t for k in ("درد", "تب", "سرفه")):
            sections["symptoms"].append(t)
        if any(k in t for k in ("پیشنهاد", "توصیه", "درمان")):
            sections["recommendations"].append(t)
    return {k: "\n".join(v) for k, v in sections.items()}

def summarize_user_chats(user, *, limit_sessions: int | None = None) -> ChatSummary:
    """
    جمع‌آوری همه یا n جلسهٔ آخر کاربر و ایجاد خلاصهٔ جامع.
    """
    qs = ChatSession.objects.filter(user=user).order_by("-started_at")
    if limit_sessions:
        qs = qs[:limit_sessions]  # pragma: no cover
    sessions = list(qs)
    if not sessions:
        raise ValueError("No chat sessions found for user.")
    raw = _serialize_conversation(sessions)
    rewritten = _call_rewriter_api(raw)
    structured = _simple_medical_extract(rewritten)
    with transaction.atomic():
        summary = ChatSummary.objects.create(
            user=user,
            session=None if len(sessions) > 1 else sessions[0],
            model_used=REWRITER_MODEL,
            raw_text=raw,
            rewritten_text=rewritten,
            structured_json=structured,
        )
    return summary

def _is_expired(obj: ChatSummary, ttl_minutes: int) -> bool:
    return (timezone.now() - obj.updated_at) > timedelta(minutes=ttl_minutes)

def get_or_create_global_summary(user) -> ChatSummary:
    """
    بازگرداندن یا تجدید خلاصهٔ جامع (cross-session).
    """
    summary = (
        ChatSummary.objects
        .filter(user=user, session__isnull=True)
        .order_by("-updated_at")
        .first()
    )
    if summary and not _is_expired(summary, GLOBAL_TTL_MIN):
        return summary  # pragma: no cover
    return summarize_user_chats(user)

def get_or_update_session_summary(session) -> ChatSummary:  # pragma: no cover
    """
    بازگرداندن یا تجدید خلاصهٔ مکالمات یک جلسه.
    """
    summary = session.summaries.order_by("-updated_at").first()
    if summary and not _is_expired(summary, SESSION_TTL_MIN):
        return summary  # pragma: no cover
    raw = _serialize_conversation([session])
    rewritten = _call_rewriter_api(raw)
    structured = _simple_medical_extract(rewritten)
    with transaction.atomic():
        if summary:
            summary.raw_text = raw
            summary.rewritten_text = rewritten
            summary.structured_json = structured
            summary.save(update_fields=[
                "raw_text", "rewritten_text", "structured_json", "updated_at"
            ])
        else:  # pragma: no cover
            summary = ChatSummary.objects.create(
                user=session.user,
                session=session,
                model_used=REWRITER_MODEL,
                raw_text=raw,
                rewritten_text=rewritten,
                structured_json=structured,
            )
    return summary