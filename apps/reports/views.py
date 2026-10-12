"""Views Tahap 6 — Dashboard pembina nyata + rekap/laporan + koreksi + CSV.

Semua queryset ter-scope organization dari membership aktif (TDIP §7.3).
"""
import csv
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models import Sum  # noqa: F401
from django.db import models  # noqa: F401
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.utils import timezone as dj_timezone

from apps.audit.models import AuditLog
from apps.audit.services import catat_audit
from apps.attendance.models import AttendanceDay, AttendancePolicy, StudentProfile
from apps.tenants.context import RoleRequiredMixin, role_required
from .forms import AttendanceStatusForm

_WIB_TZ = ZoneInfo("Asia/Jakarta")
_BULAN_ID = ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"]


def _local_time(value):
    """DateTimeField aware → jam WIB 'HH:MM' (None-safe)."""
    if not value:
        return "—"
    return dj_timezone.localtime(value, _WIB_TZ).strftime("%H:%M")


def _parse_date(value, default):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- Dashboard


def build_pembina_context(membership, organization):
    """Context dashboard pembina (dipakai view baru dan endpoint lama)."""
    org = organization
    today = dj_timezone.localtime(dj_timezone.now(), _WIB_TZ).date()

    students = org.students.filter(is_active=True).select_related("shift")
    total_siswa = students.count()

    days_today = {
        d.student_id: d
        for d in AttendanceDay.objects.filter(
            organization=org, work_date=today, student__is_active=True
        ).select_related("student", "check_in_location", "check_out_location")
    }

    hadir = sum(
        1 for d in days_today.values() if d.status == AttendanceDay.Status.PRESENT
    )
    terlambat = sum(
        1 for d in days_today.values() if d.status == AttendanceDay.Status.LATE
    )
    sedang_berjalan = sum(
        1 for d in days_today.values() if d.check_in_at and not d.check_out_at
    )
    belum_ids = [s.id for s in students if s.id not in days_today]
    belum = list(students.filter(id__in=belum_ids).order_by("full_name"))

    aktivitas = (
        AttendanceDay.objects.filter(organization=org)
        .filter(Q(check_in_at__isnull=False) | Q(check_out_at__isnull=False))
        .select_related("student", "check_in_location", "check_out_location")
        .order_by("-check_in_at", "-check_out_at")[:10]
    )

    return {
        "membership": membership,
        "today": today,
        "total_siswa": total_siswa,
        "hadir": hadir,
        "terlambat": terlambat,
        "belum_absen": len(belum),
        "sedang_berjalan": sedang_berjalan,
        "belum_list": belum,
        "aktivitas": [
            {
                "day": d,
                "masuk": _local_time(d.check_in_at),
                "pulang": _local_time(d.check_out_at),
                "lokasi": (
                    d.check_in_location.name
                    if d.check_in_location
                    else (d.check_out_location.name if d.check_out_location else "")
                ),
            }
            for d in aktivitas
        ],
        "rekap_url": "/reports/rekap/",
    }


def _student_status_label(status):
    return dict(AttendanceDay.Status.choices).get(status, status)


def build_student_home_context(membership):
    """Context dashboard siswa: hari ini + rekap bulan berjalan."""
    org = membership.organization
    now = dj_timezone.localtime(dj_timezone.now(), _WIB_TZ)
    today = now.date()

    student = org.students.filter(
        user=membership.user, is_active=True
    ).first()

    ctx = {
        "membership": membership,
        "today": today,
        "month_label": f"{_BULAN_ID[now.month - 1]} {now.year}",
        "today_day": None,
        "today_status_label": "",
        "month_present": 0,
        "month_late": 0,
        "month_absent": 0,
        "month_excused": 0,
        "month_late_minutes": 0,
    }
    if student is None:
        return ctx

    today_day = AttendanceDay.objects.filter(
        organization=org, student=student, work_date=today
    ).first()
    if today_day:
        ctx["today_day"] = today_day
        ctx["today_status_label"] = _student_status_label(today_day.status)

    month_days = AttendanceDay.objects.filter(
        organization=org, student=student,
        work_date__year=today.year, work_date__month=today.month,
    )
    counts = month_days.values("status").annotate(n=models.Count("id"))
    for row in counts:
        if row["status"] == AttendanceDay.Status.PRESENT:
            ctx["month_present"] = row["n"]
        elif row["status"] == AttendanceDay.Status.LATE:
            ctx["month_late"] = row["n"]
        elif row["status"] == AttendanceDay.Status.ABSENT:
            ctx["month_absent"] = row["n"]
        elif row["status"] == AttendanceDay.Status.EXCUSED:
            ctx["month_excused"] = row["n"]
    ctx["month_late_minutes"] = (
        month_days.aggregate(total=models.Sum("late_minutes"))["total"] or 0
    )
    return ctx


