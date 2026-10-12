"""Tes dashboard admin (mockup Web Builder → data nyata).

File baru; tidak mengubah tes lama. Semua endpoint ter-scope tenant,
role-gated admin/billing.
"""
import uuid
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client
from django.urls import reverse
from django.utils import timezone as dj_timezone

from apps.attendance.models import AttendanceDay, AttendanceLocation
from apps.audit.models import AuditLog
from apps.tenants.models import Membership, Organization

_WIB_TZ = ZoneInfo("Asia/Jakarta")
PASSWORD = "Str0ng-Passw0rd!"
pytestmark = pytest.mark.django_db

TODAY = dj_timezone.localtime(dj_timezone.now(), _WIB_TZ).date()


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _make_org(slug):
    org = Organization.objects.create(name=f"Sekolah {slug}", slug=slug)
    admin = get_user_model().objects.create_user(
        f"admin-{slug}@example.com", PASSWORD
    )
    Membership.objects.create(
        organization=org, user=admin, role=Membership.Role.ADMIN
    )
    return org, admin


def _login(client, email):
    resp = client.post(
        reverse("accounts:login"), {"username": email, "password": PASSWORD}
    )
    assert resp.status_code in (302, 200)


def test_admin_dashboard_200_dan_angka_benar(client):
    org, admin = _make_org("admtest")
    loc = AttendanceLocation.objects.create(
        organization=org, name="Bengkel A",
        latitude="-6.2", longitude="106.8",
    )
    siswa1 = org.students.create(
        organization=org, student_number="S1", full_name="Satu Dua"
    )
    siswa2 = org.students.create(
        organization=org, student_number="S2", full_name="Dua Tiga"
    )
    siswa3 = org.students.create(
        organization=org, student_number="S3", full_name="Tiga Empat"
    )
    AttendanceDay.objects.create(
        organization=org, student=siswa1, work_date=TODAY,
        status=AttendanceDay.Status.PRESENT,
        check_in_at=dj_timezone.now(), check_in_location=loc,
    )
    AttendanceDay.objects.create(
        organization=org, student=siswa2, work_date=TODAY,
        status=AttendanceDay.Status.LATE, late_minutes=8,
        check_in_at=dj_timezone.now(),
    )
    # siswa3 belum absen.

    _login(client, f"admin-admtest@example.com")
    resp = client.get(reverse("tenants:dashboard_admin"))
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "Sekolah admtest" in content  # nama org dari organization.name
    assert "S1" in content and "S3" in content
    # KPI: total 3, hadir 1, terlambat 1, belum 1
    ctx = resp.context
    assert ctx["total_siswa"] == 3
    assert ctx["hadir"] == 1
    assert ctx["terlambat"] == 1
    assert ctx["belum_absen"] == 1
    assert ctx["pct_hadir"] == 33.3
    # Perlu tindakan memuat siswa3
    assert any(s.pk == siswa3.pk for s in ctx["belum_list"])
    # Aktivitas memuat 2 baris
    assert len(ctx["aktivitas_rows"]) == 2


def test_pembina_dan_siswa_dilarang_dashboard_admin(client):
    org, _ = _make_org("admdeny")
    pembina = get_user_model().objects.create_user(
        "pembina-admdeny@example.com", PASSWORD
    )
    Membership.objects.create(
        organization=org, user=pembina, role=Membership.Role.PEMBINA
    )
    siswa_user = get_user_model().objects.create_user(
        "siswa-admdeny@example.com", PASSWORD
    )
    Membership.objects.create(
        organization=org, user=siswa_user, role=Membership.Role.SISWA
    )

    _login(client, "pembina-admdeny@example.com")
    resp = client.get(reverse("tenants:dashboard_admin"))
    assert resp.status_code == 403

    _login(client, "siswa-admdeny@example.com")
    resp = client.get(reverse("tenants:dashboard_admin"))
    assert resp.status_code == 403


def test_catat_izin_buat_attendanceday_dan_audit(client):
    org, admin = _make_org("admizin")
    siswa = org.students.create(
        organization=org, student_number="S9", full_name="Sembilan"
    )
    _login(client, "admin-admizin@example.com")

    # Alasan kosong → ditolak, tidak ada AttendanceDay.
    resp = client.post(
        reverse("reports:admin_catat_izin"),
        {"student_id": str(siswa.pk), "status": "excused", "reason": ""},
    )
    assert resp.status_code == 302
    assert AttendanceDay.objects.filter(student=siswa).count() == 0
    assert AuditLog.objects.filter(action='attendance_status_recorded').count() == 0

    # Valid → AttendanceDay dibuat + audit.
    resp = client.post(
        reverse("reports:admin_catat_izin"),
        {
            "student_id": str(siswa.pk),
            "status": "excused",
            "reason": "Sakit, konfirmasi ortu",
        },
    )
    assert resp.status_code == 302
    day = AttendanceDay.objects.get(
        organization=org, student=siswa, work_date=TODAY
    )
    assert day.status == AttendanceDay.Status.EXCUSED
    log = AuditLog.objects.filter(action="attendance_status_recorded").get()
    assert log.action == "attendance_status_recorded"
    assert log.reason == "Sakit, konfirmasi ortu"
    assert log.metadata["new_status"] == "excused"

    # Siswa org lain tidak bisa dipakai (scope tenant).
    org_b, admin_b = _make_org("admizin-b")
    siswa_b = org_b.students.create(
        organization=org_b, student_number="SB1", full_name="B Siswa"
    )
    client.force_login(admin)
    resp = client.post(
        reverse("reports:admin_catat_izin"),
        {
            "student_id": str(siswa_b.pk),
            "status": "absent",
            "reason": "coba lintas tenant",
        },
    )
    assert resp.status_code == 302
    assert not AttendanceDay.objects.filter(
        student=siswa_b, work_date=TODAY
    ).exists()
    assert AuditLog.objects.filter(
        reason="coba lintas tenant"
    ).count() == 0


def test_riwayat_koreksi_dan_csv(client):
    org, admin = _make_org("admriw")
    siswa = org.students.create(
        organization=org, student_number="S5", full_name="Lima"
    )
    day = AttendanceDay.objects.create(
        organization=org, student=siswa, work_date=TODAY,
        status=AttendanceDay.Status.PRESENT,
    )
    _login(client, "admin-admriw@example.com")

    # Koreksi via endpoint existing → audit + muncul di riwayat.
    resp = client.post(
        reverse("reports:koreksi", args=[day.pk]),
        {"status": "excused", "reason": "Surat dokter"},
    )
    assert resp.status_code == 302
    assert AuditLog.objects.filter(action="attendance_corrected").count() == 1

    resp = client.get(reverse("reports:riwayat_koreksi"))
    assert resp.status_code == 200
    assert b"Surat dokter" in resp.content

    resp = client.get(reverse("reports:rekap_csv"))
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    body = b"".join(resp.streaming_content)
    assert b"nama,student_number,tanggal" in body

    # Riwayat koreksi terlarang untuk siswa.
    siswa_user = get_user_model().objects.create_user(
        "siswa-admriw@example.com", PASSWORD
    )
    Membership.objects.create(
        organization=org, user=siswa_user, role=Membership.Role.SISWA
    )
    _login(client, "siswa-admriw@example.com")
    assert client.get(reverse("reports:riwayat_koreksi")).status_code == 403
