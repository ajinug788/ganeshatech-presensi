"""Tes Tahap 3 — Master data: CRUD siswa/lokasi/kebijakan, tenant isolation,
validasi model, provisioning akun, pagination/filter, audit.
"""
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.attendance.models import AttendanceLocation, AttendancePolicy, StudentProfile
from apps.tenants.models import Membership, Organization

PASSWORD = "Str0ng-Passw0rd!"

pytestmark = pytest.mark.django_db


@pytest.fixture
def org_a():
    return Organization.objects.create(name="SMK A", slug="smk-a")


@pytest.fixture
def org_b():
    return Organization.objects.create(name="SMK B", slug="smk-b")


def make_admin(org, email="admin@example.com"):
    user = get_user_model().objects.create_user(email, PASSWORD)
    Membership.objects.create(organization=org, user=user, role="admin")
    return user


def login_org(client, org, email="admin@example.com", role="admin"):
    user = get_user_model().objects.create_user(email, PASSWORD)
    Membership.objects.create(organization=org, user=user, role=role)
    client.post(reverse("accounts:login"), {"username": email, "password": PASSWORD})
    return user


# ------------------------------------------------------------- validasi model


def test_location_validasi_koordinat(org_a):
    loc = AttendanceLocation(
        organization=org_a, name="Bengkel", latitude=95, longitude=0
    )
    with pytest.raises(Exception):
        loc.full_clean()


def test_location_validasi_radius_harus_positif(org_a):
    loc = AttendanceLocation(
        organization=org_a, name="Bengkel", latitude=0, longitude=0, radius_m=0
    )
    with pytest.raises(Exception):
        loc.full_clean()


def test_policy_validasi_jam_check_in(org_a):
    policy = AttendancePolicy(
        organization=org_a,
        days_active=[0, 1],
        check_in_start="09:00",
        check_in_end="08:00",
        check_out_start="15:00",
        check_out_end="17:00",
    )
    with pytest.raises(Exception):
        policy.full_clean()


def test_policy_validasi_jam_check_out(org_a):
    policy = AttendancePolicy(
        organization=org_a,
        days_active=[0, 1],
        check_in_start="07:00",
        check_in_end="09:00",
        check_out_start="18:00",
        check_out_end="17:00",
    )
    with pytest.raises(Exception):
        policy.full_clean()


def test_student_number_unik_per_org(org_a, org_b):
    StudentProfile.objects.create(
        organization=org_a, student_number="1001", full_name="Satu"
    )
    # Org lain boleh NIS sama.
    StudentProfile.objects.create(
        organization=org_b, student_number="1001", full_name="Dua"
    )
    with pytest.raises(IntegrityError):
        StudentProfile.objects.create(
            organization=org_a, student_number="1001", full_name="Tiga"
        )


def test_days_active_validasi(org_a):
    policy = AttendancePolicy(
        organization=org_a,
        days_active=[0, 9],
        check_in_start="07:00",
        check_in_end="09:00",
        check_out_start="15:00",
        check_out_end="17:00",
    )
    with pytest.raises(Exception):
        policy.full_clean()


# ------------------------------------------------------------- CRUD via client


def test_crud_siswa_flow(client, org_a):
    login_org(client, org_a)
    url = reverse("attendance:student_create")
    resp = client.post(
        url,
        {
            "student_number": "1001",
            "full_name": "Andi",
            "group": "10A",
            "is_active": "on",
        },
    )
    assert resp.status_code == 302
    student = StudentProfile.objects.get(
        organization=org_a, student_number="1001"
    )
    assert student.user is None  # tanpa email → tanpa akun
    assert AuditLog.objects.filter(action="student_created").exists()

    # update
    resp = client.post(
        reverse("attendance:student_update", args=[student.pk]),
        {"student_number": "1001", "full_name": "Andi K", "group": "10B", "is_active": "on"},
    )
    assert resp.status_code == 302
    student.refresh_from_db()
    assert student.full_name == "Andi K"
    assert AuditLog.objects.filter(action="student_updated").exists()

    # delete (menonaktifkan)
    resp = client.post(reverse("attendance:student_delete", args=[student.pk]))
    assert resp.status_code == 302
    student.refresh_from_db()
    assert student.is_active is False
    assert AuditLog.objects.filter(action="student_deleted").exists()


