"""Tes fitur Manajemen Akun Siswa (AUTH-02) + Multi-Shift (engine & CRUD)."""
import datetime
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.attendance.models import (
    AttendanceDay,
    AttendanceLocation,
    AttendancePolicy,
    Shift,
    StudentProfile,
)
from apps.attendance.services import (
    AttendanceError,
    create_check_in,
)
from apps.tenants.models import Membership, Organization

PASSWORD = "Str0ng-Passw0rd!"
Admin = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def org_a():
    return Organization.objects.create(name="SMK A", slug="smk-a")


@pytest.fixture
def org_b():
    return Organization.objects.create(name="SMK B", slug="smk-b")


def make_membership(org, email, role):
    user = Admin.objects.create_user(email, PASSWORD)
    Membership.objects.create(organization=org, user=user, role=role)
    return user


def make_student(org, email, number="2024001", with_account=True):
    user = None
    if with_account:
        user = Admin.objects.create_user(email, PASSWORD)
        Membership.objects.create(
            organization=org, user=user, role=Membership.Role.SISWA
        )
    return org.students.create(
        student_number=number,
        full_name=f"Siswa {number}",
        user=user,
    )


def make_media(org):
    from apps.media_assets.models import MediaAsset

    return MediaAsset.objects.create(
        organization=org,
        storage_key="test/key.jpg",
        mime_type="image/jpeg",
        width=10, height=10, size_bytes=100, checksum="abc",
    )


def login(client, email):
    client.post(reverse("accounts:login"), {"username": email, "password": PASSWORD})


@pytest.fixture
def admin_a(org_a):
    return make_membership(org_a, "admin-a@example.com", "admin")


@pytest.fixture
def admin_b(org_b):
    return make_membership(org_b, "admin-b@example.com", "admin")


def make_policy(org, **kw):
    defaults = dict(
        days_active=[0, 1, 2, 3, 4, 5, 6],
        check_in_start="07:00",
        check_in_end="09:00",
        check_out_start="15:00",
        check_out_end="17:00",
        late_tolerance_min=15,
    )
    defaults.update(kw)
    return AttendancePolicy.objects.create(organization=org, **defaults)


def make_location(org, name="Gerbang", lat=-6.9, lng=107.6):
    return AttendanceLocation.objects.create(
        organization=org, name=name, latitude=lat, longitude=lng, radius_m=100
    )


def make_shift(org, name="Pagi", **kw):
    defaults = dict(
        check_in_start="06:00",
        check_in_end="07:00",
        check_out_start="13:00",
        check_out_end="14:00",
        days_active=[0, 1, 2, 3, 4, 5, 6],
        late_tolerance_min=15,
    )
    defaults.update(kw)
    return Shift.objects.create(organization=org, name=name, **defaults)


class FakePhoto:
    """Foto fake untuk create_check_in (mock _store_photo agar tidak file I/O)."""

    def read(self):
        return b"fake-jpeg"

    def seek(self, pos):
        return None


def checkin_now(student, **kw):
    """Panggil create_check_in dengan waktu & foto di-mock."""
    args = dict(
        student=student,
        user=student.user,
        photo=FakePhoto(),
        latitude=-6.9,
        longitude=107.6,
        accuracy=10,
        idempotency_key=kw.pop("key", "idem-1"),
    )
    args.update(kw)
    return args


# ================================================================ AUTH-02


