import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from chatbot.models import ChatSession, ChatMessage, ChatSummary
from chatbot.utils import text_summary as ts
from chatbot.tasks import rebuild_session_summary, rebuild_global_summary
from chatbot.serializers import (
    ChatMessageSerializer,
    ChatSessionSerializer,
    ChatSummarySerializer,
)

User = get_user_model()


@pytest.mark.django_db
def test_summary_helpers_and_tasks(monkeypatch):
    user = User.objects.create_user(username="u1", password="p", auth_code="123456", phone_number="0911")
    session = ChatSession.objects.create(user=user)
    ChatMessage.objects.create(session=session, user=user, message="سلام")

    scheduled = []
    monkeypatch.setattr(
        "chatbot.tasks.rebuild_session_summary.apply_async",
        lambda *a, **k: scheduled.append("session"),
        raising=False,
    )
    monkeypatch.setattr(
        "chatbot.tasks.rebuild_global_summary.apply_async",
        lambda *a, **k: scheduled.append("global"),
        raising=False,
    )

    gsum = ts.get_or_create_global_summary(user)
    ssum = ts.get_or_update_session_summary(session)
    assert gsum.is_stale and ssum.is_stale
    assert set(scheduled) == {"session", "global"}

    # serializers
    assert ChatMessageSerializer(ChatMessage.objects.first()).data["message"] == "سلام"
    assert "messages" in ChatSessionSerializer(session).data
    assert "is_stale" in ChatSummarySerializer(ssum).data

    # Internal helpers
    raw = ts._serialize_conversation([session])
    assert "سلام" in raw
    data = ts._simple_medical_extract("دارو 10mg\nتوصیه: استراحت")
    assert "دارو" in data["medications"]

    # Mock rewriter API
    class DummyResp:
        ok = True
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"result": {"text": "بازنویسی"}}

    monkeypatch.setattr(ts.requests, "post", lambda *a, **k: DummyResp())
    out = ts._call_rewriter_api("x" * 120)
    assert out == "بازنویسی"

    # Test tasks with patched helpers
    monkeypatch.setattr(ts, "_serialize_conversation", lambda s: "raw")
    monkeypatch.setattr(ts, "_call_rewriter_api", lambda t: "rewritten")
    monkeypatch.setattr(ts, "_simple_medical_extract", lambda t: {"k": "v"})

    rebuild_session_summary(session.id)
    rebuild_global_summary(user.id)

    ssum.refresh_from_db()
    gsum.refresh_from_db()
    assert ssum.rewritten_text == gsum.rewritten_text == "rewritten"
    assert not ssum.is_stale and not gsum.is_stale

    # signal branch: new message marks summary stale
    ssum.is_stale = False
    ssum.save()
    ChatMessage.objects.create(session=session, user=user, message="جدید")
    ssum.refresh_from_db()
    assert ssum.is_stale
