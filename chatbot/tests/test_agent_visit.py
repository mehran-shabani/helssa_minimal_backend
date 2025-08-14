import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from chatbot.models import ChatSession, ChatMessage
from chatbot.utils import text_summary as ts
from chatbot import agent as ag
from telemedicine.models import BoxMoney, Visit

User = get_user_model()


class DummySummary:
    def __init__(self, text: str):
        self.rewritten_text = text


@pytest.mark.django_db
def test_create_visit_from_summary_success(monkeypatch):
    user = User.objects.create_user(username="u5", password="p", auth_code="999999", phone_number="0915")
    session = ChatSession.objects.create(user=user)
    ChatMessage.objects.create(session=session, user=user, message="بیمار 30 ساله با تب، سرفه و گلودرد")
    # BoxMoney ساخته می‌شود از سیگنال؛ به‌روزرسانی موجودی
    bm, _ = BoxMoney.objects.get_or_create(user=user)
    bm.amount = 500000
    bm.save(update_fields=["amount"]) 

    # Mock summary to return deterministic text
    monkeypatch.setattr(ag.ts, "get_or_update_session_summary", lambda s: DummySummary("شرح حال: تب و سرفه و گلودرد"))

    res = ag.tool_create_visit_from_summary({"name": "ویزیت تستی", "max_cost": 398000}, user.id, session)
    assert res["ok"] is True
    vid = res["visit_id"]
    v = Visit.objects.get(id=vid)
    assert v.user_id == user.id
    assert v.name == "ویزیت تستی"
    assert v.general_symptoms in ("fever", "general_pain")
    assert v.respiratory_symptoms in ("cough", "sore_throat")

    box = BoxMoney.objects.get(user=user)
    assert box.amount == 500000 - 398000


@pytest.mark.django_db
def test_create_visit_from_summary_insufficient_funds(monkeypatch):
    user = User.objects.create_user(username="u6", password="p", auth_code="111111", phone_number="0916")
    session = ChatSession.objects.create(user=user)
    ChatMessage.objects.create(session=session, user=user, message="تهوع و اسهال")
    bm, _ = BoxMoney.objects.get_or_create(user=user)
    bm.amount = 100000
    bm.save(update_fields=["amount"]) 

    monkeypatch.setattr(ag.ts, "get_or_update_session_summary", lambda s: DummySummary("شرح حال: تهوع و اسهال"))

    res = ag.tool_create_visit_from_summary({"name": "ویزیت"}, user.id, session)
    assert res["ok"] is False
    assert res["error"] == "insufficient_funds"
    assert BoxMoney.objects.get(user=user).amount == 100000