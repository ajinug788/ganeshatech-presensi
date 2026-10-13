"""Regresi: siswa dapat melihat FOTO ABSEN dirinya sendiri via /photos/<uuid>/.

Bug produksi 13 Okt 2026: gating siswa di MediaAssetView hanya mengizinkan
profile_photo milik sendiri — tombol "Lihat foto" di riwayat selalu 404.
"""
import pytest
from django.urls import reverse

from apps.attendance.models import AttendanceDay
from apps.media_assets.models import MediaAsset
from apps.tenants.models import Organization

pytestmark = pytest.mark.django_db


@pytest.fixture
def org_a():
    return Organization.objects.create(name="SMK G1", slug="smk-g1")


def _make_student(org, email, number="2024001"):
    from apps.accounts.models import User as Admin
    from apps.tenants.models import Membership

    user = Admin.objects.create_user(email, "Str0ng-Passw0rd!")
    Membership.objects.create(
        organization=org, user=user, role=Membership.Role.SISWA
    )
    return org.students.create(
        student_number=number, full_name=f"Siswa {number}", user=user
    )


def _make_asset(org):
    from django.conf import settings

    from apps.media_assets.models import MediaAsset

    key = f"private_media/test/{org.slug}/absen-foto.jpg"
    physical = settings.MEDIA_ROOT / key
    physical.parent.mkdir(parents=True, exist_ok=True)
    physical.write_bytes(b"\xff\xd8\xff\xe0fakejpg")
    return MediaAsset.objects.create(
        organization=org,
        storage_key=key,
        mime_type="image/jpeg",
        size_bytes=8,
        checksum="a" * 64,
    )


def test_siswa_bisa_lihat_foto_absen_sendiri(org_a, client):
    student = _make_student(org_a, "fotosiswa@g1.com")
    asset = _make_asset(org_a)
    day = AttendanceDay.objects.create(
        organization=org_a,
        student=student,
        work_date="2026-10-13",
        status="present",
        check_in_media=asset,
    )
    client.force_login(student.user)
    resp = client.get(reverse("photos:photo", args=[asset.pk]))
    assert resp.status_code == 200


def test_siswa_tetap_404_foto_absen_siswa_lain(org_a, client):
    owner = _make_student(org_a, "pemilik@g1.com")
    other = _make_student(org_a, "lain@g1.com", number="2024002")
    asset = _make_asset(org_a)
    AttendanceDay.objects.create(
        organization=org_a,
        student=owner,
        work_date="2026-10-13",
        status="present",
        check_in_media=asset,
    )
    client.force_login(other.user)
    resp = client.get(reverse("photos:photo", args=[asset.pk]))
    assert resp.status_code == 404


def test_siswa_foto_profil_sendiri_masih_200(org_a, client):
    student = _make_student(org_a, "profilfoto@g1.com")
    asset = _make_asset(org_a)
    student.profile_photo = asset
    student.save(update_fields=["profile_photo"])
    client.force_login(student.user)
    resp = client.get(reverse("photos:photo", args=[asset.pk]))
    assert resp.status_code == 200
