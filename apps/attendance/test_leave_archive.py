"""Tes arsip (soft-delete) pengajuan izin — hanya admin, pending/rejected saja."""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.attendance.models import LeaveRequest
from apps.attendance.services import archive_leave
from apps.tenants.models import Membership, Organization

PASSWORD = "Str0ng-Passw0rd!"
Admin = get_user_model()


def make_user(org, email, role):
    user = Admin.objects.create_user(email, PASSWORD)
    Membership.objects.create(organization=org, user=user, role=role)
    return user


@pytest.fixture
def org_a():
    return Organization.objects.create(name="SMK Arsip", slug="smk-arsip")


@pytest.fixture
def admin_a(org_a):
    return make_user(org_a, "admin-arsip@example.com", "admin")


@pytest.fixture
def pembina_a(org_a):
    return make_user(org_a, "pembina-arsip@example.com", "pembina")


@pytest.fixture
def student_a(org_a):
    user = make_user(org_a, "siswa-arsip@example.com", "siswa")
    return org_a.students.create(
        student_number="2024901", full_name="Siswa Arsip", user=user
    )


def _make_leave(student, status=LeaveRequest.Status.PENDING):
    today = datetime.date.today()
    return LeaveRequest.objects.create(
        organization=student.organization,
        student=student,
        kind="izin",
        date_from=today,
        date_to=today,
        reason="tes arsip",
        status=status,
    )


pytestmark = pytest.mark.django_db


def test_archive_pending_ok(org_a, admin_a, student_a):
    leave = _make_leave(student_a)
    out = archive_leave(leave_request=leave, actor=admin_a)
    out.refresh_from_db()
    assert out.archived_at is not None
    assert out.archived_by == admin_a


def test_archive_approved_rejected(org_a, admin_a, student_a):
    leave = _make_leave(student_a, status=LeaveRequest.Status.APPROVED)
    with pytest.raises(ValueError):
        archive_leave(leave_request=leave, actor=admin_a)


def test_admin_can_archive_via_view(client, admin_a, student_a):
    leave = _make_leave(student_a)
    client.force_login(admin_a)
    resp = client.post(reverse("attendance:leave_archive", args=[leave.pk]))
    assert resp.status_code == 302
    leave.refresh_from_db()
    assert leave.archived_at is not None


def test_pembina_cannot_archive(client, pembina_a, student_a):
    leave = _make_leave(student_a)
    client.force_login(pembina_a)
    resp = client.post(reverse("attendance:leave_archive", args=[leave.pk]))
    assert resp.status_code in (302, 403)
    leave.refresh_from_db()
    assert leave.archived_at is None


def test_archived_hidden_from_review_list(client, admin_a, student_a):
    leave = _make_leave(student_a)
    client.force_login(admin_a)
    archive_leave(leave_request=leave, actor=admin_a)
    resp = client.get(reverse("attendance:leave_review_list"))
    assert leave.pk not in [l.pk for l in resp.context["object_list"]]
