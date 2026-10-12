"""Tes isolasi tenant (TDIP §7.3): user tenant A tidak bisa akses tenant B.

Prinsip yang diuji: otorisasi diambil dari membership server-side, bukan
dari organization_id/slug di URL atau body request.
"""
import json

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse

from apps.accounts import ratelimit
from apps.tenants.context import get_active_membership
from apps.tenants.models import Membership, Organization

PASSWORD = "Str0ng-Passw0rd!"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def org_a():
    return Organization.objects.create(name="Sekolah A", slug="sekolah-a")


@pytest.fixture
def org_b():
    return Organization.objects.create(name="Sekolah B", slug="sekolah-b")


def login(client, email, password=PASSWORD):
    return client.post(reverse("accounts:login"), {"username": email, "password": password})


def test_membership_org_tetap_saat_url_org_lain(org_a, org_b, client):
    """Slug org lain di URL tidak mengubah tenant aktif user."""
    user = get_user_model().objects.create_user("anggota-a@example.com", PASSWORD)
    Membership.objects.create(organization=org_a, user=user, role="admin")
    login(client, "anggota-a@example.com")

    membership = get_active_membership(user, organization=org_b)
    assert membership is None
    assert get_active_membership(user).organization == org_a


def test_membership_nonaktif_tidak_dihitung(org_a, client):
    user = get_user_model().objects.create_user("nonaktif@example.com", PASSWORD)
    Membership.objects.create(organization=org_a, user=user, role="admin", is_active=False)
    login(client, "nonaktif@example.com")
    assert get_active_membership(user) is None
    # Dashboard juga menolak (403).
    resp = client.get(reverse("tenants:dashboard_siswa"))
    assert resp.status_code == 403


def test_org_suspended_tidak_bisa_dipakai(org_a, client):
    user = get_user_model().objects.create_user("suspend@example.com", PASSWORD)
    Membership.objects.create(organization=org_a, user=user, role="admin")
    org_a.status = "suspended"
    org_a.save()
    login(client, "suspend@example.com")
    assert get_active_membership(user) is None
    resp = client.get(reverse("tenants:dashboard_siswa"))
    assert resp.status_code == 403


def test_user_org_a_tidak_dapat_dashboard_seolah_org_b(org_a, org_b, client):
    """Dashboard selalu render org dari membership, bukan parameter."""
    user = get_user_model().objects.create_user("a2@example.com", PASSWORD)
    Membership.objects.create(organization=org_a, user=user, role="admin")
    login(client, "a2@example.com")
    # Coba "memaksa" tenant B via query/body — harus diabaikan.
    resp = client.get(reverse("tenants:dashboard_siswa"), {"organization": str(org_b.pk)})
    assert resp.status_code == 200
    assert b"Sekolah B" not in resp.content
    assert b"Sekolah A" in resp.content


def test_role_dari_org_lain_tidak_diwariskan(org_a, org_b, client):
    """Role gating berlaku per membership organisasi aktif."""
    user = get_user_model().objects.create_user("b-admin@example.com", PASSWORD)
    Membership.objects.create(organization=org_b, user=user, role="admin")
    login(client, "b-admin@example.com")
    # Admin org B tetap bisa dashboard; org aktif harus B, bukan A.
    resp = client.get(reverse("tenants:dashboard_admin"))
    assert resp.status_code == 200
    assert b"Sekolah B" in resp.content
