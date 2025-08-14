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

    # Mock summarization API
    monkeypatch.setattr(ts, "_call_llm_for_summary", lambda raw: {"rewritten": "بازنویسی", "structured": {"k": "v"}})

    gsum = ts.get_or_create_global_summary(user)
    ssum = ts.get_or_update_session_summary(session)
    assert gsum.rewritten_text == ssum.rewritten_text == "بازنویسی"

    # serializers
    assert ChatMessageSerializer(ChatMessage.objects.first()).data["message"] == "سلام"
    assert "messages" in ChatSessionSerializer(session).data
    assert ChatSummarySerializer(ssum).data["rewritten_text"] == "بازنویسی"

    # Internal helpers
    raw = ts._serialize_conversation([session])
    assert "سلام" in raw
    data = ts._simple_medical_extract("دارو 10mg\nتوصیه: استراحت")
    assert "دارو" in data["medications"]
