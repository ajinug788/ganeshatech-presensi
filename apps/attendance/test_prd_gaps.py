"""Tes PRD gaps: impor siswa (USER-03), izin/sakit (ATT-11),
penugasan pembina (USER-04), profil organisasi (TEN-06).
"""
import datetime
import io

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.attendance.models import (
    AttendanceDay,
    AttendanceLocation,
    LeaveRequest,
    SupervisorAssignment,
)
from apps.attendance.services import (
    apply_leave_approval,
    import_students,
    reject_leave,
    update_organization_profile,
)
from apps.audit.models import AuditLog
from apps.tenants.models import Membership, Organization

PASSWORD = "Str0ng-Passw0rd!"
Admin = get_user_model()

pytestmark = pytest.mark.django_db

CSV_HEADER = "student_number,full_name,group,email\n"


@pytest.fixture
def org_a():
    return Organization.objects.create(name="SMK A", slug="smk-a")


@pytest.fixture
def org_b():
    return Organization.objects.create(name="SMK B", slug="smk-b")


def login(client, email):
    client.post(reverse("accounts:login"), {"username": email, "password": PASSWORD})


def make_user(org, email, role):
    user = Admin.objects.create_user(email, PASSWORD)
    Membership.objects.create(organization=org, user=user, role=role)
    return user


@pytest.fixture
def admin_a(org_a):
    return make_user(org_a, "admin-a@example.com", "admin")


# ============================================================ USER-03 impor


def _csv_bytes(text):
    return text.encode("utf-8")


def test_import_success_and_audit(org_a, admin_a):
    data = _csv_bytes(
        CSV_HEADER + "2024001,Budi,kelas A,budi@ex.com\n2024002,Ani,kelas A,\n"
    )
    summary = import_students(
        organization=org_a, file_bytes=data, filename="siswa.csv", actor=admin_a
    )
    assert summary["created"] == 2
    assert summary["accounts_created"] == 1
    assert org_a.students.count() == 2
    log = AuditLog.objects.filter(action="students_imported").latest("created_at")
    assert log.metadata["created"] == 2
    assert "password" not in log.metadata


def test_import_duplicate_number_in_file_and_db(org_a, admin_a):
    org_a.students.create(student_number="2024001", full_name="Lama")
    data = _csv_bytes(
        CSV_HEADER + "2024001,Budi,\n2024001,Ani,\n2024002,Citra,\n"
    )
    summary = import_students(
        organization=org_a, file_bytes=data, filename="s.csv", actor=admin_a
    )
    assert summary["created"] == 1
    assert summary["skipped"] == 2
    assert len(summary["errors"]) == 2


def test_import_duplicate_email_platform_wide(org_a, org_b, admin_a):
    Admin.objects.create_user("taken@ex.com", PASSWORD)
    data = _csv_bytes(CSV_HEADER + "2024001,Budi,,taken@ex.com\n")
    summary = import_students(
        organization=org_a, file_bytes=data, filename="s.csv", actor=admin_a
    )
    assert summary["created"] == 0
    assert summary["skipped"] == 1
    assert any("terdaftar" in e["message"] for e in summary["errors"])


def test_import_bad_header_raises_nothing_created(org_a, admin_a):
    data = _csv_bytes("nim,nama\n2024001,Budi\n")
    with pytest.raises(ValueError):
        import_students(
            organization=org_a, file_bytes=data, filename="s.csv", actor=admin_a
        )
    assert org_a.students.count() == 0


def test_import_empty_rows_skipped(org_a, admin_a):
    data = _csv_bytes(CSV_HEADER + ",,\n2024001,Budi,\n")
    summary = import_students(
        organization=org_a, file_bytes=data, filename="s.csv", actor=admin_a
    )
    assert summary["created"] == 1
    assert summary["skipped"] == 1


