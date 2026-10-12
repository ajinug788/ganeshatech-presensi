"""Dashboard placeholder per role + contoh view ter-scope tenant."""
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from apps.attendance.models import AttendanceDay, StudentProfile
from apps.audit.models import AuditLog
from apps.reports.views import build_pembina_context, build_student_home_context
from .context import TenantRequiredMixin, get_active_membership, role_required
from .models import Organization


@login_required
def dashboard_superadmin(request):
    """Ringkasan lintas tenant khusus admin platform."""
    if not (request.user.is_superuser or request.user.is_platform_admin):
        raise PermissionDenied

    today = timezone.localdate()
    organizations = Organization.objects.annotate(
        active_member_count=Count(
            "memberships", filter=Q(memberships__is_active=True), distinct=True
        ),
        active_student_count=Count(
            "students", filter=Q(students__is_active=True), distinct=True
        ),
    ).order_by("-created_at")
    status_counts = {
        row["status"]: row["total"]
        for row in Organization.objects.values("status").annotate(total=Count("id"))
    }
    context = {
        "today": today,
        "organization_count": Organization.objects.count(),
        "active_organization_count": status_counts.get(Organization.Status.AKTIF, 0),
        "inactive_organization_count": status_counts.get(Organization.Status.DITANGGUHKAN, 0)
        + status_counts.get(Organization.Status.DITUTUP, 0),
        "active_user_count": get_user_model().objects.filter(is_active=True).count(),
        "active_student_count": StudentProfile.objects.filter(is_active=True).count(),
        "today_attendance_count": AttendanceDay.objects.filter(
            work_date=today, check_in_at__isnull=False
        ).count(),
        "organizations": organizations[:8],
        "recent_audit_logs": AuditLog.objects.select_related(
            "actor", "organization"
        ).order_by("-created_at")[:6],
    }
    return render(request, "tenants/superadmin_dashboard.html", context)


@login_required
def dashboard_siswa(request):
    membership = get_active_membership(request.user)
    if membership is None:
        return render(request, "tenants/no_membership.html", status=403)
    ctx = build_student_home_context(membership)
    ctx["role_label"] = "Siswa"
    return render(request, "tenants/dashboard.html", ctx)


@login_required
@role_required("pembina")
def dashboard_pembina(request):
    """Dashboard pembina nyata (Tahap 6) di endpoint lama /dashboard/pembina/."""
    ctx = build_pembina_context(request.membership, request.organization)
    ctx["role_label"] = "Pembina"
    return render(request, "dashboard/pembina.html", ctx)


@login_required
@role_required("admin", "billing")
def dashboard_admin(request):
    return render(request, "tenants/dashboard.html", {"membership": request.membership, "role_label": "Admin"})


@login_required
def no_membership(request):
    """Akun login tapi tidak punya membership organisasi aktif."""
    return render(request, "tenants/no_membership.html", status=403)


class TenantExampleListView(TenantRequiredMixin):
    """Contoh view class-based yang selalu scope ke organisasi aktif.

    Pattern yang wajib ditiru modul lain: data diambil melalui relasi
    organisasi aktif hasil verifikasi membership — bukan parameter URL/body.
    """

    template_name = "tenants/dashboard.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {"membership": self.membership, "role_label": self.membership.get_role_display()},
        )
