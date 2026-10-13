"""Tes hapus permanen pengajuan izin — hanya admin, pending/rejected saja."""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.attendance.models import LeaveRequest
from apps.attendance.services import delete_leave
from apps.audit.models import AuditLog
from apps.tenants.models import Membership, Organization

PASSWORD = "Str0ng-Passw0rd!"
Admin = get_user_model()


def make_user(org, email, role):
    user = Admin.objects.create_user(email, PASSWORD)
    Membership.objects.create(organization=org, user=user, role=role)
    return user


@pytest.fixture
def org_a():
    return Organization.objects.create(name="SMK Hapus", slug="smk-hapus")


@pytest.fixture
def admin_a(org_a):
    return make_user(org_a, "admin-hapus@example.com", "admin")


@pytest.fixture
def pembina_a(org_a):
    return make_user(org_a, "pembina-hapus@example.com", "pembina")


@pytest.fixture
def student_a(org_a):
    user = make_user(org_a, "siswa-hapus@example.com", "siswa")
    return org_a.students.create(
        student_number="2024902", full_name="Siswa Hapus", user=user
    )


def _make_leave(student, status=LeaveRequest.Status.PENDING):
    today = datetime.date.today()
    return LeaveRequest.objects.create(
        organization=student.organization,
        student=student,
        kind="izin",
        date_from=today,
        date_to=today,
        reason="tes hapus",
        status=status,
    )


pytestmark = pytest.mark.django_db


def test_delete_pending_ok(org_a, admin_a, student_a):
    leave = _make_leave(student_a)
    info = delete_leave(leave_request=leave, actor=admin_a)
    assert info["student_number"] == "2024902"
    assert not LeaveRequest.objects.filter(pk=leave.pk).exists()
    assert AuditLog.objects.filter(action="leave_deleted").exists()


def test_delete_approved_rejected(org_a, admin_a, student_a):
    leave = _make_leave(student_a, status=LeaveRequest.Status.APPROVED)
    with pytest.raises(ValueError):
        delete_leave(leave_request=leave, actor=admin_a)
    assert LeaveRequest.objects.filter(pk=leave.pk).exists()


def test_admin_can_delete_via_view(client, admin_a, student_a):
    leave = _make_leave(student_a)
    client.force_login(admin_a)
    resp = client.post(reverse("attendance:leave_delete", args=[leave.pk]))
    assert resp.status_code == 302
    assert not LeaveRequest.objects.filter(pk=leave.pk).exists()


def test_pembina_cannot_delete(client, pembina_a, student_a):
    leave = _make_leave(student_a)
    client.force_login(pembina_a)
    resp = client.post(reverse("attendance:leave_delete", args=[leave.pk]))
    assert resp.status_code in (302, 403)
    assert LeaveRequest.objects.filter(pk=leave.pk).exists()
