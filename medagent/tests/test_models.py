import hashlib
import datetime
import pytest
from unittest import mock
from django.utils import timezone
from freezegun import freeze_time
from django.contrib.auth import get_user_model

from medagent.models import (
    OTPVerification, ChatSession, ChatMessage,
    SessionSummary, PatientSummary, AccessHistory
)
from sub.models import SubscriptionPlan, Subscription

User = get_user_model()


@pytest.mark.django_db
def test_otp_verification_creation_and_validation():
    user = User.objects.create_user(username="testuser", email="u1@e.com", password="pwd")
    raw_code = "123456"
    otp = OTPVerification.create(user, raw_code)
    assert otp.code_hash == hashlib.sha256(raw_code.encode()).hexdigest()
    assert otp.valid(raw_code)
    assert not otp.valid("000000")
    future = timezone.now() + datetime.timedelta(minutes=11)
    with freeze_time(future):
        assert not otp.valid(raw_code)


@pytest.mark.django_db
def test_subscription_is_active_property():
    user = User.objects.create_user(username="subuser", email="u2@e.com", password="pwd")
    plan = SubscriptionPlan.objects.create(name="Monthly", days=31, price=300)
    now = timezone.now()
    sub = Subscription.objects.create(user=user, plan=plan, end_date=now + datetime.timedelta(days=plan.days))
    assert sub.is_active
    future = now + datetime.timedelta(days=plan.days + 1)
    with freeze_time(future):
        assert not sub.is_active


@pytest.mark.django_db
@mock.patch("medagent.talkbot_client.profanity", return_value=False)
def test_chat_session_and_message_creation(mock_profanity):
    user = User.objects.create_user(username="chatter", email="u3@e.com", password="pwd")
    session = ChatSession.objects.create(user=user)
    assert str(session).startswith("Session")
    msg_owner = ChatMessage.objects.create(session=session, role="owner", content="Hello")
    msg_assistant = ChatMessage.objects.create(session=session, role="assistant", content="Hi there")
    assert msg_owner.role == "owner"
    assert msg_assistant.role == "assistant"
    assert str(msg_owner).startswith("[owner]")


@pytest.mark.django_db
@mock.patch("medagent.talkbot_client.profanity", return_value=False)
def test_session_summary_creation(mock_profanity):
    user = User.objects.create_user(username="summarizer", email="u4@e.com", password="pwd")
    session = ChatSession.objects.create(user=user)
    ChatMessage.objects.create(session=session, role="owner", content="test")
    ChatMessage.objects.create(session=session, role="assistant", content="reply")
    summ = SessionSummary.objects.create(session=session, text_summary="A summary", json_summary={"key": "value"}, tokens_used=10)
    assert summ.session == session
    assert summ.text_summary == "A summary"
    assert summ.json_summary == {"key": "value"}


@pytest.mark.django_db
def test_str_methods_and_patient_summary_error(monkeypatch):
    user = User.objects.create_user(username="u", email="u@example.com", password="pwd")
    other = User.objects.create_user(username="o", email="o@example.com", password="pwd")
    # PatientSummary __str__ references nonexistent attribute 'patient'
    summary = PatientSummary.objects.create(user=user)
    with pytest.raises(AttributeError):
        str(summary)

    access = AccessHistory.objects.create(doctor=user, patient=other)
    assert str(access).startswith(str(user))

    session = ChatSession.objects.create(user=user)
    summ = SessionSummary.objects.create(session=session, text_summary="t", json_summary={}, tokens_used=1)
    assert str(summ) == f"Summary for session {session.id}"
