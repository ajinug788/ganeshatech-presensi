"""API DRF Tahap 5 — /api/v1/attendance/* (TDIP v1.2 §9).

Session auth, role siswa. Error JSON {code, message} sesuai §9:
409 untuk konflik/duplikasi, 422 untuk validasi gagal.
"""
import json

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

# DRF dipakai via APIView; import di bawah.
from rest_framework import status as http_status
from rest_framework.views import APIView

from apps.tenants.context import get_active_membership

from .models import AttendanceAttempt, AttendanceDay
from .services import (
    AttendanceError,
    IDEMPOTENCY_CONFLICT,
    attendance_day_snapshot,
    create_check_in,
    create_check_out,
)


def _error_response(code, http_code):
    from django.http import JsonResponse

    return JsonResponse(
        {"code": code, "message": code}, status=http_code
    )


def _get_student(membership):
    from .models import StudentProfile

    return StudentProfile.objects.filter(
        organization=membership.organization,
        user=membership.user,
        is_active=True,
    ).first()


def _idempotency_key(request):
    return (
        request.headers.get("Idempotency-Key")
        or request.POST.get("idempotency_key")
        or request.POST.get("client_request_id")
        or ""
    )


@method_decorator(csrf_exempt, name="dispatch")
class BaseCheckView(APIView):
    """POST multipart check-in/check-out — session auth, role siswa."""

    kind_endpoint = ""
    service = None

    def post(self, request):
        from django.http import JsonResponse

        if not request.user.is_authenticated:
            return _error_response("AUTH_REQUIRED", 401)
        membership = get_active_membership(request.user)
        if membership is None:
            return _error_response("TENANT_ACCESS_DENIED", 403)
        if membership.role != "siswa":
            return _error_response("TENANT_ACCESS_DENIED", 403)
        student = _get_student(membership)
        if student is None:
            return _error_response("TENANT_ACCESS_DENIED", 403)

        photo = request.FILES.get("foto") or request.FILES.get("photo")
        key = _idempotency_key(request)
        if not key:
            return _error_response("VALIDATION_ERROR", 422)

        try:
            day, _created, replayed = self.service(
                student=student,
                user=request.user,
                photo=photo,
                latitude=request.POST.get("latitude"),
                longitude=request.POST.get("longitude"),
                accuracy=request.POST.get("accuracy"),
                idempotency_key=key,
                endpoint=self.kind_endpoint,
            )
        except AttendanceError as exc:
            http_code = 409 if exc.code == IDEMPOTENCY_CONFLICT else 422
            if exc.code in (
                "ALREADY_CHECKED_IN",
                "ALREADY_CHECKED_OUT",
                "NOT_CHECKED_IN",
            ):
                http_code = 409
            return _error_response(exc.code, http_code)

        snapshot = attendance_day_snapshot(day)
        return JsonResponse(
            {
                "status": "accepted",
                "replayed": replayed,
                "status_attendance": snapshot["status"],
                "late_minutes": snapshot["late_minutes"],
                "attendance": snapshot,
            },
            status=200 if replayed else http_status.HTTP_201_CREATED,
        )


class CheckInView(BaseCheckView):
    kind_endpoint = "/api/v1/attendance/check-in/"
    service = staticmethod(create_check_in)


class CheckOutView(BaseCheckView):
    kind_endpoint = "/api/v1/attendance/check-out/"
    service = staticmethod(create_check_out)


class MyHistoryView(APIView):
    """GET riwayat absensi milik sendiri (pagination sederhana)."""

    def get(self, request):
        from django.http import JsonResponse

        if not request.user.is_authenticated:
            return _error_response("AUTH_REQUIRED", 401)
        membership = get_active_membership(request.user)
        if membership is None or membership.role != "siswa":
            return _error_response("TENANT_ACCESS_DENIED", 403)
        student = _get_student(membership)
        if student is None:
            return _error_response("TENANT_ACCESS_DENIED", 403)

        try:
            page = max(1, int(request.GET.get("page", 1)))
        except ValueError:
            page = 1
        page_size = min(50, max(1, int(request.GET.get("page_size", 20))))

        qs = AttendanceDay.objects.filter(
            student=student, organization=membership.organization
        ).order_by("-work_date")
        total = qs.count()
        start = (page - 1) * page_size
        rows = [
            attendance_day_snapshot(d) for d in qs[start : start + page_size]
        ]
        return JsonResponse(
            {
                "count": total,
                "page": page,
                "page_size": page_size,
                "results": rows,
            }
        )
