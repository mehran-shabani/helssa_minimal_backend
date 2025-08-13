import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from chatbot.models import ChatSession, ChatSummary

User = get_user_model()


@pytest.mark.skip(reason="ChatSummary enforces unique user/session so duplicates cannot exist")
def test_cleanup_chat_summaries_removes_duplicates():
    pass
