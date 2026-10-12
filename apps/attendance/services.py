"""Services master data Tahap 3: provisioning siswa + audit helper.

Logika bisnis di sini agar view HTML dan API masa depan memakai jalur yang
sama (TDIP §5.1). Semua operasi tenant-scoped dari penelepon (organization
hasil verifikasi membership, bukan input klien).
"""
import secrets

from django.db import transaction

from apps.accounts.models import User
from apps.audit.services import catat_audit
from apps.tenants.models import Membership

SISWA_TEMP_PASSWORD_LENGTH = 12
_TEMP_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%"


def generate_temp_password(length: int = SISWA_TEMP_PASSWORD_LENGTH) -> str:
    """Password sementara acak (dev convenience; wajib ganti saat login pertama)."""
    return "".join(secrets.choice(_TEMP_ALPHABET) for _ in range(length))


@transaction.atomic
def provision_student(
    *, organization, student_number, full_name, group=None,
    email=None, actor=None,
):
    """Buat StudentProfile; bila email diisi, buat akun + membership siswa.

    Satu transaksi. Password acak dikembalikan SEKALI ke pemanggil untuk
    ditampilkan di halaman sukses (dev convenience) — tidak pernah masuk log
    atau audit. email_verified_at null (DEC-01: verifikasi menyusul).
    """
    temp_password = None
    user = None
    if email:
        email = User.objects.normalize_email(email).lower()
        # Email unik platform-wide; bila sudah ada, jangan buat duplikat.
        if User.objects.filter(email=email).exists():
            raise ValueError("Email sudah terdaftar.")
        temp_password = generate_temp_password()
        user = User.objects.create_user(
            email,
            temp_password,
            email_verified_at=None,
        )
        Membership.objects.create(
            organization=organization, user=user, role=Membership.Role.SISWA
        )

    student = organization.students.create(
        student_number=student_number,
        full_name=full_name,
        group=group,
        user=user,
    )

    catat_audit(
        action="student_created",
        object_type="attendance.StudentProfile",
        object_id=student.pk,
        organization=organization,
        actor=actor,
        metadata={
            "student_number": student_number,
            "has_account": user is not None,
        },
    )
    if user is not None:
        catat_audit(
            action="account_provisioned",
            object_type="accounts.User",
            object_id=user.pk,
            organization=organization,
            actor=actor,
            metadata={"email": email, "role": "siswa"},
        )
    return student, temp_password


# =====================================================================
# Manajemen akun siswa (PRD AUTH-02) + penugasan shift
# =====================================================================

from django.core.exceptions import ValidationError as DjangoValidationError  # noqa: E402
from django.core.validators import validate_email as dj_validate_email  # noqa: E402


def _validate_unique_email(email):
    email = User.objects.normalize_email(email).lower()
    dj_validate_email(email)
    if User.objects.filter(email=email).exists():
        raise ValueError("Email ini sudah terdaftar.")
    return email


def set_student_account_active(*, student, active, actor):
    """Nonaktifkan/aktifkan akun siswa (User.is_active). Rekam absen utuh."""
    if student.user is None:
        raise ValueError("Siswa ini tidak punya akun.")
    user = student.user
    user.is_active = active
    user.save(update_fields=["is_active"])
    catat_audit(
        action="student_account_activated" if active else "student_account_deactivated",
        object_type="accounts.User",
        object_id=user.pk,
        organization=student.organization,
        actor=actor,
        metadata={"email": user.email, "student_number": student.student_number},
    )
    return user


def reset_student_password(*, student, actor):
    """Reset password akun siswa; password acak dikembalikan SEKALI, tak disimpan."""
    if student.user is None:
        raise ValueError("Siswa ini tidak punya akun.")
    user = student.user
    new_password = generate_temp_password()
    user.set_password(new_password)
    user.save(update_fields=["password"])
    catat_audit(
        action="student_password_reset",
        object_type="accounts.User",
        object_id=user.pk,
        organization=student.organization,
        actor=actor,
        metadata={"email": user.email, "student_number": student.student_number},
    )
    return new_password


def change_student_email(*, student, new_email, actor):
    """Ubah email akun siswa; validasi unik platform-wide + audit."""
    if student.user is None:
        raise ValueError("Siswa ini tidak punya akun.")
    user = student.user
    new_email = _validate_unique_email(new_email)
    old_email = user.email
    user.email = new_email
    user.email_verified_at = None
    user.save(update_fields=["email", "email_verified_at"])
    catat_audit(
        action="student_email_changed",
        object_type="accounts.User",
        object_id=user.pk,
        organization=student.organization,
        actor=actor,
        metadata={
            "old_email": old_email,
            "new_email": new_email,
            "student_number": student.student_number,
        },
    )
    return user


