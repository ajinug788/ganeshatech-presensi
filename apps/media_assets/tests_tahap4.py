"""Tes Tahap 4 — Media Pipeline (TDIP v1.2 §11, §16 Tahap 4).

- Normalisasi: PNG besar → JPEG 1280px, EXIF dihapus, checksum konsisten.
- Penolakan: SVG, gambar korup, ukuran > MEDIA_MAX_UPLOAD_MB, pixel ekstrem.
- Endpoint foto: admin org A lihat foto org A; admin org B → 404;
  anonim → redirect login; file di private_media, tidak dilayani publik.
- Cleanup yatim: dry-run dan real.
Foto uji dibuat via Pillow (tanpa binari commit).
"""
import hashlib
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from apps.media_assets.models import MediaAsset
from apps.media_assets.services import (
    INVALID_PHOTO,
    PHOTO_REQUIRED,
    PHOTO_TOO_LARGE,
    file_exists,
    generate_storage_key,
    normalize_image,
    private_media_dir,
    simpan_file,
)
from apps.media_assets.management.commands.cleanup_media import cleanup_media
from apps.tenants.models import Membership, Organization

PASSWORD = "Str0ng-Passw0rd!"
pytestmark = pytest.mark.django_db


# --------------------------------------------------------------- fixtures

@pytest.fixture
def org_a():
    return Organization.objects.create(name="SMK A", slug="smk-a")


@pytest.fixture
def org_b():
    return Organization.objects.create(name="SMK B", slug="smk-b")


def make_admin(org, email="admin@example.com", role="admin"):
    user = get_user_model().objects.create_user(email, PASSWORD)
    Membership.objects.create(organization=org, user=user, role=role)
    return user


def login_org(client, org, email, role="admin"):
    user = get_user_model().objects.create_user(email, PASSWORD)
    Membership.objects.create(organization=org, user=user, role=role)
    client.post(reverse("accounts:login"), {"username": email, "password": PASSWORD})
    return user


def make_jpeg(size=(2000, 1000), with_exif=False):
    """Generate JPEG uji via Pillow, di memori."""
    from PIL import Image

    img = Image.new("RGB", size, color=(120, 30, 200))
    kwargs = {"format": "JPEG", "quality": 90}
    buf = BytesIO()
    img.save(buf, **kwargs)
    return buf.getvalue()


def make_png(size=(2000, 1000)):
    from PIL import Image

    img = Image.new("RGB", size, color=(10, 200, 30))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_asset(org, user=None):
    """Asset + file nyata di private_media (dari JPEG uji)."""
    content = make_jpeg(size=(800, 600))
    key = generate_storage_key()
    simpan_file(key, content)
    return MediaAsset.objects.create(
        organization=org,
        storage_key=key,
        mime_type="image/jpeg",
        width=800,
        height=600,
        size_bytes=len(content),
        checksum=hashlib.sha256(content).hexdigest(),
        uploaded_by=user,
    )


# --------------------------------------------------------------- normalisasi


def test_normalisasi_png_besar_ke_jpeg_1280():
    png = make_png(size=(2560, 1600))
    upload = SimpleUploadedFile("t.png", png, content_type="image/png")
    result = normalize_image(upload)
    assert result["mime_type"] == "image/jpeg"
    assert max(result["width"], result["height"]) == 1280
    # Konsistensi checksum: konten sama → checksum sama.
    assert (
        result["checksum"]
        == hashlib.sha256(result["content"]).hexdigest()
    )


def test_normalisasi_jpeg_kecil_tidak_diresize():
    upload = SimpleUploadedFile("t.jpg", make_jpeg(size=(640, 480)))
    result = normalize_image(upload)
    assert (result["width"], result["height"]) == (640, 480)