class TestResetPassword:
    def test_admin_org_a_reset_ok_login_baru_lama_gagal(self, client, org_a, admin_a):
        student = make_student(org_a, "sis1@a.com")
        assert client.login(username="sis1@a.com", password=PASSWORD)
        client.logout()
        login(client, "admin-a@example.com")
        resp = client.post(
            reverse("attendance:student_reset_password", args=[student.pk])
        )
        assert resp.status_code == 200
        new_password = resp.context["one_time_password"]
        assert new_password  # ditampilkan sekali di context
        client.logout()
        assert client.login(username="sis1@a.com", password=new_password)
        client.logout()
        assert not client.login(username="sis1@a.com", password=PASSWORD)

    def test_admin_org_b_lintas_tenant_404(self, client, org_a, org_b, admin_a, admin_b):
        student = make_student(org_a, "sis2@a.com")
        login(client, "admin-b@example.com")
        resp = client.post(
            reverse("attendance:student_reset_password", args=[student.pk])
        )
        assert resp.status_code == 404

    def test_audit_tanpa_password(self, client, org_a, admin_a):
        student = make_student(org_a, "sis3@a.com")
        login(client, "admin-a@example.com")
        client.post(reverse("attendance:student_reset_password", args=[student.pk]))
        log = AuditLog.objects.filter(
            action="student_password_reset", organization=org_a
        ).latest("created_at")
        raw = str(log.metadata)
        assert "password" not in raw.lower().replace(
            "student_password_reset", ""
        ) or log.metadata == {}


class TestNonaktifAkun:
    def test_nonaktif_login_ditolak_data_absen_tetap_reaktif_ok(
        self, client, org_a, admin_a
    ):
        student = make_student(org_a, "sis4@a.com")
        AttendanceDay.objects.create(
            organization=org_a, student=student,
            work_date=datetime.date(2026, 10, 1), status=AttendanceDay.Status.PRESENT,
        )
        login(client, "admin-a@example.com")
        resp = client.post(
            reverse("attendance:student_account_active", args=[student.pk]),
            {"active": "off"},
        )
        assert resp.status_code == 302
        student.user.refresh_from_db()
        assert not student.user.is_active
        # Login ditolak
        client.logout()
        assert not client.login(username="sis4@a.com", password=PASSWORD)
        # Rekam jejak absen tidak dihapus
        assert AttendanceDay.objects.filter(student=student).count() == 1
        # Reaktif
        client.login(username="admin-a@example.com", password=PASSWORD)
        client.post(
            reverse("attendance:student_account_active", args=[student.pk]),
            {"active": "on"},
        )
        student.user.refresh_from_db()
        assert student.user.is_active
        assert AuditLog.objects.filter(
            action="student_account_deactivated", organization=org_a
        ).exists()
        assert AuditLog.objects.filter(
            action="student_account_activated", organization=org_a
        ).exists()


class TestUbahEmail:
    def test_email_duplikat_ditolak(self, client, org_a, admin_a):
        make_student(org_a, "taken@a.com", number="2024010")
        student = make_student(org_a, "sis5@a.com", number="2024005")
        login(client, "admin-a@example.com")
        resp = client.post(
            reverse("attendance:student_change_email", args=[student.pk]),
            {"email": "taken@a.com"},
        )
        assert resp.status_code == 200
        student.user.refresh_from_db()
        assert student.user.email == "sis5@a.com"

    def test_email_baru_ok_audit(self, client, org_a, admin_a):
        student = make_student(org_a, "sis6@a.com")
        login(client, "admin-a@example.com")
        resp = client.post(
            reverse("attendance:student_change_email", args=[student.pk]),
            {"email": "baru@a.com"},
        )
        assert resp.status_code == 302
        student.user.refresh_from_db()
        assert student.user.email == "baru@a.com"
        assert AuditLog.objects.filter(
            action="student_email_changed", organization=org_a
        ).exists()


# ================================================================ Shift CRUD


