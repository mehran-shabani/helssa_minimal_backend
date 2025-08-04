import pytest
from django.contrib.auth import get_user_model
from telemedicine.models import BoxMoney, Order, validate_image_url
from rest_framework.exceptions import ValidationError
from django.core.exceptions import ValidationError as DjangoValidationError

User = get_user_model()

@pytest.mark.django_db
def test_box_money_operations():
    user = User.objects.create_user(username="bm", email="bm@example.com", password="pwd")
    wallet = user.box_money
    assert wallet.amount == 300000
    assert wallet.has_sufficient_balance(200000)
    assert wallet.deduct_amount(100000) is True
    assert wallet.get_balance() == 200000
    wallet.add_amount(50000)
    assert wallet.get_balance() == 250000
    assert not wallet.deduct_amount(999999)

@pytest.mark.django_db
def test_order_autofill_download_url():
    user = User.objects.create_user(username="ord", email="o@example.com", password="pwd")
    order = Order.objects.create(
        user=user,
        first_name="A",
        last_name="B",
        national_code="1234567890",
        order_number="ON1",
    )
    assert order.download_url.endswith("order_1234567890.pdf")

@pytest.mark.parametrize("url", [
    "http://example.com/image.jpg",
    "https://foo.com/pic.png",
])
def test_validate_image_url_valid(url):
    validate_image_url(url)

@pytest.mark.parametrize("url", [
    "not-a-url",
    "http://example.com/file.txt",
])
def test_validate_image_url_invalid(url):
    with pytest.raises((ValidationError, DjangoValidationError)):
        validate_image_url(url)
      
