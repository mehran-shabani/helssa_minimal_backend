import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
def test_request_otp_and_verify(monkeypatch):
    """کد OTP واقعی را از تابع send_sms گرفته و سپس همان را تأیید می‌کنیم."""
    # پرمیشن‌ها را خاموش می‌کنیم
    from medagent import views
    monkeypatch.setattr(views.RequestOTP, "permission_classes", [])
    monkeypatch.setattr(views.VerifyOTP, "permission_classes", [])

    client = APIClient()

    patient = User.objects.create_user(
        username="pat",
        email="p@x.com",
        password="p",
        phone_number="09113078859",
    )
    doctor = User.objects.create_user(
        username="doc",
        email="d@x.com",
        password="d",
        phone_number="09135666326",
    )
    doctor.is_doctor = True
    doctor.save()
    client.force_authenticate(user=doctor)

    captured: dict = {}

    def fake_send_sms(phone: str, raw: str):
        captured["code"] = raw

    # مهم: روی همان آبجکت views پچ می‌کنیم
    monkeypatch.setattr(views, "send_sms", fake_send_sms)

    url_req = reverse("medagent:request-otp")
    resp = client.post(url_req, {"phone_number": patient.phone_number}, format="json")
    assert resp.status_code == 200
    assert "code" in captured  # کد واقعاً گرفته شده است

    url_ver = reverse("medagent:verify-otp")
    resp2 = client.post(
        url_ver,
        {"phone_number": patient.phone_number, "code": captured["code"]},
        format="json",
    )
    assert resp2.status_code == 200
    assert resp2.data["patient_id"] == patient.id
