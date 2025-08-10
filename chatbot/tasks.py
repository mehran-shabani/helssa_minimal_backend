from __future__ import annotations

from celery import shared_task
from django.db import transaction
from django.contrib.auth import get_user_model

from chatbot.models import ChatSession, ChatSummary
from .utils import text_summary as ts

User = get_user_model()


def _ensure_session_summary(session: ChatSession) -> ChatSummary:
    summary = session.summaries.order_by("-updated_at").first()
    if summary:
        return summary
    return ChatSummary.objects.create(
        user=session.user,
        session=session,
        model_used=ts.REWRITER_MODEL,
        raw_text="",
        rewritten_text="",
        structured_json={},
        is_stale=True,
        last_message_id=0,
        in_progress=False,
    )


def _ensure_global_summary(user: User) -> ChatSummary:
    summary = (
        ChatSummary.objects.filter(user=user, session__isnull=True)
        .order_by("-updated_at")
        .first()
    )
    if summary:
        return summary
    return ChatSummary.objects.create(
        user=user,
        session=None,
        model_used=ts.REWRITER_MODEL,
        raw_text="",
        rewritten_text="",
        structured_json={},
        is_stale=True,
        last_message_id=0,
        in_progress=False,
    )


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def rebuild_session_summary(self, session_id: int):
    session = ChatSession.objects.get(id=session_id)

    # Soft lock using in_progress
    with transaction.atomic():
        summary = _ensure_session_summary(session)
        if summary.in_progress:
            return
        summary.in_progress = True
        summary.save(update_fields=["in_progress"])

    try:
        raw = ts._serialize_conversation([session])
        rewritten = ts._call_rewriter_api(raw)
        structured = ts._simple_medical_extract(rewritten)
        last_id = (
            session.messages.order_by("-id").values_list("id", flat=True).first()
            or 0
        )

        with transaction.atomic():
            summary.refresh_from_db()
            summary.raw_text = raw
            summary.rewritten_text = rewritten
            summary.structured_json = structured
            summary.last_message_id = last_id
            summary.is_stale = False
            summary.in_progress = False
            summary.save()
    except Exception:
        with transaction.atomic():
            summary.refresh_from_db()
            summary.in_progress = False
            summary.is_stale = True
            summary.save(update_fields=["in_progress", "is_stale"])
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def rebuild_global_summary(self, user_id: int, limit_sessions: int | None = None):
    user = User.objects.get(id=user_id)

    with transaction.atomic():
        summary = _ensure_global_summary(user)
        if summary.in_progress:
            return
        summary.in_progress = True
        summary.save(update_fields=["in_progress"])

    try:
        qs = ChatSession.objects.filter(user=user).order_by("-started_at")
        if limit_sessions:
            qs = qs[:limit_sessions]
        sessions = list(qs)
        if not sessions:
            raw, rewritten, structured = "", "", {}
        else:
            raw = ts._serialize_conversation(sessions)
            rewritten = ts._call_rewriter_api(raw)
            structured = ts._simple_medical_extract(rewritten)
        with transaction.atomic():
            summary.refresh_from_db()
            summary.raw_text = raw
            summary.rewritten_text = rewritten
            summary.structured_json = structured
            summary.is_stale = False
            summary.in_progress = False
            summary.save()
    except Exception:
        with transaction.atomic():
            summary.refresh_from_db()
            summary.in_progress = False
            summary.is_stale = True
            summary.save(update_fields=["in_progress", "is_stale"])
        raise


@shared_task
def nightly_rebuild_all():
    for sid in ChatSession.objects.filter(is_open=True).values_list("id", flat=True):
        rebuild_session_summary.delay(session_id=sid)
    user_ids = ChatSession.objects.values_list("user_id", flat=True).distinct()
    for uid in user_ids:
        rebuild_global_summary.delay(user_id=uid)
