"""API pembina/admin: daftar kehadiran siswa per tanggal (dipakai dashboard.js).

Ter-scope tenant dari membership aktif; role admin/pembina saja.
"""
from django.http import JsonResponse
from django.utils import timezone as dj_timezone
from rest_framework.views import APIView

from apps.attendance.models import AttendanceDay
from apps.attendance.services import attendance_day_snapshot
from apps.tenants.context import get_active_membership

_ALLOWED_ROLES = {"admin", "pembina"}

_STATUS_MAP = {
    "present": "HADIR",
    "late": "PERLU_DITINJAU",
    "absent": "BELUM_HADIR",
    "excused": "BELUM_HADIR",
}


def _error(code, http):
    return JsonResponse({"code": code, "message": code}, status=http)


class AdminRecordsView(APIView):
    """GET /api/v1/attendance/records/?date=YYYY-MM-DD — daftar siswa + status hari itu."""

    def get(self, request):
        if not request.user.is_authenticated:
            return _error("AUTH_REQUIRED", 401)
        membership = get_active_membership(request.user)
        if membership is None or membership.role not in _ALLOWED_ROLES:
            return _error("TENANT_ACCESS_DENIED", 403)
        org = membership.organization

        date_str = request.GET.get("date")
        if date_str:
            try:
                the_date = dj_timezone.datetime.date.fromisoformat(date_str)
            except (ValueError, AttributeError):
                return _error("VALIDATION_ERROR", 422)
        else:
            the_date = dj_timezone.localtime(dj_timezone.now()).date()

        students = list(org.students.filter(is_active=True).order_by("full_name"))
        days = {
            d.student_id: d
            for d in AttendanceDay.objects.filter(
                organization=org, work_date=the_date
            ).select_related("student", "check_in_location")
        }

        status_filter = request.GET.get("status")
        results = []
        for s in students:
            d = days.get(s.id)
            if d is None:
                if status_filter in ("BELUM_HADIR",):
                    pass  # tetap tampil
                elif status_filter and status_filter != "BELUM_HADIR":
                    continue
                results.append({
                    "id": str(s.id),
                    "name": s.full_name,
                    "group": s.group or "",
                    "date": the_date.isoformat(),
                    "check_in": None,
                    "check_out": None,
                    "status": "BELUM_HADIR",
                    "distance_m": None,
                    "check_in_media_id": None,
                    "check_out_media_id": None,
                    "late_minutes": 0,
                })
                continue
            ui_status = _STATUS_MAP.get(d.status, "HADIR")
            if d.status in ("present", "late") and not d.check_out_at:
                ui_status = "BELUM_PULANG"
            if status_filter and ui_status != status_filter:
                continue
            snap = attendance_day_snapshot(d)
            results.append({
                "id": str(s.id),
                "name": s.full_name,
                "group": s.group or "",
                "date": the_date.isoformat(),
                "check_in": (
                    dj_timezone.localtime(d.check_in_at).strftime("%H:%M")
                    if d.check_in_at else None
                ),
                "check_out": (
                    dj_timezone.localtime(d.check_out_at).strftime("%H:%M")
                    if d.check_out_at else None
                ),
                "status": ui_status,
                "distance_m": None,
                "late_minutes": d.late_minutes,
                "check_in_media_id": snap["check_in_media_id"],
                "check_out_media_id": snap["check_out_media_id"],
                "location": (
                    d.check_in_location.name if d.check_in_location else ""
                ),
            })

        summary = {
            "hadir": sum(1 for r in results if r["status"] == "HADIR"),
            "belum_hadir": sum(1 for r in results if r["status"] == "BELUM_HADIR"),
            "pulang": sum(
                1 for r in results
                if r["status"] == "HADIR" and r["check_out"]
            ),
            "perlu_ditinjau": sum(
                1 for r in results if r["status"] == "PERLU_DITINJAU"
            ),
        }
        return JsonResponse({
            "date": the_date.isoformat(),
            "summary": summary,
            "count": len(results),
            "results": results,
        })