class PembinaDashboardView(RoleRequiredMixin, View):
    """Dashboard pembina/admin: ringkasan hari ini per organisasi."""

    allowed_roles = ("admin", "pembina")
    template_name = "dashboard/pembina.html"

    def get(self, request):
        ctx = build_pembina_context(self.membership, self.organization)
        return render(request, self.template_name, ctx)


# ---------------------------------------------------------------- Dashboard Admin


def build_admin_context(membership, organization):
    """Context dashboard admin (dipakai tenants.views.dashboard_admin).

    Mengikuti struktur mockup: KPI hari ini, tabel aktivitas presensi,
    panel 'Perlu Tindakan' (siswa belum absen), mini-card per lokasi.
    """
    import datetime as _dt

    base = build_pembina_context(membership, organization)
    org = organization
    today = base["today"]
    students = org.students.filter(is_active=True).select_related("shift")

    total = base["total_siswa"]
    hadir = base["hadir"]
    terlambat = base["terlambat"]
    belum = base["belum_absen"]

    def _pct(part, whole):
        return round(part / whole * 100, 1) if whole else 0.0

    # Tabel aktivitas dibatasi ke hari kerja saat ini dan siswa aktif.
    today_days = AttendanceDay.objects.filter(
        organization=org, work_date=today, student__is_active=True
    ).select_related(
        "student", "check_in_location", "check_out_location",
        "check_in_media", "check_out_media",
    ).order_by("-updated_at")
    aktivitas_rows = []
    for d in today_days[:10]:
        media_id = (
            d.check_in_media.id
            if d.check_in_media
            else (d.check_out_media.id if d.check_out_media else None)
        )
        aktivitas_rows.append(
            {
                "day": d,
                "masuk": _local_time(d.check_in_at),
                "pulang": _local_time(d.check_out_at),
                "lokasi": (
                    d.check_out_location.name
                    if d.check_out_location
                    else (d.check_in_location.name if d.check_in_location else "")
                ),
                "status_label": _student_status_label(d.status),
                "late_minutes": d.late_minutes,
                "photo_url": (
                    f"/photos/{media_id}/"
                    if media_id and membership.role == "admin"
                    else None
                ),
            }
        )

    # Check-in per titik tersedia; backend tidak menyimpan penugasan
    # siswa ke titik, jadi jangan tampilkan rasio kehadiran per lokasi.
    lokasi_rows = []
    active_locations = org.attendance_locations.filter(is_active=True)
    for loc in active_locations:
        days_loc = AttendanceDay.objects.filter(
            organization=org,
            work_date=today,
            check_in_location=loc,
            student__is_active=True,
        )
        check_ins = days_loc.filter(check_in_at__isnull=False).count()
        late_loc = days_loc.filter(status=AttendanceDay.Status.LATE).count()
        lokasi_rows.append(
            {
                "location": loc,
                "check_ins": check_ins,
                "late": late_loc,
                "radius_m": loc.radius_m,
            }
        )

    koreksi_logs = (
        AuditLog.objects.filter(
            organization=org,
            action__in=("attendance_corrected", "attendance_status_recorded"),
        ).select_related("actor").order_by("-created_at")[:10]
    )

    try:
        policy = org.attendance_policy
    except AttendancePolicy.DoesNotExist:
        policy = None

    shift_rows = []
    active_shifts = org.shifts.filter(is_active=True)
    for shift in active_shifts:
        assigned_total = students.filter(shift=shift).count()
        shift_days = AttendanceDay.objects.filter(
            organization=org,
            student__is_active=True,
            student__shift=shift,
            work_date=today,
        )
        recorded = shift_days.count()
        shift_cutoff = (
            _dt.datetime.combine(today, shift.check_in_end, tzinfo=_WIB_TZ)
            + _dt.timedelta(minutes=shift.late_tolerance_min)
        ).time()
        shift_rows.append({
            "shift": shift,
            "assigned_total": assigned_total,
            "recorded": recorded,
            "check_ins": shift_days.filter(check_in_at__isnull=False).count(),
            "late": shift_days.filter(status=AttendanceDay.Status.LATE).count(),
            "unrecorded": max(assigned_total - recorded, 0),
            "tolerance_at": shift_cutoff,
        })

    fallback_students = students.filter(
        Q(shift__isnull=True) | Q(shift__is_active=False)
    )
    fallback_total = fallback_students.count()
    fallback_recorded = AttendanceDay.objects.filter(
        organization=org,
        student__is_active=True,
        work_date=today,
    ).filter(Q(student__shift__isnull=True) | Q(student__shift__is_active=False)).count()

    return {
        **base,
        "pct_hadir": _pct(hadir, total),
        "pct_terlambat": _pct(terlambat, total),
        "pct_belum": _pct(belum, total),
        "aktivitas_rows": aktivitas_rows,
        "lokasi_rows": lokasi_rows,
        "lokasi_aktif": len(lokasi_rows),
        "koreksi_logs": koreksi_logs,
        "org_slug": org.slug,
        "org_name": org.name,
        "now_wib": dj_timezone.localtime(dj_timezone.now(), _WIB_TZ),
        "policy": policy,
        "shift_rows": shift_rows,
        "shift_aktif": len(shift_rows),
        "fallback_total": fallback_total,
        "fallback_unrecorded": max(fallback_total - fallback_recorded, 0),
    }