def test_crud_lokasi_flow(client, org_a):
    login_org(client, org_a)
    resp = client.post(
        reverse("attendance:location_create"),
        {
            "name": "Bengkel Mesin",
            "latitude": "-6.200000",
            "longitude": "106.816666",
            "radius_m": "150",
            "max_accuracy_m": "40",
            "is_active": "on",
        },
    )
    assert resp.status_code == 302
    loc = AttendanceLocation.objects.get(organization=org_a, name="Bengkel Mesin")
    assert AuditLog.objects.filter(action="location_created").exists()

    resp = client.post(
        reverse("attendance:location_update", args=[loc.pk]),
        {
            "name": "Bengkel Mesin 2",
            "latitude": "-6.200000",
            "longitude": "106.816666",
            "radius_m": "150",
            "max_accuracy_m": "40",
            "is_active": "on",
        },
    )
    assert resp.status_code == 302
    loc.refresh_from_db()
    assert loc.name == "Bengkel Mesin 2"
    assert AuditLog.objects.filter(action="location_updated").exists()

    client.post(reverse("attendance:location_delete", args=[loc.pk]))
    loc.refresh_from_db()
    assert loc.is_active is False
    assert AuditLog.objects.filter(action="location_deleted").exists()


def test_policy_flow(client, org_a):
    login_org(client, org_a)
    url = reverse("attendance:policy")
    resp = client.get(url)
    assert resp.status_code == 200
    assert AttendancePolicy.objects.filter(organization=org_a).exists()
    resp = client.post(
        url,
        {
            "days_active": ["0", "1", "2", "3", "4"],
            "check_in_start": "07:00",
            "check_in_end": "09:00",
            "check_out_start": "15:00",
            "check_out_end": "17:00",
            "late_tolerance_min": "10",
        },
    )
    assert resp.status_code == 302
    policy = AttendancePolicy.objects.get(organization=org_a)
    assert policy.days_active == [0, 1, 2, 3, 4]
    assert policy.late_tolerance_min == 10
    assert AuditLog.objects.filter(action="policy_updated", organization=org_a).exists()


def test_policy_lokasi_terbatas_ke_org(client, org_a, org_b):
    login_org(client, org_a)
    loc_b = AttendanceLocation.objects.create(
        organization=org_b, name="Lokasi B", latitude=0, longitude=0
    )
    resp = client.get(reverse("attendance:policy"))
    # Form lokasi hanya menampilkan lokasi org A.
    content = resp.content.decode()
    assert "Lokasi B" not in content


# ------------------------------------------------------------- provisioning akun


def test_provision_siswa_dengan_email(client, org_a):
    login_org(client, org_a)
    resp = client.post(
        reverse("attendance:student_create"),
        {
            "student_number": "2001",
            "full_name": "Budi",
            "group": "",
            "email": "budi@example.com",
            "is_active": "on",
        },
    )
    assert resp.status_code == 302
    student = StudentProfile.objects.get(organization=org_a, student_number="2001")
    user = get_user_model().objects.get(email="budi@example.com")
    assert student.user == user
    assert user.email_verified_at is None
    assert user.memberships.filter(
        organization=org_a, role="siswa", is_active=True
    ).exists()
    # Password tidak muncul di redirect response.
    assert "password" not in resp.content.decode().lower()
    assert AuditLog.objects.filter(
        action="account_provisioned", organization=org_a
    ).exists()


def test_provision_email_duplikat_ditolak(client, org_a):
    login_org(client, org_a)
    get_user_model().objects.create_user("dupe@example.com", PASSWORD)
    resp = client.post(
        reverse("attendance:student_create"),
        {
            "student_number": "3001",
            "full_name": "Cici",
            "email": "dupe@example.com",
            "is_active": "on",
        },
    )
    assert resp.status_code == 200  # form error
    assert not StudentProfile.objects.filter(organization=org_a, student_number="3001").exists()


# ------------------------------------------------------------- tenant isolation


