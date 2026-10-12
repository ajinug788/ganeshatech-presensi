"""Tes fondasi Tahap 1: custom User email-only (DEC-01) + health endpoint."""
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

User = get_user_model()


@pytest.mark.django_db
def test_create_user_email_lowercase():
    u = User.objects.create_user("  Aku@Example.COM ", "Str0ng-Passw0rd!")
    assert u.email == "aku@example.com"
    assert u.is_active and not u.is_staff and not u.is_platform_admin
    assert u.username is None


@pytest.mark.django_db
def test_email_unique():
    User.objects.create_user("sama@example.com", "Str0ng-Passw0rd!")
    with pytest.raises(IntegrityError):
        User.objects.create_user("SAMA@example.com", "Str0ng-Passw0rd!")


@pytest.mark.django_db
def test_create_superuser_flags():
    u = User.objects.create_superuser("root@example.com", "Str0ng-Passw0rd!")
    assert u.is_staff and u.is_superuser and u.is_platform_admin


def test_healthz(client):
    resp = client.get("/healthz/")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_login_page_uses_email(client):
    resp = client.get("/admin/login/")
    assert resp.status_code == 200
