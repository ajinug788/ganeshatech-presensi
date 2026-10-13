"""Tes gap dashboard siswa: shift tampil/fallback, kartu izin,
self-shift, label 'Dikoreksi admin' + peringatan attempt rejected,
dan media id di API history.
"""
import datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.attendance.models import (
    AttendanceAttempt,
    AttendanceDay,
    AttendancePolicy,
    LeaveRequest,
    Shift,
)
from apps.tenants.models import Membership, Organization

PASSWORD = "Str0ng-Passw0rd!"
Admin = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def org_a():
    return Organization.objects.create(name="SMK G1", slug="smk-g1")


def make_student(org, email, number="2024001"):
    user = Admin.objects.create_user(email, PASSWORD)
    Membership.objects.create(
        organization=org, user=user, role=Membership.Role.SISWA
    )
    return org.students.create(
        student_number=number, full_name=f"Siswa {number}", user=user
    )


def make_policy(org):
    return AttendancePolicy.objects.create(
        organization=org,
        days_active=[0, 1, 2, 3, 4, 5, 6],
        check_in_start="07:00",
        check_in_end="09:00",
        check_out_start="15:00",
        check_out_end="17:00",
        late_tolerance_min=15,
    )


def make_shift(org, name="Pagi", **kw):
    defaults = dict(
        check_in_start="06:00",
        check_in_end="07:00",
        check_out_start="13:00",
        check_out_end="14:00",
        days_active=[0, 1, 2, 3, 4, 5, 6],
        late_tolerance_min=10,
    )
    defaults.update(kw)
    return Shift.objects.create(organization=org, name=name, **defaults)


def login(client, email):
    client.post(reverse("accounts:login"), {"username": email, "password": PASSWORD})


def get_dashboard(client):
    resp = client.get(reverse("tenants:dashboard_siswa"))
    assert resp.status_code == 200
    return resp.context


# ================================================== (1) shift tampil / fallback

def test_shift_siswa_tampil_bukan_policy(org_a, client):
    make_policy(org_a)
    shift = make_shift(org_a, name="Shift Pagi Khusus")
    student = make_student(org_a, "shift1@g1.com")
    student.shift = shift
    student.save()
    login(client, "shift1@g1.com")
    ctx = get_dashboard(client)
    assert ctx["shift_label"] == "Shift Pagi Khusus"
    # dari shift (06:00), bukan policy (07:00)
    assert ctx["policy_check_in"] == "06:00"
    assert ctx["policy_check_out"] == "13:00"
    assert ctx["policy_tolerance"] == 10
    content = client.get(reverse("tenants:dashboard_siswa")).content.decode()
    assert "Shift:</span> <strong>Shift Pagi Khusus</strong>" in content


def test_fallback_policy_bila_shift_null(org_a, client):
    make_policy(org_a)
    make_shift(org_a)
    make_student(org_a, "shift2@g1.com")
    login(client, "shift2@g1.com")
    ctx = get_dashboard(client)
    assert ctx["shift_label"] is None
    assert ctx["policy_check_in"] == "07:00"
    assert ctx["policy_tolerance"] == 15


# ================================================== (2) kartu izin + ringkasan

def test_kartu_izin_dan_ringkasan_pengajuan(org_a, client):
    student = make_student(org_a, "izin1@g1.com")
    today = datetime.date.today()
    LeaveRequest.objects.create(
        organization=org_a, student=student, kind="sakit",
        date_from=today, date_to=today, reason="Demam", status="pending",
    )
    LeaveRequest.objects.create(
        organization=org_a, student=student, kind="izin",
        date_from=today, date_to=today, reason="Acara keluarga", status="approved",
    )
    login(client, "izin1@g1.com")
    resp = client.get(reverse("tenants:dashboard_siswa"))
    content = resp.content.decode()
    assert reverse("attendance:leave_request_create") in content
    assert "Izin &amp; Sakit" in content
    assert "Menunggu" in content
    assert "Disetujui" in content
    ctx = resp.context
    assert len(ctx["my_leave_requests"]) == 2


# ================================================== (3) kartu pilih shift sendiri

