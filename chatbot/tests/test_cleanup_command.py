import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from chatbot.models import ChatSession, ChatSummary

User = get_user_model()


@pytest.mark.django_db
def test_cleanup_chat_summaries_removes_duplicates():
    user = User.objects.create_user(username="u1", password="p", auth_code="123456", phone_number="0901")
    session = ChatSession.objects.create(user=user)

    # two session summaries
    ChatSummary.objects.create(user=user, session=session, raw_text="a", rewritten_text="a")
    ChatSummary.objects.create(user=user, session=session, raw_text="b", rewritten_text="b")
    # two global summaries
    ChatSummary.objects.create(user=user, raw_text="g1", rewritten_text="g1")
    ChatSummary.objects.create(user=user, raw_text="g2", rewritten_text="g2")

    call_command("cleanup_chat_summaries")

    assert ChatSummary.objects.filter(user=user, session=session).count() == 1
    assert ChatSummary.objects.filter(user=user, session=None).count() == 1
    kept = ChatSummary.objects.get(user=user, session=session)
    assert kept.raw_text == "b"
    kept_global = ChatSummary.objects.get(user=user, session=None)
    assert kept_global.raw_text == "g2"
