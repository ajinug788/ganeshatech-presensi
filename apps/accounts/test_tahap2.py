"""Tes Tahap 2: login/logout, rate limit, role gating, dashboard."""
import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse

from apps.accounts import ratelimit
from apps.tenants.models import Membership, Organization

PASSWORD = "Str0ng-Passw0rd!"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def org():
    return Organization.objects.create(name="SMK TeFa A", slug="smk-a")


def _default_org():
    org_obj, _ = Organization.objects.get_or_create(
        slug="smk-a", defaults={"name": "SMK TeFa A"}
    )
    return org_obj


def make_user(email, role, org_obj=None, **kw):
    user = get_user_model().objects.create_user(email, PASSWORD, **kw)
    Membership.objects.create(
        organization=org_obj if org_obj is not None else _default_org(), user=user, role=role
    )
    return user


def login(client, email, password=PASSWORD):
    return client.post(reverse("accounts:login"), {"username": email, "password": password})


def test_login_sukses_redirect_ke_dashboard_role(client, org):
    make_user("siswa@example.com", "siswa")
    resp = login(client, "siswa@example.com")
    assert resp.status_code == 302
    assert resp["Location"] == reverse("tenants:dashboard_siswa")
    # Dashboard menampilkan nama org + role.
    page = client.get(resp["Location"])
    assert page.status_code == 200
    assert b"SMK TeFa A" in page.content
    assert b"Siswa" in page.content


def test_login_gagal_email_salah(client):
    resp = login(client, "hantu@example.com", "Salah-Banget-1!")
    assert resp.status_code == 401
    assert not client.session.items() or "_auth_user_id" not in client.session


def test_logout(client, org):
    make_user("siswa2@example.com", "siswa")
    login(client, "siswa2@example.com")
    resp = client.post(reverse("accounts:logout"))
    assert resp.status_code == 302
    resp = client.get(reverse("tenants:dashboard_siswa"))
    assert resp.status_code == 302  # redirect ke login


def test_dashboard_butuh_login(client):
    resp = client.get(reverse("tenants:dashboard_siswa"))
    assert resp.status_code == 302


def test_user_tanpa_membership_ditolak(client):
    get_user_model().objects.create_user("kosong@example.com", PASSWORD)
    login(client, "kosong@example.com")
    resp = client.get(reverse("tenants:dashboard_siswa"))
    assert resp.status_code == 403


def test_rate_limit_login_setelah_10_gagal(client, org):
    email = "brute@example.com"
    make_user(email, "siswa")
    for _ in range(10):
        resp = login(client, email, "Password-Salah-1!")
        assert resp.status_code == 401
    # Percobaan ke-11 (bahkan dengan password benar) diblokir.
    resp = login(client, email, PASSWORD)
    assert resp.status_code == 429


def test_rate_limit_reset_setelah_sukses(client, org):
    email = "reset@example.com"
    make_user(email, "siswa")
    for _ in range(9):
        login(client, email, "Password-Salah-1!")
    # 9 gagal via client (IP tes) + 1 manual dengan IP sama → terkunci.
    from django.test import RequestFactory

    ip = ratelimit._client_ip(RequestFactory().get("/", REMOTE_ADDR="127.0.0.1"))
    # 9 gagal via client sudah tercatat dengan IP sama; +1 → 10 → terkunci.
    assert ratelimit.register_failure(email, ip) == 10
    assert ratelimit.is_locked(email, ip)
    ratelimit.reset_failures(email, ip)
    assert not ratelimit.is_locked(email, ip)


def test_rate_limit_per_ip(client, org):
    email = "ip@example.com"
    make_user(email, "siswa")
    for _ in range(10):
        ratelimit.register_failure(email, "9.9.9.9")
    assert ratelimit.is_locked(email, "9.9.9.9")
    assert not ratelimit.is_locked(email, "8.8.8.8")


def test_role_gating_siswa_tidak_bisa_dashboard_pembina(client, org):
    make_user("siswa3@example.com", "siswa")
    login(client, "siswa3@example.com")
    resp = client.get(reverse("tenants:dashboard_pembina"))
    assert resp.status_code == 403


def test_role_gating_pembina_bisa_dashboard_pembina(client, org):
    make_user("pembina@example.com", "pembina")
    login(client, "pembina@example.com")
    resp = client.get(reverse("tenants:dashboard_pembina"))
    assert resp.status_code == 200


def test_admin_dan_billing_bisa_dashboard_admin(client, org):
    make_user("admin@example.com", "admin")
    make_user("billing@example.com", "billing")
    for email in ("admin@example.com", "billing@example.com"):
        c = client.__class__()
        login(c, email)
        assert c.get(reverse("tenants:dashboard_admin")).status_code == 200


def test_membership_unique_per_org(org):
    user = get_user_model().objects.create_user("dua@example.com", PASSWORD)
    Membership.objects.create(organization=org, user=user, role="siswa")
    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        Membership.objects.create(organization=org, user=user, role="admin")