def test_self_shift_kartu_muncul_dan_post_bekerja(org_a, client):
    shift = make_shift(org_a, name="Malam")
    org_a.settings["allow_self_shift"] = True
    org_a.save()
    make_student(org_a, "self1@g1.com")
    login(client, "self1@g1.com")
    ctx = get_dashboard(client)
    assert ctx["show_self_shift"] is True
    assert shift in ctx["self_shift_choices"]
    resp = client.post(
        reverse("attendance:shift_self_select"), {"shift": str(shift.pk)}
    )
    assert resp.status_code == 302
    student = org_a.students.get(student_number="2024001")
    student.refresh_from_db()
    assert student.shift == shift
    assert AuditLog.objects.filter(action="student_self_shift").exists()


def test_self_shift_kartu_tidak_muncul_bila_setting_false(org_a, client):
    make_shift(org_a)
    make_student(org_a, "self2@g1.com")
    login(client, "self2@g1.com")
    ctx = get_dashboard(client)
    assert ctx["show_self_shift"] is False
    assert ctx["self_shift_choices"] == []


def test_self_shift_kartu_tidak_muncul_bila_sudah_punya_shift(org_a, client):
    shift = make_shift(org_a)
    org_a.settings["allow_self_shift"] = True
    org_a.save()
    student = make_student(org_a, "self3@g1.com")
    student.shift = shift
    student.save()
    login(client, "self3@g1.com")
    ctx = get_dashboard(client)
    assert ctx["show_self_shift"] is False
    assert ctx["self_shift_choices"] == []


# ================================================== (4) koreksi + attempt rejected

def test_label_dikoreksi_admin_muncul(org_a, client):
    student = make_student(org_a, "korek1@g1.com")
    today = datetime.date.today()
    day = AttendanceDay.objects.create(
        organization=org_a, student=student, work_date=today, status="late",
        late_minutes=20,
        check_in_at=datetime.datetime.now(datetime.timezone.utc),
    )
    AuditLog.objects.create(
        organization=org_a,
        action="attendance_corrected",
        object_type="attendance.AttendanceDay",
        object_id=str(day.pk),
    )
    login(client, "korek1@g1.com")
    content = client.get(reverse("tenants:dashboard_siswa")).content.decode()
    assert "Dikoreksi admin" in content
    ctx = client.get(reverse("tenants:dashboard_siswa")).context
    assert all(d.was_corrected for d in ctx["recent_days"])


def test_peringatan_attempt_rejected(org_a, client):
    student = make_student(org_a, "rej1@g1.com")
    AttendanceAttempt.objects.create(
        organization=org_a, student=student,
        kind="check_in", idempotency_key="k1", payload_hash="h" * 64,
        outcome=AttendanceAttempt.Outcome.REJECTED, error_code="OUT_OF_RADIUS",
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    login(client, "rej1@g1.com")
    content = client.get(reverse("tenants:dashboard_siswa")).content.decode()
    assert "Ada percobaan absen perlu perhatian" in content
    assert "OUT_OF_RADIUS" in content


def test_tanpa_rejected_tidak_ada_peringatan(org_a, client):
    make_student(org_a, "rej2@g1.com")
    login(client, "rej2@g1.com")
    content = client.get(reverse("tenants:dashboard_siswa")).content.decode()
    assert "Ada percobaan absen perlu perhatian" not in content


# ================================================== (5) media id di API history

def test_history_api_mengembalikan_media_id(org_a, client):
    from apps.media_assets.models import MediaAsset

    student = make_student(org_a, "foto1@g1.com")
    media = MediaAsset.objects.create(
        organization=org_a,
        storage_key="test/foto1.jpg",
        mime_type="image/jpeg",
        checksum="a" * 64,
    )
    AttendanceDay.objects.create(
        organization=org_a, student=student,
        work_date=datetime.date.today(), status="present",
        check_in_at=datetime.datetime.now(datetime.timezone.utc),
        check_in_media=media,
    )
    login(client, "foto1@g1.com")
    resp = client.get(reverse("api_attendance:history"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    row = data["results"][0]
    assert row["check_in_media_id"] == str(media.pk)
    assert row["check_out_media_id"] is None