class TestShiftCRUD:
    def test_role_gate_pembina_ditolak(self, client, org_a):
        make_membership(org_a, "pemb@a.com", "pembina")
        login(client, "pemb@a.com")
        resp = client.get(reverse("attendance:shift_list"))
        assert resp.status_code == 403

    def test_lintas_tenant_404(self, client, org_a, org_b, admin_a, admin_b):
        shift_b = make_shift(org_b)
        login(client, "admin-a@example.com")
        resp = client.get(
            reverse("attendance:shift_update", args=[shift_b.pk])
        )
        assert resp.status_code == 404
        resp = client.post(
            reverse("attendance:shift_delete", args=[shift_b.pk]), {}
        )
        assert resp.status_code == 404

    def test_validasi_jam(self, org_a, admin_a):
        shift = make_shift(org_a, check_in_start="09:00", check_in_end="08:00")
        with pytest.raises(Exception):
            shift.full_clean()

    def test_nama_duplikat_per_org(self, org_a, admin_a):
        make_shift(org_a, name="Pagi")
        dup = Shift(
            organization=org_a, name="Pagi",
            check_in_start="06:00", check_in_end="07:00",
            check_out_start="13:00", check_out_end="14:00",
            days_active=[0],
        )
        with pytest.raises(Exception):
            dup.full_clean()

    def test_create_update_delete_audit(self, client, org_a, admin_a):
        login(client, "admin-a@example.com")
        resp = client.post(
            reverse("attendance:shift_create"),
            {
                "name": "Siang",
                "days_active": ["0", "1"],
                "check_in_start": "12:00",
                "check_in_end": "13:00",
                "check_out_start": "18:00",
                "check_out_end": "19:00",
                "late_tolerance_min": 10,
            },
        )
        assert resp.status_code == 302
        shift = Shift.objects.get(organization=org_a, name="Siang")
        assert AuditLog.objects.filter(action="shift_created").exists()
        # Soft delete
        resp = client.post(reverse("attendance:shift_delete", args=[shift.pk]), {})
        assert resp.status_code == 302
        shift.refresh_from_db()
        assert not shift.is_active
        assert AuditLog.objects.filter(action="shift_deleted").exists()


# ================================================================ Penetapan


class TestPenetapanShift:
    def test_bulk_per_grup(self, client, org_a, admin_a):
        make_shift(org_a)
        for i in range(3):
            s = make_student(org_a, f"g{i}@a.com", number=f"20250{i}")
            s.group = "XII RPL"
            s.save()
        login(client, "admin-a@example.com")
        shift = org_a.shifts.first()
        resp = client.post(
            reverse("attendance:student_group_shift"),
            {"group": "XII RPL", "shift": str(shift.pk)},
        )
        assert resp.status_code == 302
        assert org_a.students.filter(group="XII RPL", shift=shift).count() == 3
        assert AuditLog.objects.filter(
            action="student_shift_assigned", organization=org_a
        ).count() == 3

    def test_per_siswa(self, client, org_a, admin_a):
        student = make_student(org_a, "ps@a.com")
        shift = make_shift(org_a, name="Sore")
        login(client, "admin-a@example.com")
        resp = client.post(
            reverse("attendance:student_shift", args=[student.pk]),
            {"shift": str(shift.pk)},
        )
        assert resp.status_code == 302
        student.refresh_from_db()
        assert student.shift == shift


# ================================================================ Engine


