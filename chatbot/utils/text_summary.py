"""Utility helpers for conversation summarisation.

These functions avoid blocking the request/response cycle. They simply return
the latest stored summaries and, when needed, schedule Celery tasks to rebuild
them in the background.
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

# Rewriter API configuration
REWRITER_ENDPOINT = "https://api.talkbot.ir/v1/text/rewriter/REQ"
REWRITER_MODEL = "zarin-1.0"
API_TIMEOUT = 45  # seconds

# TTLs for refreshing summaries (in minutes)
GLOBAL_TTL_MIN = 60 * 24   # 24 hours
SESSION_TTL_MIN = 60 * 12  # 12 hours


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.TALKBOT_API_KEY}",
        "Content-Type": "application/x-www-form-urlencoded",
    }


def _serialize_conversation(sessions: List[ChatSession]) -> str:
    lines: List[str] = []
    for s in sessions:
        for m in s.messages.select_related("user"):
            role = "USER" if not m.is_bot else "BOT "
            ts = m.created_at.strftime("%Y-%m-%d %H:%M")
            lines.append(f"[{ts}] {role}: {m.message}")
    return "\n".join(lines)


MIN_CHARS = 100
MAX_CHARS = 20_000
PADDING_TOKEN = "‌"  # Zero-width non-joiner


def _call_rewriter_api(text: str, *, model: str = REWRITER_MODEL) -> str:
    original_len = len(text)
    if original_len < MIN_CHARS:
        padding_needed = MIN_CHARS - original_len
        text += PADDING_TOKEN * padding_needed
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]

    data = {
        "text": text,
        "model": model,
        "summary": "true",
        "translate": "none",
        "style": "8",
        "paraphrase-type": "8",
        "textlanguage": "fa",
        "half-space": "0",
    }
    try:
        resp = requests.post(REWRITER_ENDPOINT, headers=_headers(), data=data, timeout=API_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
        rewritten_text = payload.get("result", {}).get("text")
        if not rewritten_text:
            logger.error("Unexpected Rewriter response: %s", payload)
            return text.strip()
        if original_len < MIN_CHARS:
            rewritten_text = rewritten_text[:original_len].rstrip()
        return rewritten_text
    except Exception as exc:  # pragma: no cover - network failures
        logger.exception("Rewriter API failed: %s", exc)
        return text.strip()


def _simple_medical_extract(text: str) -> Dict:
    sections = {"history": [], "symptoms": [], "medications": [], "recommendations": []}
    for line in text.splitlines():
        t = line.strip()
        if any(k in t for k in ("سابقه", "تاریخچه")):
            sections["history"].append(t)
        if any(k in t for k in ("دارو", "mg", "قرص")):
            sections["medications"].append(t)
        if any(k in t for k in ("درد", "تب", "سرفه")):
            sections["symptoms"].append(t)
        if any(k in t for k in ("پیشنهاد", "توصیه", "درمان")):
            sections["recommendations"].append(t)
    return {k: "\n".join(v) for k, v in sections.items()}


# --- Non-blocking helpers for request path ---------------------------------

def _is_expired(obj: ChatSummary, ttl_minutes: int) -> bool:
    return (timezone.now() - obj.updated_at) > timedelta(minutes=ttl_minutes)


def _schedule_safe(task_kind: str, **kwargs):
    """Schedule Celery tasks, swallowing errors if Celery is unavailable."""
    try:
        if task_kind == "session":
            from chatbot.tasks import rebuild_session_summary

            rebuild_session_summary.apply_async(kwargs={"session_id": kwargs["session_id"]}, countdown=60)
        elif task_kind == "global":
            from chatbot.tasks import rebuild_global_summary

            rebuild_global_summary.apply_async(kwargs={"user_id": kwargs["user_id"]}, countdown=120)
    except Exception as exc:  # pragma: no cover - Celery misconfig
        logger.warning("Celery scheduling failed (non-fatal): %s", exc)


def get_or_create_global_summary(user) -> ChatSummary:
    summary = (
        ChatSummary.objects.filter(user=user, session__isnull=True)
        .order_by("-updated_at")
        .first()
    )
    if summary:
        if _is_expired(summary, GLOBAL_TTL_MIN) and not summary.in_progress:
            summary.is_stale = True
            summary.save(update_fields=["is_stale", "updated_at"])
            _schedule_safe("global", user_id=user.id)
        return summary

    with transaction.atomic():
        summary = ChatSummary.objects.create(
            user=user,
            session=None,
            model_used=REWRITER_MODEL,
            raw_text="",
            rewritten_text="",
            structured_json={},
            is_stale=True,
            last_message_id=0,
            in_progress=False,
        )
    _schedule_safe("global", user_id=user.id)
    return summary


def get_or_update_session_summary(session) -> ChatSummary:
    summary = session.summaries.order_by("-updated_at").first()
    if summary:
        if (summary.is_stale or _is_expired(summary, SESSION_TTL_MIN)) and not summary.in_progress:
            summary.is_stale = True
            summary.save(update_fields=["is_stale", "updated_at"])
            _schedule_safe("session", session_id=session.id)
        return summary

    with transaction.atomic():
        summary = ChatSummary.objects.create(
            user=session.user,
            session=session,
            model_used=REWRITER_MODEL,
            raw_text="",
            rewritten_text="",
            structured_json={},
            is_stale=True,
            last_message_id=0,
            in_progress=False,
        )
    _schedule_safe("session", session_id=session.id)
    return summary
