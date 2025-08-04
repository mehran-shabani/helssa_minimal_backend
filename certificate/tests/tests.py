import pytest
from django.contrib.auth import get_user_model
from certificate.models import MedicalCertificate

User = get_user_model()


@pytest.mark.django_db
def test_medical_certificate_str():
    user = User.objects.create_user(
        username="certuser",
        email="cert@example.com",
        password="pwd",
    )
    cert = MedicalCertificate.objects.create(
        user=user,
        first_name="Ali",
        last_name="B",
        national_code="123",
        sick_days=1,
        sick_name="flu",
    )
    assert str(cert) == "گواهی Ali B"