def test_normalisasi_menghapus_exif():
    # Buat JPEG dengan EXIF (Pillow murni, tanpa piexif).
    from PIL import Image

    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    exif = img.getexif()
    exif[0x010F] = "TestCamera"  # Make tag
    buf = BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    raw_with_exif = buf.getvalue()
    assert b"TestCamera" in raw_with_exif  # EXIF benar-benar tertanam

    upload = SimpleUploadedFile("t.jpg", raw_with_exif, content_type="image/jpeg")
    result = normalize_image(upload)
    assert b"TestCamera" not in result["content"]  # EXIF hilang di output


def test_tolak_svg():
    svg = b"<svg xmlns='http://www.w3.org/2000/svg'><rect width='10' height='10'/></svg>"
    upload = SimpleUploadedFile("t.svg", svg, content_type="image/svg+xml")
    with pytest.raises(ValueError) as exc:
        normalize_image(upload)
    assert str(exc.value) == INVALID_PHOTO


def test_tolak_svg_berkedok_jpg():
    svg = b"<svg xmlns='http://www.w3.org/2000/svg'><rect width='10' height='10'/></svg>"
    upload = SimpleUploadedFile("t.jpg", svg, content_type="image/jpeg")
    with pytest.raises(ValueError) as exc:
        normalize_image(upload)
    assert str(exc.value) == INVALID_PHOTO


def test_tolak_file_korup():
    # Header JPEG tapi konten sampah → gagal decode.
    upload = SimpleUploadedFile("t.jpg", b"\xff\xd8\xff\xe0" + b"garbage" * 100)
    with pytest.raises(ValueError) as exc:
        normalize_image(upload)
    assert str(exc.value) == INVALID_PHOTO


def test_tolak_file_kosong_dan_none():
    with pytest.raises(ValueError) as exc1:
        normalize_image(None)
    assert str(exc1.value) == PHOTO_REQUIRED
    with pytest.raises(ValueError) as exc2:
        normalize_image(SimpleUploadedFile("t.jpg", b""))
    assert str(exc2.value) == PHOTO_REQUIRED


@override_settings(MEDIA_MAX_UPLOAD_MB=1)
def test_tolak_oversize():
    big = make_jpeg(size=(2000, 1000))
    assert len(big) > 0
    upload = SimpleUploadedFile("t.jpg", b"x" * (1 * 1024 * 1024 + 10))
    with pytest.raises(ValueError) as exc:
        normalize_image(upload)
    assert str(exc.value) == PHOTO_TOO_LARGE


def test_default_batas_2mb_tanpa_oversize():
    # Di atas default 2 MB (tapi di bawah 5 MB) → ditolak (DEC-14).
    upload = SimpleUploadedFile("t.jpg", b"\x00" * (2 * 1024 * 1024 + 1))
    with pytest.raises(ValueError) as exc:
        normalize_image(upload)
    assert str(exc.value) == PHOTO_TOO_LARGE

    # Di bawah default 2 MB → lolos cek ukuran (bukan ditolak).
    upload2 = SimpleUploadedFile("t.jpg", make_jpeg())
    result = normalize_image(upload2)
    assert result["mime_type"] == "image/jpeg"


def test_tolak_pixel_ekstrem():
    from PIL import Image

    buf = BytesIO()
    # 26MP (5200x5000) melewati MEDIA_MAX_PIXELS — buat PNG terkompresi kecil.
    Image.new("RGB", (5200, 5000), color=(0, 0, 0)).save(buf, format="PNG")
    upload = SimpleUploadedFile("t.png", buf.getvalue(), content_type="image/png")
    with pytest.raises(ValueError) as exc:
        normalize_image(upload)
    assert str(exc.value) == INVALID_PHOTO


# --------------------------------------------------------------- endpoint foto


def test_endpoint_admin_org_a_lihat_foto_org_a(client, org_a):
    admin = make_admin(org_a, "a-admin@example.com")
    asset = make_asset(org_a, admin)
    client.login(email="a-admin@example.com", password=PASSWORD)
    resp = client.get(reverse("photos:photo", args=[asset.pk]))
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("image/jpeg")


