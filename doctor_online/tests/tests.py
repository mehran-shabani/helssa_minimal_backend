import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from doctor_online.models import Doctor

@pytest.mark.django_db
def test_doctor_full_name_and_str():
    img = SimpleUploadedFile("img.jpg", b"data")
    doc = Doctor.objects.create(first_name="Ali", last_name="B", specialty="GP", image=img)
    assert doc.full_name == "Ali B"
    assert str(doc) == "Ali B - GP"

@pytest.mark.django_db
def test_only_one_oncall_doctor():
    img = SimpleUploadedFile("img.jpg", b"data")
    Doctor.objects.create(first_name="A", last_name="B", specialty="GP", image=img, is_oncall=True)
    with pytest.raises(ValidationError):
        Doctor.objects.create(first_name="C", last_name="D", specialty="ENT", image=img, is_oncall=True)
