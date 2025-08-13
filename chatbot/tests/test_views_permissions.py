import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.management import call_command

from chatbot.permissions import HasActiveSubscription
from sub.models import Plan, Subscription
from chatbot.models import ChatSession

User = get_user_model()


@pytest.mark.django_db
def test_permission_and_view(monkeypatch):
    user = User.objects.create_user(username="u2", password="p", auth_code="654321", phone_number="0912")

    plan = Plan.objects.create(code="basic", name="Basic")
    Subscription.objects.create(
        user=user,
        plan=plan,
        started_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=1),
    )

    perm = HasActiveSubscription()
    request = type("obj", (), {"user": user})()
    assert perm.has_permission(request, None) is True

    client = APIClient()
    client.force_authenticate(user=user)
    monkeypatch.setattr("chatbot.views.generate_gpt_response", lambda **k: "ok")
    data = {
        "message": "hi",
        "new_session": "true",
        "images": ["data:image/jpeg;base64,AAAA"],
        "image_urls": ["http://example.com/img.jpg"],
    }
    resp = client.post("/chat/msg/", data, format="json")
    assert resp.status_code == 200 and resp.data["answer"] == "ok"


@pytest.mark.django_db
def test_management_commands(monkeypatch, capsys):
    user = User.objects.create_user(username="u3", password="p", auth_code="777777", phone_number="0913")
    session = ChatSession.objects.create(user=user, started_at=timezone.now() - timezone.timedelta(hours=13))

    call_command("close_open_sessions", hours=12)
    session.refresh_from_db()
    assert session.is_open is False

    called = {}

    def fake_rebuild(user_id, limit_sessions=None):
        called["user"] = user_id

    monkeypatch.setattr(
        "chatbot.management.commands.summarize_chats.rebuild_global_summary",
        fake_rebuild,
    )
    monkeypatch.setattr(
        "chatbot.management.commands.summarize_chats.get_or_create_global_summary",
        lambda u: None,
    )
    call_command("summarize_chats", user.username)
    assert called["user"] == user.id