class TestEngineShift:
    def _patch_photo(self, m_photo, org):
        asset = make_media(org)
        m_photo.return_value = asset

    @mock.patch("apps.attendance.services._store_photo")
    @mock.patch("apps.attendance.services._now_wib")
    def test_checkin_shift_sampai_akhir_window_checkout_dihitung_terlambat(
        self, m_now, m_photo, org_a, admin_a
    ):
        self._patch_photo(m_photo, org_a)
        make_location(org_a)
        make_policy(org_a)  # fallback, window 07:00-09:00
        shift = make_shift(org_a)  # window check-in 06:00-07:00 +15 toleransi
        student = make_student(org_a, "eng1@a.com")
        student.shift = shift
        student.save()
        # 06:30 WIB → di window shift pagi, di luar window policy → sukses.
        m_now.return_value = datetime.datetime(
            2026, 10, 12, 6, 30, tzinfo=datetime.timezone(datetime.timedelta(hours=7))
        )
        day, created, _ = create_check_in(**checkin_now(student))
        assert created
        # 08:00 WIB → masih sebelum check_out_end (14:00), jadi diterima;
        # terlambat 60 menit dihitung dari check_in_end (07:00), tanpa grace gate.
        m_now.return_value = datetime.datetime(
            2026, 10, 13, 8, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=7))
        )
        day, created, _ = create_check_in(**checkin_now(student, key="idem-2"))
        assert created
        assert day.status == AttendanceDay.Status.LATE
        assert day.late_minutes == 60

    @mock.patch("apps.attendance.services._store_photo")
    @mock.patch("apps.attendance.services._now_wib")
    def test_siswa_tanpa_shift_fallback_policy(self, m_now, m_photo, org_a):
        self._patch_photo(m_photo, org_a)
        make_location(org_a)
        make_policy(org_a)
        student = make_student(org_a, "eng2@a.com")
        assert student.shift is None
        m_now.return_value = datetime.datetime(
            2026, 10, 12, 8, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=7))
        )
        day, created, _ = create_check_in(**checkin_now(student))
        assert created

    @mock.patch("apps.attendance.services._store_photo")
    @mock.patch("apps.attendance.services._now_wib")
    def test_lokasi_shift_dibatasi(self, m_now, m_photo, org_a):
        self._patch_photo(m_photo, org_a)
        lok_jauh = make_location(org_a, name="Jauh", lat=-6.95, lng=107.7)
        make_policy(org_a)
        shift = make_shift(org_a)
        shift.locations.add(lok_jauh)
        student = make_student(org_a, "eng3@a.com")
        student.shift = shift
        student.save()
        m_now.return_value = datetime.datetime(
            2026, 10, 12, 6, 30, tzinfo=datetime.timezone(datetime.timedelta(hours=7))
        )
        # Absen di koordinat lokasi lain (dekat Gerbang, bukan Jauh) → geofence tolak.
        with pytest.raises(AttendanceError) as exc:
            create_check_in(**checkin_now(student))
        assert exc.value.code == "OUTSIDE_GEOFENCE"

    @mock.patch("apps.attendance.services._store_photo")
    @mock.patch("apps.attendance.services._now_wib")
    def test_shift_nonaktif_fallback_ke_policy(self, m_now, m_photo, org_a):
        self._patch_photo(m_photo, org_a)
        make_location(org_a)
        make_policy(org_a)  # 07:00-09:00
        shift = make_shift(org_a, is_active=False)  # 06:00-07:00
        student = make_student(org_a, "eng4@a.com")
        student.shift = shift
        student.save()
        m_now.return_value = datetime.datetime(
            2026, 10, 12, 8, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=7))
        )
        day, created, _ = create_check_in(**checkin_now(student))
        # 08:00 di luar window shift (nonaktif) tapi dalam policy → sukses (fallback).
        assert created


# ================================================================ Self-shift


class TestSelfShift:
    def test_off_403(self, client, org_a):
        make_shift(org_a)
        make_policy(org_a)
        make_student(org_a, "self1@a.com")
        login(client, "self1@a.com")
        resp = client.get(reverse("attendance:shift_self_select"))
        assert resp.status_code == 403

    def test_on_bisa_pilih_shift_aktif_audit(self, client, org_a):
        make_policy(org_a)
        shift = make_shift(org_a, name="Malam")
        org_a.settings["allow_self_shift"] = True
        org_a.save()
        student = make_student(org_a, "self2@a.com")
        login(client, "self2@a.com")
        resp = client.post(
            reverse("attendance:shift_self_select"), {"shift": str(shift.pk)}
        )
        assert resp.status_code == 302
        student.refresh_from_db()
        assert student.shift == shift
        assert AuditLog.objects.filter(action="student_self_shift").exists()

    def test_sudah_punya_shift_ditolak(self, client, org_a):
        make_policy(org_a)
        s1 = make_shift(org_a, name="Malam")
        s2 = make_shift(org_a, name="Siang")
        org_a.settings["allow_self_shift"] = True
        org_a.save()
        student = make_student(org_a, "self3@a.com")
        student.shift = s1
        student.save()
        login(client, "self3@a.com")
        resp = client.post(
            reverse("attendance:shift_self_select"), {"shift": str(s2.pk)}
        )
        assert resp.status_code == 200
        student.refresh_from_db()
        assert student.shift == s1