@role_required("admin")
def riwayat_koreksi(request):
    """Riwayat koreksi dan status manual untuk satu organisasi."""
    action = request.GET.get("action", "").strip()
    logs = AuditLog.objects.filter(
        organization=request.organization,
        action__in=("attendance_corrected", "attendance_status_recorded"),
    ).select_related("actor")
    if action in {"attendance_corrected", "attendance_status_recorded"}:
        logs = logs.filter(action=action)
    logs = Paginator(logs.order_by("-created_at"), 25).get_page(
        request.GET.get("page")
    )
    return render(
        request,
        "reports/riwayat_koreksi.html",
        {"membership": request.membership, "logs": logs, "action": action},
    )


class AdminCatatIzinView(RoleRequiredMixin, View):
    """POST dari modal 'Catat Izin' dashboard admin.

    Siswa tanpa AttendanceDay hari ini → catat izin/tidak hadir dan audit.
    Hanya admin sekolah; scope tenant dari membership aktif.
    """

    allowed_roles = ("admin",)

    def post(self, request):
        org = self.organization
        student_id = (request.POST.get("student_id") or "").strip()
        student = org.students.filter(pk=student_id, is_active=True).first()
        if student is None:
            messages.error(request, "Siswa tidak ditemukan di organisasi ini.")
            return redirect("tenants:dashboard_admin")

        today = dj_timezone.localtime(dj_timezone.now(), _WIB_TZ).date()
        if AttendanceDay.objects.filter(
            organization=org, student=student, work_date=today
        ).exists():
            messages.error(
                request,
                "Siswa sudah memiliki catatan hari ini. Gunakan alur koreksi absensi.",
            )
            return redirect("tenants:dashboard_admin")
        form = AttendanceStatusForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Status dan alasan pencatatan wajib diisi dengan benar.")
            return redirect("tenants:dashboard_admin")

        new_status = form.cleaned_data["status"]
        reason = form.cleaned_data["reason"]
        try:
            with transaction.atomic():
                day = AttendanceDay.objects.create(
                    organization=org,
                    student=student,
                    work_date=today,
                    status=new_status,
                    late_minutes=0,
                )
                catat_audit(
                    action="attendance_status_recorded",
                    object_type="attendance.AttendanceDay",
                    object_id=day.pk,
                    organization=org,
                    actor=request.user,
                    reason=reason,
                    metadata={
                        "old_status": None,
                        "new_status": new_status,
                        "work_date": day.work_date.isoformat(),
                        "student_number": student.student_number,
                        "created": True,
                        "source": "dashboard_admin",
                    },
                )
        except IntegrityError:
            messages.error(
                request,
                "Siswa sudah memiliki catatan hari ini. Gunakan alur koreksi absensi.",
            )
            return redirect("tenants:dashboard_admin")
        messages.success(
            request, "Status siswa tersimpan dan tercatat di audit."
        )
        return redirect("tenants:dashboard_admin")


# ---------------------------------------------------------------- Rekap


