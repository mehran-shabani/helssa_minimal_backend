import importlib
import pytest
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

from sub.models import Plan, Subscription, Specialty, SpecialtyAccess, TokenTopUp
from sub.services import (
    get_active_subscription,
    get_today_usage,
    get_topup_balance,
    get_allowed_specialties,
    compute_caps_for_request,
)
from chatbot.models import UsageLog
from django.db import connection

# Ensure modules like admin and urls are loaded for coverage
importlib.import_module("sub.admin")
importlib.import_module("sub.urls")

User = get_user_model()


@pytest.fixture(autouse=True)
def ensure_usagelog_table(db):
    if "chatbot_usagelog" not in connection.introspection.table_names():
        with connection.schema_editor() as editor:
            editor.create_model(UsageLog)


@pytest.mark.django_db
def test_plan_buy_and_is_active():
    user = User.objects.create_user(username="u", phone_number="0910000000", password="p")
    plan = Plan.objects.create(
        code="basic",
        name="Basic",
        monthly_price=0,
        daily_char_limit=100,
        daily_requests_limit=5,
    )
    sub = plan.buy(user, months=2)
    assert sub.plan == plan
    assert sub.is_active is True
    assert sub.expires_at - sub.started_at == timedelta(days=60)


@pytest.mark.django_db
def test_specialty_access_and_token_topup_services_signal():
    user = User.objects.create_user(username="bob", phone_number="0911000000", password="p")
    plan = Plan.objects.create(code="pro", name="Pro", monthly_price=0, daily_char_limit=10)
    sub = plan.buy(user)

    # Token topup purchase
    topup = TokenTopUp.buy(user, 20)
    assert get_topup_balance(user) == 20
    assert "TopUp" in str(topup)

    # Specialty access buy & extend
    spec = Specialty.objects.create(code="derm", name="Derm")
    acc1 = SpecialtyAccess.buy(user, spec)
    first_expires = acc1.expires_at
    acc2 = SpecialtyAccess.buy(user, spec)
    assert acc1.id == acc2.id and acc2.expires_at > first_expires

    # Usage log and services
    UsageLog.objects.create(user=user, input_chars=3, output_chars=2)
    usage = get_today_usage(user)
    assert usage == {"chars": 5, "requests": 1}
    assert get_active_subscription(user) == sub

    # Allowed specialties combines plan and add-ons
    spec2 = Specialty.objects.create(code="cardio", name="Cardio")
    plan.specialties.add(spec2)
    allowed = get_allowed_specialties(user, plan)
    codes = {s.code for s in allowed}
    assert "cardio" in codes and "derm" in codes

    # Signal consumes topup when exceeding daily limit (10)
    UsageLog.objects.create(user=user, input_chars=10, output_chars=10)
    topup.refresh_from_db()
    # total chars today = 5 + 20 => overflow 15, so remaining = 5
    assert topup.char_balance == 5


@pytest.mark.django_db
def test_compute_caps_for_request_branches():
    user = User.objects.create_user(username="alice", phone_number="0912000000", password="p")
    plan1 = Plan.objects.create(
        code="starter",
        name="Starter",
        monthly_price=0,
        daily_char_limit=50,
        daily_requests_limit=1,
        allow_vision=False,
        allow_agent_tools=True,
    )
    sub1 = plan1.buy(user)
    factory = APIRequestFactory()
    req = factory.post("/x", {})
    result = compute_caps_for_request(user, sub1, req)
    assert result["ok"] is True
    assert result["tool_whitelist"] == [
        "triage_level",
        "get_patient_profile",
        "update_patient_profile",
    ]

    # Vision not allowed
    class Dummy:
        data = {"images": ["a"]}
        FILES = {}

    req_img = Dummy()
    result3 = compute_caps_for_request(user, sub1, req_img)
    assert result3["ok"] is False and "تصویر" in result3["reason"]


    # Plan with tools disabled
    plan2 = Plan.objects.create(
        code="pro",
        name="Pro",
        monthly_price=0,
        daily_char_limit=50,
        daily_requests_limit=5,
        allow_agent_tools=False,
    )
    sub2 = plan2.buy(user)
    result4 = compute_caps_for_request(user, sub2, req)
    assert result4["tool_whitelist"] == []