def assign_student_shift(*, student, shift, actor):
    """Tetapkan shift satu siswa (shift boleh None = fallback policy org)."""
    org = student.organization
    if shift is not None:
        if shift.organization_id != org.pk:
            raise ValueError("Shift bukan milik organisasi ini.")
        if not shift.is_active:
            raise ValueError("Shift tidak aktif.")
    old_shift = student.shift
    student.shift = shift
    student.save(update_fields=["shift", "updated_at"])
    catat_audit(
        action="student_shift_assigned",
        object_type="attendance.StudentProfile",
        object_id=student.pk,
        organization=org,
        actor=actor,
        metadata={
            "student_number": student.student_number,
            "shift": shift.name if shift else None,
            "previous_shift": old_shift.name if old_shift else None,
        },
    )
    return student


def bulk_assign_shift(*, organization, queryset, shift, actor):
    """Tetapkan shift untuk banyak siswa sekaligus (bulk per grup/kelas)."""
    count = 0
    for student in queryset:
        assign_student_shift(student=student, shift=shift, actor=actor)
        count += 1
    return count


def self_assign_shift(*, student, shift, actor):
    """Siswa pilih sendiri shift (bila allow_self_shift aktif di org settings)."""
    org = student.organization
    if not org.settings.get("allow_self_shift", False):
        raise PermissionError("Organisasi tidak mengizinkan pemilihan shift mandiri.")
    if student.shift_id:
        raise ValueError("Anda sudah punya shift.")
    if shift.organization_id != org.pk or not shift.is_active:
        raise ValueError("Shift tidak tersedia.")
    student.shift = shift
    student.save(update_fields=["shift", "updated_at"])
    catat_audit(
        action="student_self_shift",
        object_type="attendance.StudentProfile",
        object_id=student.pk,
        organization=org,
        actor=actor,
        metadata={
            "student_number": student.student_number,
            "shift": shift.name,
        },
    )
    return student


# =====================================================================
# Tahap 5 — Attendance Engine (TDIP v1.2 §10.2, §16 Tahap 5)
# =====================================================================

import hashlib  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402
import math  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402

from django.utils import timezone as dj_timezone  # noqa: E402

from apps.media_assets.services import (  # noqa: E402
    INVALID_PHOTO,
    PHOTO_REQUIRED,
    PHOTO_TOO_LARGE,
    generate_storage_key,
    normalize_image,
    simpan_file,
)
from apps.media_assets.models import MediaAsset as _MediaAsset  # noqa: E402

from .models import (  # noqa: E402
    AttendanceAttempt,
    AttendanceDay,
    AttendanceLocation,
    AttendancePolicy,
    IdempotencyRecord,
    Shift,
    StudentProfile,
)

# Error code stabil (kontrak API §9/§9.4 — konsisten frontend).
OUTSIDE_GEOFENCE = "OUTSIDE_GEOFENCE"
ACCURACY_TOO_LOW = "ACCURACY_TOO_LOW"
ALREADY_CHECKED_IN = "ALREADY_CHECKED_IN"
ALREADY_CHECKED_OUT = "ALREADY_CHECKED_OUT"
NOT_CHECKED_IN = "NOT_CHECKED_IN"
OUTSIDE_CHECKIN_WINDOW = "OUTSIDE_CHECKIN_WINDOW"
OUTSIDE_CHECKOUT_WINDOW = "OUTSIDE_CHECKOUT_WINDOW"
POLICY_NOT_CONFIGURED = "POLICY_NOT_CONFIGURED"
IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
VALIDATION_ERROR = "VALIDATION_ERROR"

_WIB = "Asia/Jakarta"
_WIB_TZ = ZoneInfo(_WIB)


class AttendanceError(Exception):
    """Error terkode; code adalah error code stabil untuk klien."""

    def __init__(self, code, message=""):
        self.code = code
        super().__init__(message or code)


