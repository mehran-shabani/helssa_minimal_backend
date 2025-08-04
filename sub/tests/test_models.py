# tests/test_subscription_models_extra.py
import pytest
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from sub.models import SubscriptionPlan, Subscription
from telemedicine.models import BoxMoney

User = get_user_model()

@pytest.mark.django_db
def test_subscription_str_and_is_active():
    user = User.objects.create_user(username="u", email="u@x.com", password="u")
    plan = SubscriptionPlan.objects.create(name="M", days=1, price=10)
    sub = Subscription.objects.create(
        user=user, plan=plan,
        start_date=timezone.now(),
        end_date=timezone.now() + timedelta(days=1)
    )
    assert "active=True" in str(sub)
    assert sub.is_active is True

@pytest.mark.django_db
def test_buy_plan_renew(monkeypatch):
    user = User.objects.create_user(username="p2", email="p2@x.com", password="p2")
    plan = SubscriptionPlan.objects.create(name="basic", days=1, price=10)

    # جعبه‌پول در دسترس
    bm = BoxMoney.objects.get(user=user)
    bm.add_amount(10)

    # خرید اول
    sub_first = Subscription.buy_plan(user, plan)
    assert sub_first.plan == plan

    # خرید دوم قبل از انقضا → ‌باید تمدید شود
    before = sub_first.end_date
    sub_second = Subscription.buy_plan(user, plan)
    assert sub_second.end_date > before
