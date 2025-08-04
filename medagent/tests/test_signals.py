import pytest
from django.contrib.auth import get_user_model
from medagent.models import ChatSession, ChatMessage

User = get_user_model()


@pytest.mark.django_db
def test_sanitize_on_save(monkeypatch):
    monkeypatch.setattr(
        "medagent.tools.ProfanityCheckTool._run", lambda self, text: "True"
    )
    user = User.objects.create_user(username="owner", email="o@example.com", password="pwd")
    session = ChatSession.objects.create(user=user)
    msg = ChatMessage.objects.create(session=session, role="owner", content="bad")
    msg.refresh_from_db()
    assert msg.content == "[پیام حاوی کلمات نامناسب بود]"
