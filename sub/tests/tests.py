import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from sub.models import SubscriptionPlan, Subscription
from telemedicine.models import BoxMoney

User = get_user_model()

@pytest.fixture
def user(db):
    user = User.objects.create_user(username="testuser", auth_code= '123456', phone_number='09113078859', password="testpass")
    return user

@pytest.fixture
def api_client(user):
    client = APIClient()
    response = client.post('/api/verify/', {'phone_number': "09113078859", 'code': 123456})
    assert response.status_code == 200
    access = response.data['access']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    return client

@pytest.fixture
def plans(db):
    p1 = SubscriptionPlan.objects.create(name="یک‌ماهه آزمایشی", days=31, price=30000)
    p2 = SubscriptionPlan.objects.create(name="سه‌ماهه فصلی", days=90, price=790000)
    p3 = SubscriptionPlan.objects.create(name="شش‌ماهه مراقبتی", days=180, price=1490000)
    p4 = SubscriptionPlan.objects.create(name="یک‌ساله سالیانه", days=365, price=3290000)
    return [p1, p2, p3, p4]

@pytest.mark.django_db
def test_get_plans(api_client, plans):
    url = reverse("subscription-plan-list")
    response = api_client.get(url)
    assert response.status_code == 200
    assert len(response.data) >= 4
    assert response.data[0]['name'] == "یک‌ماهه آزمایشی"

@pytest.mark.django_db
def test_buy_plan_with_sufficient_balance(user, api_client, plans):
    # افزایش موجودی
    user.box_money.add_amount(35000)
    url = reverse("purchase-subscription")
    data = {"plan_id": plans[0].id}  # یک‌ماهه آزمایشی
    response = api_client.post(url, data)
    assert response.status_code == 201
    assert response.data['plan']['name'] == "یک‌ماهه آزمایشی"
    user.box_money.refresh_from_db()
    # کیف پول هنگام ایجاد کاربر به صورت سیگنال با 300000 تومان شارژ می‌شود
    # بنابراین پس از افزودن موجودی و خرید پلن باید 305000 باقی بماند
    assert user.box_money.amount == 305000

@pytest.mark.django_db
def test_buy_plan_with_insufficient_balance(user, api_client, plans):
    url = reverse("purchase-subscription")
    data = {"plan_id": plans[1].id}  # سه‌ماهه فصلی (790000)
    response = api_client.post(url, data)
    assert response.status_code == 402
    assert "موجودی کافی نیست" in response.data['detail']

@pytest.mark.django_db
def test_extend_subscription(user, api_client, plans):
    # خرید اولیه
    user.box_money.add_amount(1000000)
    url = reverse("purchase-subscription")
    data = {"plan_id": plans[0].id}
    response = api_client.post(url, data)
    assert response.status_code == 201
    end_date_1 = Subscription.objects.get(user=user).end_date

    # خرید مجدد همان پلن (تمدید)
    user.box_money.add_amount(30000)
    response = api_client.post(url, data)
    assert response.status_code == 201
    end_date_2 = Subscription.objects.get(user=user).end_date
    assert end_date_2 > end_date_1  # باید تمدید شده باشد

@pytest.mark.django_db
def test_get_user_subscription(user, api_client, plans):
    # بدون اشتراک
    url = reverse("user-subscription")
    response = api_client.get(url)
    assert response.status_code == 404

    # خرید اشتراک
    user.box_money.add_amount(40000)
    buy_url = reverse("purchase-subscription")
    api_client.post(buy_url, {"plan_id": plans[0].id})

    # حالا چک کن
    response = api_client.get(url)
    assert response.status_code == 200
    assert response.data['plan']['name'] == "یک‌ماهه آزمایشی"
    assert response.data['is_active'] is True


@pytest.mark.django_db
def test_buy_plan_invalid_inputs(user, api_client, plans):
    url = reverse("purchase-subscription")
    # Missing plan_id
    response = api_client.post(url, {})
    assert response.status_code == 400

    # Invalid plan_id
    response = api_client.post(url, {"plan_id": 9999})
    assert response.status_code == 404
