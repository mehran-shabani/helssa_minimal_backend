import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate

from sub.models import Plan, Specialty, TokenTopUp
from sub.views import (
    PlanListView,
    MySubscriptionView,
    BuyPlanView,
    BuyTopUpView,
    BuySpecialtyView,
    MyUsageView,
)

User = get_user_model()


@pytest.mark.django_db
def test_view_flow_and_errors():
    factory = APIRequestFactory()
    user = User.objects.create_user(username="u", phone_number="0900000000", password="p")
    plan = Plan.objects.create(code="basic", name="Basic")
    specialty = Specialty.objects.create(code="spec", name="Spec")

    # Plan list
    request = factory.get("/plans/")
    force_authenticate(request, user=user)
    resp = PlanListView.as_view()(request)
    assert resp.status_code == 200 and len(resp.data["plans"]) == 1

    # MySubscriptionView without subscription
    request = factory.get("/me/")
    force_authenticate(request, user=user)
    resp = MySubscriptionView.as_view()(request)
    assert resp.status_code == 404

    # BuyPlanView invalid code
    request = factory.post("/buy/", {"plan_code": "nope"})
    force_authenticate(request, user=user)
    resp = BuyPlanView.as_view()(request)
    assert resp.status_code == 400

    # BuyPlanView valid
    request = factory.post("/buy/", {"plan_code": "basic", "months": 1})
    force_authenticate(request, user=user)
    resp = BuyPlanView.as_view()(request)
    assert resp.status_code == 200

    # MySubscriptionView now
    request = factory.get("/me/")
    force_authenticate(request, user=user)
    resp = MySubscriptionView.as_view()(request)
    assert resp.status_code == 200 and resp.data["subscription"]["plan"]["code"] == "basic"

    # BuyTopUpView invalid
    request = factory.post("/topup/", {"chars": 0})
    force_authenticate(request, user=user)
    resp = BuyTopUpView.as_view()(request)
    assert resp.status_code == 400

    # BuyTopUpView valid
    request = factory.post("/topup/", {"chars": 10})
    force_authenticate(request, user=user)
    resp = BuyTopUpView.as_view()(request)
    assert resp.status_code == 200

    # BuySpecialtyView invalid
    request = factory.post("/specialty/", {"specialty_code": "none"})
    force_authenticate(request, user=user)
    resp = BuySpecialtyView.as_view()(request)
    assert resp.status_code == 400

    # BuySpecialtyView valid
    request = factory.post("/specialty/", {"specialty_code": "spec"})
    force_authenticate(request, user=user)
    resp = BuySpecialtyView.as_view()(request)
    assert resp.status_code == 200

    # MyUsageView after some usage/topup
    TokenTopUp.buy(user, 5)
    request = factory.get("/usage/")
    force_authenticate(request, user=user)
    resp = MyUsageView.as_view()(request)
    assert resp.status_code == 200 and resp.data["plan"] == "basic"