def test_endpoint_admin_org_b_404(client, org_a, org_b):
    make_admin(org_a, "a-admin@example.com")
    make_admin(org_b, "b-admin@example.com")
    asset = make_asset(org_a)
    client.login(email="b-admin@example.com", password=PASSWORD)
    resp = client.get(reverse("photos:photo", args=[asset.pk]))
    assert resp.status_code == 404


def test_endpoint_anonim_redirect_login(client, org_a):
    admin = make_admin(org_a)
    asset = make_asset(org_a, admin)
    resp = client.get(reverse("photos:photo", args=[asset.pk]))
    assert resp.status_code == 302
    assert "login" in resp["Location"] or "/accounts/login" in resp["Location"]


def test_endpoint_role_siswa_ditolak(client, org_a):
    admin = make_admin(org_a)
    asset = make_asset(org_a, admin)
    login_org(client, org_a, "siswa@example.com", role="siswa")
    resp = client.get(reverse("photos:photo", args=[asset.pk]))
    assert resp.status_code == 404


def test_endpoint_api_v1_alias(client, org_a):
    make_admin(org_a, "a-admin@example.com")
    asset = make_asset(org_a)
    client.login(email="a-admin@example.com", password=PASSWORD)
    resp = client.get(f"/api/v1/photos/{asset.pk}/")
    assert resp.status_code == 200


def test_file_tersimpan_di_private_media_dan_tidak_publik(client, org_a, settings):
    asset = make_asset(org_a)
    path = private_media_dir() / asset.storage_key
    assert path.is_file()
    assert "private_media" in str(path)

    # Tidak ada URL publik: akses path media langsung via URL media publik
    # tidak didaftarkan di urlconf — permintaan apa pun tidak dilayani Django.
    from django.urls import resolve, Resolver404

    with pytest.raises(Resolver404):
        resolve(f"/media/{asset.storage_key}")


# --------------------------------------------------------------- cleanup yatim


def test_cleanup_dry_run_tidak_menghapus(org_a):
    asset = make_asset(org_a)
    # File yatim: file tanpa MediaAsset.
    orphan_key = "photos/orphan-file.jpg"
    simpan_file(orphan_key, b"dummy")

    # Aset yatim: MediaAsset tanpa file.
    from apps.media_assets.services import hapus_file

    ghost_key = "photos/ghost.jpg"
    simpan_file(ghost_key, b"ghost")
    ghost = MediaAsset.objects.create(
        organization=org_a, storage_key=ghost_key, mime_type="image/jpeg",
        checksum="0" * 64,
    )
    hapus_file(ghost_key)  # file-nya dihapus → aset jadi yatim

    result = cleanup_media(dry_run=True)
    assert orphan_key in result["orphan_files"]
    assert str(ghost.pk) in result["orphan_assets"]
    # Dry-run: tidak ada yang berubah.
    assert file_exists(orphan_key)
    assert file_exists(asset.storage_key)
    assert MediaAsset.objects.filter(pk=ghost.pk).exists()


def test_cleanup_real_menghapus_yatim(org_a):
    asset = make_asset(org_a)
    orphan_key = "photos/orphan-file.jpg"
    simpan_file(orphan_key, b"dummy")

    ghost_key = "photos/ghost.jpg"
    simpan_file(ghost_key, b"ghost")
    ghost = MediaAsset.objects.create(
        organization=org_a, storage_key=ghost_key, mime_type="image/jpeg",
        checksum="1" * 64,
    )
    from apps.media_assets.services import hapus_file

    hapus_file(ghost_key)

    result = cleanup_media(dry_run=False)
    assert orphan_key in result["orphan_files"]
    assert not file_exists(orphan_key)  # file yatim dihapus
    assert not MediaAsset.objects.filter(pk=ghost.pk).exists()  # aset yatim dihapus
    # Asset valid tetap utuh.
    assert file_exists(asset.storage_key)
    assert MediaAsset.objects.filter(pk=asset.pk).exists()
