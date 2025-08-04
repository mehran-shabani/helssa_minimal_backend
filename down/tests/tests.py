import pytest
from down.models import AppUpdate


@pytest.mark.django_db
def test_app_update_str():
    upd = AppUpdate.objects.create(version="1.0", is_update_available=True)
    assert str(upd) == "Version 1.0 - Available: True"