def _haversine_m(lat1, lng1, lat2, lng2):
    """Jarak haversine dua titik (meter), input float derajat."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _parse_decimal(value, field):
    try:
        v = float(str(value).strip())
    except (TypeError, ValueError):
        raise AttendanceError(VALIDATION_ERROR, f"{field} tidak valid")
    if not math.isfinite(v):
        raise AttendanceError(VALIDATION_ERROR, f"{field} tidak valid")
    return v


def payload_hash(photo_bytes, lat, lng, accuracy, extra=""):
    """Hash payload untuk idempotensi (tanpa menyimpan payload)."""
    h = hashlib.sha256()
    h.update(photo_bytes or b"")
    h.update(f"|{lat}|{lng}|{accuracy}|{extra}".encode())
    return h.hexdigest()


def _now_wib():
    """Waktu server di zona WIB (Asia/Jakarta; DST tidak berlaku di Indonesia)."""
    return dj_timezone.localtime(dj_timezone.now(), _WIB_TZ)


def _record_attempt(*, student, kind, key, phash, outcome, error_code=None):
    AttendanceAttempt.objects.update_or_create(
        student=student,
        idempotency_key=key or "",
        defaults={
            "organization": student.organization,
            "kind": kind,
            "payload_hash": phash,
            "outcome": outcome,
            "error_code": error_code,
        },
    )


def _store_photo(*, organization, user, django_file):
    """Validasi + normalisasi foto → MediaAsset. Raise AttendanceError terkode."""
    try:
        result = normalize_image(django_file)
    except ValueError as exc:
        code = str(exc)
        if code not in (PHOTO_REQUIRED, INVALID_PHOTO, PHOTO_TOO_LARGE):
            code = INVALID_PHOTO
        raise AttendanceError(code)
    key = generate_storage_key()
    simpan_file(key, result["content"])
    return _MediaAsset.objects.create(
        organization=organization,
        storage_key=key,
        mime_type=result["mime_type"],
        width=result["width"],
        height=result["height"],
        size_bytes=result["size_bytes"],
        checksum=result["checksum"],
        uploaded_by=user,
    )


def _get_rule(*, student):
    """Aturan absensi siswa: shift miliknya (aktif) atau fallback policy org.

    Return objek dengan atribut days_active / check_in_* / check_out_* /
    late_tolerance_min / locations; raise AttendanceError bila tidak ada.
    """
    org = student.organization
    shift = None
    if student.shift_id:
        shift = Shift.objects.filter(pk=student.shift_id, is_active=True).first()
    if shift is not None and shift.organization_id != org.pk:
        # Siswa hanya boleh divalidasi terhadap shift di organisasinya.
        shift = None
    if shift is not None:
        return shift
    policy = AttendancePolicy.objects.filter(organization=org).first()
    if policy is None:
        raise AttendanceError(POLICY_NOT_CONFIGURED)
    return policy


def _get_policy_and_location(*, student, lat, lng):
    """Validasi rule (shift/policy) + pilih lokasi geofence. Raise AttendanceError."""
    org = student.organization
    if org.status != "active" or not student.is_active:
        raise AttendanceError(VALIDATION_ERROR, "Organisasi/siswa tidak aktif.")

    rule = _get_rule(student=student)

    now = _now_wib()
    if now.weekday() not in rule.days_active:
        raise AttendanceError(OUTSIDE_CHECKIN_WINDOW, "Hari ini bukan hari aktif.")

    # Lokasi berlaku: M2M rule bila diisi; selain itu semua lokasi aktif org.
    allowed = rule.locations.filter(is_active=True) or org.attendance_locations.filter(
        is_active=True
    )
    allowed = list(allowed)
    if not allowed:
        raise AttendanceError(POLICY_NOT_CONFIGURED, "Tidak ada lokasi aktif.")

    matched = None
    for loc in allowed:
        dist = _haversine_m(lat, lng, float(loc.latitude), float(loc.longitude))
        if dist <= loc.radius_m:
            matched = (loc, dist)
            break
    if matched is None:
        raise AttendanceError(OUTSIDE_GEOFENCE)
    loc, dist = matched
    return rule, loc, dist, now


def _check_window(kind, rule, now):
    """Validasi window jam untuk kind; return (start, end) waktu window."""
    if kind == AttendanceAttempt.Kind.CHECK_IN:
        end = (
            datetime.combine(now.date(), rule.check_in_end, tzinfo=now.tzinfo)
            + timedelta(minutes=rule.late_tolerance_min or 0)
        ).time()
        window = (rule.check_in_start, end)
        code = OUTSIDE_CHECKIN_WINDOW
    else:
        window = (rule.check_out_start, rule.check_out_end)
        code = OUTSIDE_CHECKOUT_WINDOW
    start, end = window
    t = now.time()
    if not (start <= t <= end):
        raise AttendanceError(code)
    return window


def _create_media_for_day(*, organization, user, django_file, day, field_at,
                          field_loc, field_media, loc, now, kind, key, phash):
    """Helper internal: simpan foto dan set field pada AttendanceDay."""
    asset = _store_photo(
        organization=organization, user=user, django_file=django_file
    )
    setattr(day, field_at, now)
    setattr(day, field_loc, loc)
    setattr(day, field_media, asset)
    day.save()
    return asset


def create_check_in(
    *,
    student, user, photo, latitude, longitude, accuracy,
    idempotency_key, endpoint="/api/v1/attendance/check-in/",
):
    """Check-in siswa: validasi berurutan → AttendanceDay (create-or-get).

    Idempotensi: key sama + payload sama → hasil sebelumnya (bukan error);
    payload beda → IDEMPOTENCY_CONFLICT. Semua penolakan tercatat pada
    AttendanceAttempt. Return (day, created, replayed).
    """
    kind = AttendanceAttempt.Kind.CHECK_IN
    lat = _parse_decimal(latitude, "latitude")
    lng = _parse_decimal(longitude, "longitude")
    acc = _parse_decimal(accuracy, "accuracy")

    photo_bytes = b""
    if photo is not None:
        try:
            photo_bytes = photo.read() or b""
        except Exception:
            photo_bytes = b""
        photo.seek(0)

    phash = payload_hash(photo_bytes, lat, lng, acc)
    org = student.organization

    # --- Idempotensi registri (sebelum validasi berat).
    if idempotency_key:
        existing = IdempotencyRecord.objects.filter(key=idempotency_key).first()
        if existing is not None:
            if existing.request_hash != phash or existing.organization_id != org.pk:
                _record_attempt(
                    student=student, kind=kind, key=idempotency_key,
                    phash=phash, outcome=AttendanceAttempt.Outcome.REJECTED,
                    error_code=IDEMPOTENCY_CONFLICT,
                )
                raise AttendanceError(IDEMPOTENCY_CONFLICT)
            # Payload sama → ulangi hasil tersimpan.
            snapshot = existing.response_snapshot or {}
            day = AttendanceDay.objects.filter(
                pk=snapshot.get("attendance_day_id")
            ).first()
            return day, False, True

    error_code = None
    try:
        with transaction.atomic():
            # --- Validasi berurutan (TDIP §10.2).
            policy, loc, dist, now = _get_policy_and_location(
                student=student, lat=lat, lng=lng
            )
            if acc > loc.max_accuracy_m:
                raise AttendanceError(ACCURACY_TOO_LOW)
            _check_window(kind, policy, now)

            # Toleransi terlambat: window check-in diperpanjang sampai
            # check_in_end + late_tolerance_min; di luar itu → window error.
            if kind == AttendanceAttempt.Kind.CHECK_IN:
                grace_end = (
                    datetime.combine(now.date(), policy.check_in_end,
                                     tzinfo=now.tzinfo)
                    + timedelta(minutes=policy.late_tolerance_min or 0)
                )
                if now > grace_end:
                    raise AttendanceError(OUTSIDE_CHECKIN_WINDOW)
            work_date = now.date()
            day, created = AttendanceDay.objects.get_or_create(
                student=student,
                work_date=work_date,
                defaults={
                    "organization": org,
                    "status": AttendanceDay.Status.PRESENT,
                },
            )
            day = AttendanceDay.objects.select_for_update().get(pk=day.pk)
            if day.check_in_at is not None:
                raise AttendanceError(ALREADY_CHECKED_IN)

            # --- Foto wajib → MediaAsset → update AttendanceDay.
            asset = _store_photo(organization=org, user=user, django_file=photo)
            day.check_in_at = now
            day.check_in_location = loc
            day.check_in_media = asset

            # Status late bila melewati check_in_end + toleransi.
            check_in_end_dt = datetime.combine(
                now.date(), policy.check_in_end, tzinfo=now.tzinfo
            )
            if now > check_in_end_dt:
                day.status = AttendanceDay.Status.LATE
                day.late_minutes = int(
                    (now - check_in_end_dt).total_seconds() // 60
                )
            else:
                day.status = AttendanceDay.Status.PRESENT
                day.late_minutes = 0
            day.save()

            IdempotencyRecord.objects.create(
                organization=org,
                key=idempotency_key,
                endpoint=endpoint,
                request_hash=phash,
                response_snapshot={"attendance_day_id": str(day.pk)},
            )
    except AttendanceError as exc:
        error_code = exc.code
    except Exception:
        error_code = "INTERNAL_ERROR"

    if error_code is not None:
        # Dicatat DI LUAR blok atomic agar tidak ikut rollback.
        _record_attempt(
            student=student, kind=kind, key=idempotency_key, phash=phash,
            outcome=(
                AttendanceAttempt.Outcome.REJECTED
                if error_code != "INTERNAL_ERROR"
                else AttendanceAttempt.Outcome.FAILED
            ),
            error_code=error_code,
        )
        raise AttendanceError(error_code)

    _record_attempt(
        student=student, kind=kind, key=idempotency_key, phash=phash,
        outcome=AttendanceAttempt.Outcome.SUCCESS,
    )
    return day, created, False


def create_check_out(
    *,
    student, user, photo, latitude, longitude, accuracy,
    idempotency_key, endpoint="/api/v1/attendance/check-out/",
):
    """Check-out siswa; butuh check-in sah, belum check-out (TDIP §16 Tahap 5)."""
    kind = AttendanceAttempt.Kind.CHECK_OUT
    lat = _parse_decimal(latitude, "latitude")
    lng = _parse_decimal(longitude, "longitude")
    acc = _parse_decimal(accuracy, "accuracy")

    photo_bytes = b""
    if photo is not None:
        try:
            photo_bytes = photo.read() or b""
        except Exception:
            photo_bytes = b""
        photo.seek(0)

    phash = payload_hash(photo_bytes, lat, lng, acc)
    org = student.organization

    error_code = None
    try:
        with transaction.atomic():
            policy, loc, dist, now = _get_policy_and_location(
                student=student, lat=lat, lng=lng
            )
            if acc > loc.max_accuracy_m:
                raise AttendanceError(ACCURACY_TOO_LOW)
            _check_window(kind, policy, now)

            work_date = now.date()
            day = AttendanceDay.objects.filter(
                student=student, work_date=work_date
            ).first()
            if day is None or day.check_in_at is None:
                raise AttendanceError(NOT_CHECKED_IN)
            day = AttendanceDay.objects.select_for_update().get(pk=day.pk)
            if day.check_out_at is not None:
                raise AttendanceError(ALREADY_CHECKED_OUT)

            asset = _store_photo(organization=org, user=user, django_file=photo)
            day.check_out_at = now
            day.check_out_location = loc
            day.check_out_media = asset
            # Status tetap (present/late) setelah check-out.
            day.save()

            IdempotencyRecord.objects.create(
                organization=org,
                key=idempotency_key,
                endpoint=endpoint,
                request_hash=phash,
                response_snapshot={"attendance_day_id": str(day.pk)},
            )
    except AttendanceError as exc:
        error_code = exc.code
    except Exception:
        error_code = "INTERNAL_ERROR"

    if error_code is not None:
        # Dicatat DI LUAR blok atomic agar tidak ikut rollback.
        _record_attempt(
            student=student, kind=kind, key=idempotency_key, phash=phash,
            outcome=(
                AttendanceAttempt.Outcome.REJECTED
                if error_code != "INTERNAL_ERROR"
                else AttendanceAttempt.Outcome.FAILED
            ),
            error_code=error_code,
        )
        raise AttendanceError(error_code)

    _record_attempt(
        student=student, kind=kind, key=idempotency_key, phash=phash,
        outcome=AttendanceAttempt.Outcome.SUCCESS,
    )
    return day, False, False


def attendance_day_snapshot(day):
    """Snapshot record untuk response API sukses 201."""
    def media_id(field):
        fid = getattr(day, f"{field}_media_id")
        return str(fid) if fid else None

    return {
        "attendance_day_id": str(day.pk),
        "work_date": day.work_date.isoformat(),
        "status": day.status,
        "late_minutes": day.late_minutes,
        "check_in_at": (
            dj_timezone.localtime(day.check_in_at, _WIB_TZ).isoformat()
            if day.check_in_at else None
        ),
        "check_in_media_id": media_id("check_in"),
        "check_in_location_id": (
            str(day.check_in_location_id) if day.check_in_location_id else None
        ),
        "check_out_at": (
            dj_timezone.localtime(day.check_out_at, _WIB_TZ).isoformat()
            if day.check_out_at else None
        ),
        "check_out_media_id": media_id("check_out"),
        "check_out_location_id": (
            str(day.check_out_location_id) if day.check_out_location_id else None
        ),
    }
