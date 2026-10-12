"""Layanan Tahap 6 — penandaan absent otomatis + helper rekap.

TDIP v1.2 §16 Tahap 6: hari yang sudah lewat window check-in tanpa
kehadiran → status absent. Idempoten: hanya membuat AttendanceDay yang
belum ada, hanya untuk tanggal yang sudah lewat, hanya organisasi aktif.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone as dj_timezone

_WIB_TZ = ZoneInfo("Asia/Jakarta")


def _today_wib(now=None):
    return dj_timezone.localtime(now or dj_timezone.now(), _WIB_TZ).date()


def mark_absent(*, organization, lookback_days=60, ref_date=None, now=None):
    """Tandai absent untuk siswa aktif tanpa AttendanceDay pada hari lewat.

    - Hanya hari yang nilai weekday-nya ada di policy.days_active.
    - Tanggal hari ini diproses hanya bila window check-in (+ toleransi)
      sudah lewat.
    - Idempoten: AttendanceDay yang sudah ada tidak pernah diubah/dibuat ulang.
    - ref_date: proses satu tanggal spesifik (harus sudah lewat window).
    Return jumlah AttendanceDay baru yang dibuat.
    """
    from apps.attendance.models import AttendanceDay, AttendancePolicy

    policy = AttendancePolicy.objects.filter(organization=organization).first()
    if policy is None or organization.status != "active":
        return 0

    today = _today_wib(now)
    tolerance_end = (
        datetime.combine(today, policy.check_in_end, tzinfo=_WIB_TZ)
        + timedelta(minutes=policy.late_tolerance_min or 0)
    )

    if ref_date is not None:
        dates = [ref_date]
    else:
        start = today - timedelta(days=max(0, int(lookback_days) - 1))
        dates = [start + timedelta(days=i) for i in range((today - start).days + 1)]

    created = 0
    for day_date in dates:
        if day_date.weekday() not in policy.days_active:
            continue
        if day_date == today:
            # Hari ini: hanya bila window check-in (+toleransi) sudah lewat.
            current = dj_timezone.localtime(now or dj_timezone.now(), _WIB_TZ)
            if current <= tolerance_end:
                continue
        elif day_date > today:
            continue

        existing = set(
            AttendanceDay.objects.filter(
                organization=organization, work_date=day_date
            ).values_list("student_id", flat=True)
        )
        missing = [
            AttendanceDay(
                organization=organization,
                student=student,
                work_date=day_date,
                status=AttendanceDay.Status.ABSENT,
            )
            for student in organization.students.filter(is_active=True)
            if student.id not in existing
        ]
        if missing:
            AttendanceDay.objects.bulk_create(missing, ignore_conflicts=True)
            created += len(missing)
    return created
