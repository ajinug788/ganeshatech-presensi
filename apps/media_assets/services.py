"""Storage adapter + pipeline normalisasi foto (TDIP v1.2 §11).

Storage adapter berupa module-level function (simpan/baca/hapus) di atas
path MEDIA_ROOT/private_media agar nanti dapat diganti object storage
tanpa mengubah pemanggil. Tidak ada URL publik; file tidak di webroot.

Error terkode: PHOTO_REQUIRED, INVALID_PHOTO, PHOTO_TOO_LARGE
(detail internal tidak dibocorkan ke klien).
"""
import hashlib
import logging
import uuid
from io import BytesIO

from django.conf import settings
from django.core.exceptions import SuspiciousOperation

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# Error code stabil untuk klien (PRD §9.4).
PHOTO_REQUIRED = "PHOTO_REQUIRED"
INVALID_PHOTO = "INVALID_PHOTO"
PHOTO_TOO_LARGE = "PHOTO_TOO_LARGE"

# Format raster yang diterima untuk bukti absensi. SVG & format aktif lain ditolak.
_ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}

# Pixel ekstrem ditolak sebelum decode penuh (anti-DoS, IMG-04).
_IMAGE_MAX_PIXELS = 25_000_000  # >25MP

# Untuk Pillow: batas decode global.
Image.MAX_IMAGE_PIXELS = _IMAGE_MAX_PIXELS

# Resampling filter kompatibel lintas versi Pillow.
_RESAMPLE = getattr(Image, "Resampling", Image).LANCZOS


def private_media_dir():
    """Direktori storage privat (di luar webroot publik)."""
    return settings.MEDIA_ROOT


def _key_to_path(storage_key):
    """Konversi storage_key → path di dalam private_media.

    storage_key berisi segmen aman (hex); tolak traversal apapun.
    """
    if not storage_key or storage_key.startswith("/"):
        raise SuspiciousOperation("storage key tidak valid")
    if any(seg in ("..", "") for seg in storage_key.split("/")):
        raise SuspiciousOperation("storage key tidak valid")
    return private_media_dir() / storage_key


def simpan_file(storage_key, content: bytes) -> int:
    """Simpan bytes ke private_media pada path dari storage_key. Return size."""
    path = _key_to_path(storage_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    size = path.write_bytes(content)
    logger.info("media_disimpan key=%s size=%s", storage_key, size)
    return size


def baca_file(storage_key) -> bytes:
    """Baca isi file dari private_media berdasarkan storage_key."""
    path = _key_to_path(storage_key)
    return path.read_bytes()


def hapus_file(storage_key) -> bool:
    """Hapus file; True bila file ada dan terhapus."""
    path = _key_to_path(storage_key)
    if path.is_file():
        path.unlink()
        logger.info("media_dihapus key=%s", storage_key)
        return True
    return False


def file_exists(storage_key) -> bool:
    return _key_to_path(storage_key).is_file()


def iter_stored_keys():
    """Yield semua storage_key yang benar-benar ada di private_media."""
    root = private_media_dir()
    if not root.exists():
        return
    for p in sorted(root.rglob("*")):
        if p.is_file():
            yield p.relative_to(root).as_posix()


def generate_storage_key() -> str:
    """Key baru: yyyy/mm/<uuid>.jpg — relatif, bukan path absolut."""
    from django.utils import timezone

    now = timezone.now()
    return f"photos/{now:%Y/%m}/{uuid.uuid4().hex}.jpg"


def normalize_image(django_file, *, max_upload_mb=None, max_pixels=None):
    """Verifikasi + normalisasi foto upload (IMG-04/05/06).

    - Verifikasi konten aktual via Pillow (bukan content-type klien).
    - Tolak SVG/format non-raster, gambar korup, pixel ekstrem (>25MP).
    - Hard limit ukuran default 2 MB (setting MEDIA_MAX_UPLOAD_MB, DEC-14).
    - Resize sisi terpanjang maks 1280px, konversi JPEG kualitas 0.78,
      EXIF dihapus (orientasi diterapkan dulu), hitung dimensi/size/checksum.

    Return dict: {content, mime_type, width, height, size_bytes, checksum}.
    Raise ValueError dengan message = kode error stabil
    (PHOTO_REQUIRED / INVALID_PHOTO / PHOTO_TOO_LARGE).
    """
    if max_upload_mb is None:
        max_upload_mb = getattr(settings, "MEDIA_MAX_UPLOAD_MB", 2)
    if max_pixels is None:
        max_pixels = getattr(settings, "MEDIA_MAX_PIXELS", _IMAGE_MAX_PIXELS)
    max_bytes = int(max_upload_mb) * 1024 * 1024

    if django_file is None:
        raise ValueError(PHOTO_REQUIRED)
    data = django_file.read()
    if not data:
        raise ValueError(PHOTO_REQUIRED)
    if len(data) > max_bytes:
        raise ValueError(PHOTO_TOO_LARGE)

    try:
        img = Image.open(BytesIO(data))
        img.load()
    except Exception:
        # Korup / format tidak dikenal / file jebakan — tanpa detail internal.
        raise ValueError(INVALID_PHOTO)
    if img.format not in _ALLOWED_FORMATS:
        raise ValueError(INVALID_PHOTO)
    if (img.width * img.height) > max_pixels:
        raise ValueError(INVALID_PHOTO)

    # Terapkan orientasi EXIF lalu buang seluruh metadata (EXIF dihapus).
    img = ImageOps.exif_transpose(img)
    # Resize sisi terpanjang maks 1280px.
    max_side = 1280
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), _RESAMPLE)
    if img.mode != "RGB":
        img = img.convert("RGB")

    out = BytesIO()
    img.save(out, format="JPEG", quality=78)
    content = out.getvalue()

    return {
        "content": content,
        "mime_type": "image/jpeg",
        "width": img.width,
        "height": img.height,
        "size_bytes": len(content),
        "checksum": hashlib.sha256(content).hexdigest(),
    }