def test_import_too_large_rejected(org_a, admin_a):
    data = b"x" * (1 * 1024 * 1024 + 1)
    with pytest.raises(ValueError):
        import_students(
            organization=org_a, file_bytes=data, filename="s.csv", actor=admin_a
        )


def test_import_view_role_gate_cross_tenant(org_a, org_b, admin_a):
    # admin org B tidak boleh impor ke org A (org aktif = org B).
    make_user(org_b, "admin-b@example.com", "admin")
    client = _client()
    login(client, "admin-b@example.com")
    url = reverse("attendance:student_import")
    resp = client.post(url, {"file": _fake_upload(_csv_bytes(CSV_HEADER))})
    # Hanya admin org aktif (B) — berhasil ke org B, bukan org A.
    assert resp.status_code in (302, 200)
    assert org_a.students.count() == 0


def _client():
    from django.test import Client

    return Client()


def _fake_upload(data, name="siswa.csv"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(name, data)


def test_import_view_admin_success(org_a, admin_a):
    client = _client()
    login(client, "admin-a@example.com")
    resp = client.post(
        reverse("attendance:student_import"),
        {"file": _fake_upload(_csv_bytes(CSV_HEADER + "2024001,Budi,\n"))},
    )
    assert resp.status_code == 302
    assert org_a.students.count() == 1


def test_import_view_siswa_forbidden(org_a):
    make_user(org_a, "siswa-a@example.com", "siswa")
    client = _client()
    login(client, "siswa-a@example.com")
    resp = client.post(
        reverse("attendance:student_import"),
        {"file": _fake_upload(_csv_bytes(CSV_HEADER))},
    )
    assert resp.status_code == 403


# ============================================================ ATT-11 izin


@pytest.fixture
def student_a(org_a):
    user = make_user(org_a, "student-leave@example.com", "siswa")
    return org_a.students.create(
        student_number="2024100", full_name="Siswa Izin", user=user
    )


@pytest.fixture
def location_a(org_a):
    return AttendanceLocation.objects.create(
        organization=org_a, name="Gedung A", latitude=-6.2, longitude=106.8
    )


def _leave(student, days_ahead=1, **kw):
    today = datetime.date.today()
    defaults = dict(
        organization=student.organization,
        student=student,
        kind="sakit",
        date_from=today + datetime.timedelta(days=days_ahead),
        date_to=today + datetime.timedelta(days=days_ahead),
        reason="Demam",
    )
    defaults.update(kw)
    return LeaveRequest.objects.create(**defaults)


def test_leave_approve_creates_excused_day_idempotent(org_a, student_a):
    leave = _leave(student_a)
    apply_leave_approval(leave_request=leave, actor=None)
    apply_leave_approval(leave_request=leave, actor=None)  # idempoten
    days = AttendanceDay.objects.filter(student=student_a)
    assert days.count() == 1
    assert days.first().status == AttendanceDay.Status.EXCUSED
    assert AuditLog.objects.filter(action="leave_approved").count() == 2


def test_leave_approve_does_not_overwrite_real_checkin(org_a, student_a):
    today = datetime.date.today()
    AttendanceDay.objects.create(
        organization=org_a, student=student_a, work_date=today,
        status=AttendanceDay.Status.PRESENT,
        check_in_at=datetime.datetime.now(tz=datetime.timezone.utc),
    )
    leave = _leave(student_a, days_ahead=0)
    apply_leave_approval(leave_request=leave, actor=None)
    day = AttendanceDay.objects.get(student=student_a, work_date=today)
    assert day.status == AttendanceDay.Status.PRESENT  # tidak ditimpa


def test_leave_reject_requires_note(org_a, student_a):
    leave = _leave(student_a)
    with pytest.raises(ValueError):
        reject_leave(leave_request=leave, actor=None, review_note="  ")
    leave.refresh_from_db()
    assert leave.status == LeaveRequest.Status.PENDING


def test_leave_reject_with_note_audited(org_a, student_a):
    leave = _leave(student_a)
    reject_leave(leave_request=leave, actor=None, review_note="Tidak lengkap")
    assert leave.status == LeaveRequest.Status.REJECTED
    assert AuditLog.objects.filter(action="leave_rejected").exists()


def test_leave_validation_dates_order(org_a, student_a):
    today = datetime.date.today()
    leave = LeaveRequest(
        organization=org_a, student=student_a, kind="izin",
        date_from=today, date_to=today - datetime.timedelta(days=1), reason="x",
    )
    with pytest.raises(Exception):
        leave.full_clean(exclude=["organization", "student"])


def test_leave_siswa_cannot_review(org_a, student_a):
    client = _client()
    login(client, "student-leave@example.com")
    leave = _leave(student_a)
    resp = client.post(
        reverse("attendance:leave_review_action", kwargs={"pk": leave.pk}),
        {"decision": "approve"},
    )
    assert resp.status_code == 403
    leave.refresh_from_db()
    assert leave.status == LeaveRequest.Status.PENDING


def test_leave_admin_review_via_view(org_a, student_a):
    make_user(org_a, "admin-leave@example.com", "admin")
    client = _client()
    login(client, "admin-leave@example.com")
    leave = _leave(student_a)
    resp = client.post(
        reverse("attendance:leave_review_action", kwargs={"pk": leave.pk}),
        {"decision": "approve"},
    )
    assert resp.status_code == 302
    leave.refresh_from_db()
    assert leave.status == LeaveRequest.Status.APPROVED


def test_leave_review_list_cross_tenant_404(org_a, org_b, student_a):
    make_user(org_b, "admin-b2@example.com", "admin")
    leave = _leave(student_a)
    client = _client()
    login(client, "admin-b2@example.com")
    resp = client.post(
        reverse("attendance:leave_review_action", kwargs={"pk": leave.pk}),
        {"decision": "approve"},
    )
    assert resp.status_code == 404


def test_leave_form_past_date_more_than_1_day_rejected(org_a, student_a):
    from apps.attendance.forms import LeaveRequestForm

    old = datetime.date.today() - datetime.timedelta(days=5)
    form = LeaveRequestForm(
        data={
            "kind": "sakit", "date_from": old.isoformat(),
            "date_to": old.isoformat(), "reason": "sakit",
        }
    )
    assert not form.is_valid()


def test_leave_form_valid(org_a, student_a):
    from apps.attendance.forms import LeaveRequestForm

    d = datetime.date.today() + datetime.timedelta(days=1)
    form = LeaveRequestForm(
        data={
            "kind": "sakit", "date_from": d.isoformat(),
            "date_to": d.isoformat(), "reason": "sakit",
        }
    )
    assert form.is_valid(), form.errors


# ============================================================ USER-04 pembina


def test_supervisor_assign_unassign_audit_unique(org_a, admin_a, location_a):
    pembina = make_user(org_a, "pembina-a@example.com", "pembina")
    membership = pembina.memberships.get(organization=org_a)
    from apps.attendance.services import assign_supervisor, unassign_supervisor

    assignment, created = assign_supervisor(
        organization=org_a, membership=membership, location=location_a, actor=admin_a
    )
    assert created
    # Assign ulang → tidak duplikat, tidak audit baru.
    _, created2 = assign_supervisor(
        organization=org_a, membership=membership, location=location_a, actor=admin_a
    )
    assert not created2
    assert SupervisorAssignment.objects.count() == 1
    assert AuditLog.objects.filter(action="supervisor_assigned").count() == 1
    unassign_supervisor(organization=org_a, assignment=assignment, actor=admin_a)
    assert SupervisorAssignment.objects.count() == 0
    assert AuditLog.objects.filter(action="supervisor_unassigned").count() == 1


def test_supervisor_only_pembina_role(org_a, admin_a, location_a):
    siswa = make_user(org_a, "siswa-supa@example.com", "siswa")
    membership = siswa.memberships.get(organization=org_a)
    from apps.attendance.services import assign_supervisor

    with pytest.raises(ValueError):
        assign_supervisor(
            organization=org_a, membership=membership,
            location=location_a, actor=admin_a,
        )


def test_supervisor_view_role_gate(org_a, location_a):
    make_user(org_a, "admin-supa@example.com", "admin")
    client = _client()
    login(client, "admin-supa@example.com")
    resp = client.get(reverse("attendance:supervisor_manage"))
    assert resp.status_code == 200


def test_supervisor_view_forbidden_for_siswa(org_a):
    make_user(org_a, "siswa-supa2@example.com", "siswa")
    client = _client()
    login(client, "siswa-supa2@example.com")
    resp = client.get(reverse("attendance:supervisor_manage"))
    assert resp.status_code == 403


def test_pembina_dashboard_sees_assigned_locations(org_a, location_a):
    pembina = make_user(org_a, "pembina-dash@example.com", "pembina")
    membership = pembina.memberships.get(organization=org_a)
    SupervisorAssignment.objects.create(
        organization=org_a, membership=membership, location=location_a
    )
    from apps.reports.views import build_pembina_context

    ctx = build_pembina_context(membership, org_a)
    assert location_a in list(ctx["assigned_locations"])


# ============================================================ TEN-06 profil


def test_org_profile_update_audit_changed_fields(org_a, admin_a):
    org, changed = update_organization_profile(
        organization=org_a, actor=admin_a, name="SMK A Baru",
        timezone="Asia/Makassar", allow_self_shift=True,
    )
    assert set(changed) == {"name", "timezone", "allow_self_shift"}
    log = AuditLog.objects.filter(action="organization_updated").latest("created_at")
    assert set(log.metadata["changed"]) == {"name", "timezone", "allow_self_shift"}


def test_org_profile_empty_name_rejected(org_a, admin_a):
    with pytest.raises(ValueError):
        update_organization_profile(
            organization=org_a, actor=admin_a, name="  "
        )


def test_org_profile_invalid_timezone_rejected(org_a, admin_a):
    with pytest.raises(ValueError):
        update_organization_profile(
            organization=org_a, actor=admin_a, timezone="Europe/Amsterdam"
        )


def test_org_profile_view_admin_can_edit(org_a):
    make_user(org_a, "admin-prof@example.com", "admin")
    client = _client()
    login(client, "admin-prof@example.com")
    url = reverse("tenants:organization_profile")
    assert client.get(url).status_code == 200
    resp = client.post(
        url,
        {
            "name": "SMK A Update",
            "timezone": "Asia/Jayapura",
            "allow_self_shift": "on",
        },
    )
    assert resp.status_code == 302
    org_a.refresh_from_db()
    assert org_a.name == "SMK A Update"
    assert org_a.timezone == "Asia/Jayapura"
    assert org_a.settings["allow_self_shift"] is True


def test_org_profile_view_pembina_cannot_edit(org_a):
    make_user(org_a, "pembina-prof@example.com", "pembina")
    client = _client()
    login(client, "pembina-prof@example.com")
    url = reverse("tenants:organization_profile")
    resp = client.get(url)
    assert resp.status_code == 200  # boleh lihat
    resp = client.post(url, {"name": "Hack", "timezone": "Asia/Jakarta"})
    assert resp.status_code in (200, 302)
    org_a.refresh_from_db()
    assert org_a.name != "Hack"


def test_org_profile_view_siswa_cannot_edit(org_a):
    make_user(org_a, "siswa-prof@example.com", "siswa")
    client = _client()
    login(client, "siswa-prof@example.com")
    url = reverse("tenants:organization_profile")
    resp = client.post(url, {"name": "Hack", "timezone": "Asia/Jakarta"})
    org_a.refresh_from_db()
    assert org_a.name != "Hack"
    assert not AuditLog.objects.filter(
        action="organization_updated", metadata__changed__name="Hack"
    ).exists()