class RekapLaporanView(RoleRequiredMixin, View):
    """Rekap kehadiran per siswa dengan filter tanggal/kelompok/status."""

    allowed_roles = ("admin", "pembina")
    template_name = "reports/rekap.html"

    def get(self, request):
        org = self.organization
        today = dj_timezone.localtime(dj_timezone.now(), _WIB_TZ).date()
        start = _parse_date(request.GET.get("start"), today.replace(day=1))
        end = _parse_date(request.GET.get("end"), today)
        if end < start:
            start, end = end, start
        group = request.GET.get("group", "").strip()
        status = request.GET.get("status", "").strip()
        student_id = request.GET.get("student", "").strip()

        students = org.students.filter(is_active=True)
        if group:
            students = students.filter(group=group)

        days = AttendanceDay.objects.filter(
            organization=org, work_date__gte=start, work_date__lte=end
        )
        if group:
            days = days.filter(student__group=group)
        if status:
            days = days.filter(status=status)

        per_student = defaultdict(
            lambda: {
                "present": 0, "late": 0, "absent": 0, "excused": 0, "late_minutes": 0,
            }
        )
        for d in days:
            agg = per_student[d.student_id]
            agg[d.status] += 1
            agg["late_minutes"] += d.late_minutes

        rows = []
        for s in students:
            agg = per_student.get(
                s.id,
                {"present": 0, "late": 0, "absent": 0, "excused": 0, "late_minutes": 0},
            )
            total = agg["present"] + agg["late"] + agg["absent"] + agg["excused"]
            pct = (
                round((agg["present"] + agg["late"]) / total * 100, 1) if total else None
            )
            rows.append({"student": s, "agg": agg, "total": total, "pct": pct})

        detail_student = None
        detail_days = None
        if student_id:
            detail_student = students.filter(id=student_id).first()
            if detail_student:
                detail_days = AttendanceDay.objects.filter(
                    organization=org, student=detail_student,
                    work_date__gte=start, work_date__lte=end,
                ).order_by("work_date")

        ctx = {
            "membership": self.membership,
            "start": start,
            "end": end,
            "group": group,
            "status": status,
            "student_id": student_id,
            "groups": (
                org.students.order_by("group").values_list("group", flat=True).distinct()
            ),
            "status_choices": AttendanceDay.Status.choices,
            "rows": rows,
            "detail_student": detail_student,
            "detail_days": detail_days,
            "can_correct": self.membership.role == "admin",
            "csv_query": request.GET.urlencode(),
            "statuses": AttendanceDay.Status.values,
        }
        return render(request, self.template_name, ctx)


# ---------------------------------------------------------------- Koreksi


class KoreksiAttendanceView(RoleRequiredMixin, View):
    """Koreksi status AttendanceDay — admin saja, alasan wajib, audit tercatat."""

    allowed_roles = ("admin",)
    template_name = "reports/koreksi.html"
    allowed_statuses = {
        AttendanceDay.Status.PRESENT,
        AttendanceDay.Status.LATE,
        AttendanceDay.Status.ABSENT,
        AttendanceDay.Status.EXCUSED,
    }

    def _get_day(self, request, pk):
        return get_object_or_404(
            AttendanceDay, pk=pk, organization=self.organization
        )

    def get(self, request, pk):
        day = self._get_day(request, pk)
        return render(request, self.template_name, {"day": day, "statuses": AttendanceDay.Status.choices})

    def post(self, request, pk):
        day = self._get_day(request, pk)
        new_status = (request.POST.get("status") or "").strip()
        reason = (request.POST.get("reason") or "").strip()

        errors = []
        if new_status not in self.allowed_statuses:
            errors.append("Status tidak valid.")
        if not reason:
            errors.append("Alasan koreksi wajib diisi.")
        if new_status and new_status == day.status:
            errors.append("Status baru sama dengan status saat ini.")
        if errors:
            return render(
                request, self.template_name,
                {
                    "day": day,
                    "statuses": AttendanceDay.Status.choices,
                    "errors": errors,
                    "selected_status": new_status,
                    "reason": reason,
                },
                status=400,
            )

        old_status = day.status
        old_late = day.late_minutes
        day.status = new_status
        if new_status != AttendanceDay.Status.LATE:
            day.late_minutes = 0
        with transaction.atomic():
            day.save(update_fields=["status", "late_minutes", "updated_at"])
            catat_audit(
                action="attendance_corrected",
                object_type="attendance.AttendanceDay",
                object_id=day.pk,
                organization=self.organization,
                actor=request.user,
                reason=reason,
                metadata={
                    "old_status": old_status,
                    "new_status": new_status,
                    "old_late_minutes": old_late,
                    "late_minutes": day.late_minutes,
                    "work_date": day.work_date.isoformat(),
                    "student_number": day.student.student_number,
                },
            )
        messages.success(request, "Koreksi absensi tersimpan dan tercatat di audit.")
        return redirect("/reports/rekap/")


# ---------------------------------------------------------------- CSV Export


class Echo:
    """File-like yang menulis baris CSV ke stream (ditulis sebagai bytes)."""

    def write(self, value):
        return value


