"""Tes Tahap 6 — Dashboard pembina, rekap/laporan, koreksi, CSV, mark_absent.

TDIP v1.2 §16 Tahap 6. Semua endpoint baru wajib ter-scope tenant dan
role-gated.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client
from django.urls import reverse
from django.utils import timezone as dj_timezone

from apps.attendance.models import (
    AttendanceDay,
    AttendanceLocation,
    AttendancePolicy,
    StudentProfile,
)
from apps.audit.models import AuditLog
from apps.tenants.models import Membership, Organization

_WIB_TZ = ZoneInfo("Asia/Jakarta")

PASSWORD = "Str0ng-Passw0rd!"
pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


class OrgFixture:
    def __init__(self, slug, role, with_policy=True):
        self.org = Organization.objects.create(name=f"Org {slug}", slug=slug)
        self.user = get_user_model().objects.create_user(
            f"{slug}-{role}@example.com", PASSWORD
        )
        Membership.objects.create(
            organization=self.org, user=self.user, role=role
        )
        self.students = []
        for i in range(1, 4):
            u = get_user_model().objects.create_user(
                f"{slug}-siswa{i}@example.com", PASSWORD
            )
            Membership.objects.create(
                organization=self.org, user=u, role=Membership.Role.SISWA
            )
            s = StudentProfile.objects.create(
                organization=self.org,
                user=u,
                student_number=f"{slug}-S{i}",
                full_name=f"Siswa {slug} {i}",
                group="10A" if i <= 2 else "10B",
            )
            self.students.append(s)
        if with_policy:
            self.loc = AttendanceLocation.objects.create(
                organization=self.org, name="Lokasi A",
                latitude="-6.200000", longitude="106.816666",
            )
            AttendancePolicy.objects.create(
                organization=self.org,
                days_active=[0, 1, 2, 3, 4, 5, 6],
                check_in_start="07:00",
                check_in_end="09:00",
                check_out_start="15:00",
                check_out_end="17:00",
                late_tolerance_min=15,
            )

    def day(self, student, work_date, status, late_minutes=0, check_in=None):
        return AttendanceDay.objects.create(
            organization=self.org,
            student=student,
            work_date=work_date,
            status=status,
            late_minutes=late_minutes,
            check_in_at=check_in,
        )


@pytest.fixture
def org_a():
    return OrgFixture("a", Membership.Role.PEMBINA)


@pytest.fixture
def org_b():
    return OrgFixture("b", Membership.Role.PEMBINA)


@pytest.fixture
def admin_a():
    return OrgFixture("adm", Membership.Role.ADMIN)


def login(client, email):
    res = client.post(
        reverse("accounts:login"), {"username": email, "password": PASSWORD}
    )
    assert res.status_code in (200, 302)


# ------------------------------------------------------- Dashboard pembina


def test_dashboard_pembina_angka_benar(org_a, client):
    today = dj_timezone.localtime(dj_timezone.now(), _WIB_TZ).date()
    s1, s2, s3 = org_a.students
    org_a.day(s1, today, AttendanceDay.Status.PRESENT,
              check_in=dj_timezone.now())
    org_a.day(s2, today, AttendanceDay.Status.LATE, late_minutes=10,
              check_in=dj_timezone.now())
    # s3 belum absen.

    login(client, "a-pembina@example.com")
    resp = client.get(reverse("reports:dashboard_pembina"))
    assert resp.status_code == 200
    assert resp.context["total_siswa"] == 3
    assert resp.context["hadir"] == 1
    assert resp.context["terlambat"] == 1
    assert resp.context["belum_absen"] == 1
    assert resp.context["sedang_berjalan"] == 2
    assert [s.full_name for s in resp.context["belum_list"]] == ["Siswa a 3"]


def test_dashboard_pembina_aktivitas_terakhir_maks_10(org_a, client):
    today = dj_timezone.localtime(dj_timezone.now(), _WIB_TZ).date()
    for i in range(15):
        org_a.day(org_a.students[0], today - timedelta(days=i),
                  AttendanceDay.Status.PRESENT, check_in=dj_timezone.now())
    login(client, "a-pembina@example.com")
    resp = client.get(reverse("reports:dashboard_pembina"))
    assert resp.status_code == 200
    assert len(resp.context["aktivitas"]) == 10


def test_siswa_tidak_bisa_akses_dashboard_pembina_dan_rekap(org_a, client):
    login(client, "a-siswa1@example.com")
    assert client.get(reverse("reports:dashboard_pembina")).status_code == 403
    assert client.get(reverse("reports:rekap")).status_code == 403
    assert client.get(reverse("reports:rekap_csv")).status_code == 403


# ------------------------------------------------------- Rekap


def test_rekap_filter_dan_persentase_benar(admin_a, client):
    today = dj_timezone.localtime(dj_timezone.now(), _WIB_TZ).date()
    s1, s2, _s3 = admin_a.students
    # s1: 2 hadir + 1 late + 1 absent → 3/4 = 75%
    admin_a.day(s1, today - timedelta(days=1), AttendanceDay.Status.PRESENT)
    admin_a.day(s1, today - timedelta(days=2), AttendanceDay.Status.PRESENT)
    admin_a.day(s1, today - timedelta(days=3), AttendanceDay.Status.LATE,
                late_minutes=20)
    admin_a.day(s1, today - timedelta(days=4), AttendanceDay.Status.ABSENT)
    admin_a.day(s2, today - timedelta(days=1), AttendanceDay.Status.EXCUSED)

    login(client, "adm-admin@example.com")
    resp = client.get(
        reverse("reports:rekap"),
        {"start": (today - timedelta(days=30)).isoformat(),
         "end": today.isoformat()},
    )
    assert resp.status_code == 200
    rows = {r["student"].pk: r for r in resp.context["rows"]}
    r1 = rows[s1.pk]
    assert r1["agg"]["present"] == 2
    assert r1["agg"]["late"] == 1
    assert r1["agg"]["absent"] == 1
    assert r1["agg"]["late_minutes"] == 20
    assert r1["pct"] == 75.0
    assert rows[s2.pk]["agg"]["excused"] == 1


def test_rekap_filter_kelompok(admin_a, client):
    today = dj_timezone.localtime(dj_timezone.now(), _WIB_TZ).date()
    s1, _s2, s3 = admin_a.students  # s1, s2 di 10A; s3 di 10B
    admin_a.day(s1, today - timedelta(days=1), AttendanceDay.Status.PRESENT)
    admin_a.day(s3, today - timedelta(days=1), AttendanceDay.Status.ABSENT)
    login(client, "adm-admin@example.com")
    resp = client.get(reverse("reports:rekap"), {"group": "10B"})
    rows = resp.context["rows"]
    assert {r["student"].pk for r in rows} == {s3.pk}


def test_rekap_detail_per_siswa(admin_a, client):
    today = dj_timezone.localtime(dj_timezone.now(), _WIB_TZ).date()
    s1, _s2, _s3 = admin_a.students
    admin_a.day(s1, today - timedelta(days=1), AttendanceDay.Status.PRESENT)
    login(client, "adm-admin@example.com")
    resp = client.get(reverse("reports:rekap"), {"student": str(s1.pk)})
    detail = resp.context["detail_student"]
    assert detail is not None and detail.pk == s1.pk
    assert resp.context["detail_days"].count() == 1


# ------------------------------------------------------- Koreksi


def test_koreksi_hanya_admin(admin_a, org_a, client):
    today = dj_timezone.localtime(dj_timezone.now(), _WIB_TZ).date()
    day = admin_a.day(admin_a.students[0], today, AttendanceDay.Status.PRESENT)
    # Pembina org yang sama-ish tidak relevan; siswa org A ditolak.
    login(client, "a-siswa1@example.com")
    resp = client.get(reverse("reports:koreksi", args=[day.pk]))
    assert resp.status_code == 403

    # Pembina tidak boleh koreksi (admin saja).
    login(client, "a-pembina@example.com")
    resp = client.post(
        reverse("reports:koreksi", args=[day.pk]),
        {"status": "absent", "reason": "tes"},
    )
    assert resp.status_code == 403


def test_koreksi_wajib_alasan_dan_audit_tercatat(admin_a, client):
    today = dj_timezone.localtime(dj_timezone.now(), _WIB_TZ).date()
    day = admin_a.day(admin_a.students[0], today, AttendanceDay.Status.PRESENT)
    login(client, "adm-admin@example.com")

    # Tanpa alasan → 400, status tidak berubah, tanpa audit.
    resp = client.post(
        reverse("reports:koreksi", args=[day.pk]), {"status": "absent", "reason": ""}
    )
    assert resp.status_code == 400
    day.refresh_from_db()
    assert day.status == AttendanceDay.Status.PRESENT
    assert not AuditLog.objects.filter(action="attendance_corrected").exists()

    # Status sama → 400.
    resp = client.post(
        reverse("reports:koreksi", args=[day.pk]),
        {"status": "present", "reason": "sama"},
    )
    assert resp.status_code == 400

    # Koreksi valid → 302 + audit attendance_corrected dengan alasan.
    resp = client.post(
        reverse("reports:koreksi", args=[day.pk]),
        {"status": "excused", "reason": "Sakit dengan surat dokter"},
    )
    assert resp.status_code == 302
    day.refresh_from_db()
    assert day.status == AttendanceDay.Status.EXCUSED
    log = AuditLog.objects.filter(
        action="attendance_corrected", object_id=str(day.pk)
    ).get()
    assert log.reason == "Sakit dengan surat dokter"
    assert log.metadata["old_status"] == "present"
    assert log.metadata["new_status"] == "excused"


def test_koreksi_tenant_isolation(org_a, admin_a, client):
    """Admin org A tidak bisa mengoreksi AttendanceDay org lain (404)."""
    today = dj_timezone.localtime(dj_timezone.now(), _WIB_TZ).date()
    day_b = org_a.day(org_a.students[0], today, AttendanceDay.Status.PRESENT)
    login(client, "adm-admin@example.com")
    resp = client.post(
        reverse("reports:koreksi", args=[day_b.pk]),
        {"status": "absent", "reason": "coba lintas tenant"},
    )
    assert resp.status_code == 404
    day_b.refresh_from_db()
    assert day_b.status == AttendanceDay.Status.PRESENT


# ------------------------------------------------------- CSV


def test_export_csv_isi_benar(admin_a, client):
    today = dj_timezone.localtime(dj_timezone.now(), _WIB_TZ).date()
    s1, _s2, _s3 = admin_a.students
    check_in = datetime(2026, 1, 5, 8, 0, tzinfo=_WIB_TZ)
    day = admin_a.day(s1, today, AttendanceDay.Status.PRESENT, check_in=check_in)
    day.check_in_location = admin_a.loc
    day.save(update_fields=["check_in_location"])

    login(client, "adm-admin@example.com")
    resp = client.get(reverse("reports:rekap_csv"))
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    lines = b"".join(resp.streaming_content).decode().strip().splitlines()
    assert lines[0] == (
        "nama,student_number,tanggal,status,late_minutes,jam_masuk,jam_keluar,lokasi"
    )
    assert f"Siswa adm 1,adm-S1,{today.isoformat()},present,0,08:00,—,Lokasi A" in lines


def test_export_csv_filter_dan_isolasi_tenant(org_a, admin_a, client):
    today = dj_timezone.localtime(dj_timezone.now(), _WIB_TZ).date()
    org_a.day(org_a.students[0], today, AttendanceDay.Status.ABSENT)
    login(client, "adm-admin@example.com")
    resp = client.get(reverse("reports:rekap_csv"))
    content = b"".join(resp.streaming_content).decode()
    assert "Org a" not in content and "a-S1" not in content

    login(client, "a-pembina@example.com")
    resp = client.get(reverse("reports:rekap_csv"))
    content = b"".join(resp.streaming_content).decode()
    assert "a-S1" in content


# ------------------------------------------------------- mark_absent


def test_mark_absent_idempoten_dan_hanya_hari_lewat(admin_a):
    from apps.reports.services import mark_absent
    from datetime import datetime as dt

    today = dj_timezone.localtime(dj_timezone.now(), _WIB_TZ).date()
    yesterday = today - timedelta(days=1)

    # Kemarin tanpa kehadiran → dibuat 3 absent.
    created = mark_absent(organization=admin_a.org, ref_date=yesterday)
    assert created == 3
    assert AttendanceDay.objects.filter(
        organization=admin_a.org, work_date=yesterday,
        status=AttendanceDay.Status.ABSENT,
    ).count() == 3

    # Idempoten: panggil ulang → 0 baru, status tidak berubah.
    assert mark_absent(organization=admin_a.org, ref_date=yesterday) == 0

    # Kehadiran yang sudah ada tidak diubah.
    admin_a.day(admin_a.students[0], yesterday - timedelta(days=1),
                AttendanceDay.Status.PRESENT)
    # Hanya 2 siswa lain yang belum ada record di hari itu; yang sudah
    # ada (s1, present) tidak diubah/diduplikasi.
    assert mark_absent(
        organization=admin_a.org, ref_date=yesterday - timedelta(days=1)
    ) == 2
    assert AttendanceDay.objects.filter(
        organization=admin_a.org, work_date=yesterday - timedelta(days=1)
    ).count() == 3
    assert AttendanceDay.objects.filter(
        organization=admin_a.org,
        work_date=yesterday - timedelta(days=1),
        status=AttendanceDay.Status.PRESENT,
    ).get().status == AttendanceDay.Status.PRESENT

    # Masa depan → tidak dibuat.
    assert mark_absent(
        organization=admin_a.org, ref_date=today + timedelta(days=1)
    ) == 0


def test_mark_absent_semua_org_aktif_lewat_command(admin_a, org_b, org_a):
    from django.core.management import call_command
    from io import StringIO

    yesterday = dj_timezone.localtime(dj_timezone.now(), _WIB_TZ).date() - timedelta(days=1)
    out = StringIO()
    call_command("mark_absent", stdout=out)
    assert "Selesai" in out.getvalue()
    for org in (admin_a.org, org_b.org, org_a.org):
        assert AttendanceDay.objects.filter(
            organization=org, work_date=yesterday,
            status=AttendanceDay.Status.ABSENT,
        ).count() == 3


def test_mark_absent_org_suspended_tidak_diproses(admin_a):
    admin_a.org.status = "suspended"
    admin_a.org.save()
    yesterday = dj_timezone.localtime(dj_timezone.now(), _WIB_TZ).date() - timedelta(days=1)
    from apps.reports.services import mark_absent
    assert mark_absent(organization=admin_a.org, ref_date=yesterday) == 0


def test_mark_absent_hari_ini_window_sudah_lewat(admin_a):
    """Hari ini diproses hanya bila window check-in + toleransi sudah lewat."""
    from apps.reports.services import mark_absent
    from unittest.mock import patch as mock_patch

    # Simulasikan jam 23:00 WIB → window sudah lewat → hari ini diabsenkan.
    fake_now = datetime.now(_WIB_TZ).replace(hour=23, minute=0, second=0)
    with mock_patch("apps.reports.services.dj_timezone.now", return_value=fake_now):
        created = mark_absent(organization=admin_a.org, lookback_days=1)
    today = dj_timezone.localtime(dj_timezone.now(), _WIB_TZ).date()
    assert created == 3
    assert AttendanceDay.objects.filter(
        organization=admin_a.org, work_date=today,
        status=AttendanceDay.Status.ABSENT,
    ).count() == 3
