"""Tes model + service audit (Tahap 2)."""
import pytest
from django.contrib.auth import get_user_model

from apps.audit.models import AuditLog
from apps.audit.services import catat_audit
from apps.tenants.models import Organization

pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.create(name="SMK B", slug="smk-b")


def test_catat_audit_membuat_record(org):
    user = get_user_model().objects.create_user("a@example.com", "Str0ng-Passw0rd!")
    log = catat_audit(
        action="membership.create",
        object_type="Membership",
        object_id="abc",
        organization=org,
        actor=user,
        reason="onboarding",
        metadata={"role": "siswa"},
    )
    assert AuditLog.objects.count() == 1
    assert log.organization == org
    assert log.action == "membership.create"


def test_metadata_password_diredaksi(org):
    log = catat_audit(
        action="user.create",
        object_type="User",
        metadata={"password": "rahasia", "email": "x@example.com", "user_token": "tok"},
    )
    assert log.metadata["password"] == "[diredaksi]"
    assert log.metadata["user_token"] == "[diredaksi]"
    assert log.metadata["email"] == "x@example.com"


def test_metadata_koordinat_diredaksi():
    log = catat_audit(
        action="attendance.attempt",
        object_type="AttendanceAttempt",
        metadata={"latitude": -6.2, "longitude": 106.8, "result": "out_of_radius"},
    )
    assert log.metadata["latitude"] == "[diredaksi]"
    assert log.metadata["longitude"] == "[diredaksi]"
    assert log.metadata["result"] == "out_of_radius"


def test_auditlog_append_only_tidak_bisa_diedit(org):
    log = catat_audit(action="t", object_type="X")
    with pytest.raises(ValueError):
        log.action = "ubah"
        log.save()
    with pytest.raises(ValueError):
        log.delete()