def _csv_rows_to_stream(rows):
    """csv.writer(Echo()) menghasilkan string; kirim sebagai UTF-8 bytes."""
    for chunk in rows():
        if isinstance(chunk, str):
            yield chunk.encode("utf-8")
        else:
            yield chunk


class RekapCsvView(RoleRequiredMixin, View):
    """Export CSV streaming: nama, student_number, tanggal, status,
    late_minutes, jam masuk/keluar, lokasi."""

    allowed_roles = ("admin", "pembina")

    def get(self, request):
        org = self.organization
        today = dj_timezone.localtime(dj_timezone.now(), _WIB_TZ).date()
        start = _parse_date(request.GET.get("start"), today.replace(day=1))
        end = _parse_date(request.GET.get("end"), today)
        if end < start:
            start, end = end, start
        group = request.GET.get("group", "").strip()
        status = request.GET.get("status", "").strip()

        days = (
            AttendanceDay.objects.filter(
                organization=org, work_date__gte=start, work_date__lte=end
            )
            .select_related("student", "check_in_location", "check_out_location")
            .order_by("work_date", "student__full_name")
        )
        if group:
            days = days.filter(student__group=group)
        if status:
            days = days.filter(status=status)

        writer = csv.writer(Echo())

        def rows():
            yield writer.writerow([
                "nama", "student_number", "tanggal", "status", "late_minutes",
                "jam_masuk", "jam_keluar", "lokasi",
            ])
            for d in days.iterator():
                loc = d.check_out_location or d.check_in_location
                yield writer.writerow([
                    d.student.full_name,
                    d.student.student_number,
                    d.work_date.isoformat(),
                    d.status,
                    d.late_minutes,
                    _local_time(d.check_in_at),
                    _local_time(d.check_out_at),
                    loc.name if loc else "",
                ])

        response = StreamingHttpResponse(
            _csv_rows_to_stream(rows), content_type="text/csv"
        )
        response["Content-Disposition"] = (
            f'attachment; filename="rekap-kehadiran-{start.isoformat()}-'
            f'{end.isoformat()}.csv"'
        )
        return response


def _recent_days(org, student, limit=3):
    return list(
        AttendanceDay.objects.filter(
            organization=org, student=student, check_in_at__isnull=False
        ).order_by("-work_date")[:limit]
    )


def _policy_context(org, ctx):
    """Info shift & toleransi dari AttendancePolicy (None-safe)."""
    try:
        policy = org.attendance_policy
    except Exception:
        policy = None
    if policy:
        ctx["policy_check_in"] = policy.check_in_start.strftime("%H:%M")
        ctx["policy_check_out"] = policy.check_out_start.strftime("%H:%M")
        ctx["policy_tolerance"] = policy.late_tolerance_min
        import datetime as _dt
        base = now_wib().replace(
            hour=policy.check_in_end.hour,
            minute=policy.check_in_end.minute,
            second=0,
            microsecond=0,
        )
        ctx["policy_tolerance_at"] = (base + _dt.timedelta(minutes=policy.late_tolerance_min)).strftime("%H:%M")
    else:
        ctx["policy_check_in"] = None
    return ctx


def now_wib():
    return dj_timezone.localtime(dj_timezone.now(), _WIB_TZ)


def build_student_dashboard_context(membership):
    """Context dashboard siswa v2 (UI baru): greeting, status, shift, rekap, riwayat 3 sesi."""
    ctx = build_student_home_context(membership)
    org = membership.organization
    now = now_wib()
    ctx["now_time"] = now.strftime("%H:%M")
    ctx["greeting"] = (
        "Selamat Pagi" if now.hour < 11
        else "Selamat Siang" if now.hour < 15
        else "Selamat Sore" if now.hour < 19
        else "Selamat Malam"
    )
    student = org.students.filter(user=membership.user, is_active=True).first()
    if student:
        ctx["student_name"] = student.full_name
        ctx["student_group"] = student.group or ""
    else:
        ctx["student_name"] = membership.user.get_short_name() or membership.user.email
        ctx["student_group"] = ""
    ctx = _policy_context(org, ctx)
    if student:
        recent = _recent_days(org, student)
        ctx["recent_days"] = recent
        ctx["recent_count"] = len(recent)
    else:
        ctx["recent_days"] = []
        ctx["recent_count"] = 0
    total = ctx["month_present"] + ctx["month_late"] + ctx["month_absent"] + ctx["month_excused"]
    ctx["month_total"] = total
    ctx["discipline_pct"] = round(100 * ctx["month_present"] / total) if total else 100
    return ctx