def test_isolasi_tenant_siswa(client, org_a, org_b):
    login_org(client, org_b, email="admin-b@example.com")
    student_a = StudentProfile.objects.create(
        organization=org_a, student_number="4001", full_name="Milik A"
    )
    for url in (
        reverse("attendance:student_detail", args=[student_a.pk]),
        reverse("attendance:student_update", args=[student_a.pk]),
        reverse("attendance:student_delete", args=[student_a.pk]),
    ):
        assert client.get(url).status_code in (403, 404), url
    # List hanya berisi org B.
    resp = client.get(reverse("attendance:student_list"))
    assert "Milik A" not in resp.content.decode()


def test_isolasi_tenant_lokasi(client, org_a, org_b):
    login_org(client, org_b, email="admin-b2@example.com")
    loc_a = AttendanceLocation.objects.create(
        organization=org_a, name="Bengkel Org A", latitude=0, longitude=0
    )
    for url in (
        reverse("attendance:location_update", args=[loc_a.pk]),
        reverse("attendance:location_delete", args=[loc_a.pk]),
    ):
        assert client.get(url).status_code in (403, 404), url
    resp = client.get(reverse("attendance:location_list"))
    assert "Bengkel Mesin" not in resp.content.decode()


def test_isolasi_tenant_policy(client, org_a, org_b):
    login_org(client, org_b, email="admin-b3@example.com")
    AttendancePolicy.objects.create(
        organization=org_a,
        days_active=[0],
        check_in_start="07:00",
        check_in_end="09:00",
        check_out_start="15:00",
        check_out_end="17:00",
    )
    # Policy org B terpisah; tidak menyentuh org A.
    resp = client.get(reverse("attendance:policy"))
    assert resp.status_code == 200
    assert AttendancePolicy.objects.filter(organization=org_b).exists()
    assert AttendancePolicy.objects.filter(organization=org_a).count() == 1


def test_role_bukan_admin_ditolak(client, org_a):
    login_org(client, org_a, email="siswa@example.com", role="siswa")
    for url in (
        reverse("attendance:student_list"),
        reverse("attendance:location_list"),
        reverse("attendance:policy"),
    ):
        resp = client.get(url)
        assert resp.status_code in (302, 403), url


def test_tidak_login_redirect(client):
    resp = client.get(reverse("attendance:student_list"))
    assert resp.status_code == 302
    assert "login" in resp["Location"]


# ------------------------------------------------------------- list/filter/pagination


def test_list_filter_dan_pagination(client, org_a):
    login_org(client, org_a)
    for i in range(25):
        StudentProfile.objects.create(
            organization=org_a,
            student_number=f"{5000+i}",
            full_name=f"Siswa {i:02d}",
            group="10A" if i < 22 else "11B",
        )
    StudentProfile.objects.create(
        organization=org_a, student_number="9999", full_name="Nonaktif X",
        is_active=False,
    )

    resp = client.get(reverse("attendance:student_list"))
    assert resp.status_code == 200
    # 26 siswa (25 aktif + 1 nonaktif) → page 1 berisi 20.
    assert resp.context["page_obj"].paginator.count == 26
    assert len(resp.context["object_list"]) == 20

    # Pagination page 2 (26 total - 20 = 6).
    resp = client.get(reverse("attendance:student_list") + "?page=2")
    assert len(resp.context["object_list"]) == 6

    # Filter q.
    resp = client.get(reverse("attendance:student_list") + "?q=Siswa 03")
    assert resp.context["page_obj"].paginator.count == 1

    # Filter group.
    resp = client.get(reverse("attendance:student_list") + "?group=11B")
    assert resp.context["page_obj"].paginator.count == 3

    # Filter status.
    resp = client.get(reverse("attendance:student_list") + "?status=inactive")
    assert resp.context["page_obj"].paginator.count == 1
    assert resp.context["object_list"][0].full_name == "Nonaktif X"


def test_service_provision_langsung(org_a):
    student, temp_password = __import__(
        "apps.attendance.services", fromlist=["provision_student"]
    ).provision_student(
        organization=org_a,
        student_number="6001",
        full_name="Dedi",
        email="dedi@example.com",
    )
    assert temp_password and len(temp_password) >= 8
    assert student.user.email == "dedi@example.com"
