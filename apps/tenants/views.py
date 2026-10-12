"""Dashboard placeholder per role + contoh view ter-scope tenant."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.attendance.models import (
    AttendanceDay,
    AttendanceLocation,
    AttendancePolicy,
    StudentProfile,
)
from apps.audit.models import AuditLog
from apps.audit.services import catat_audit
from apps.reports.views import build_pembina_context, build_student_dashboard_context
from .context import TenantRequiredMixin, get_active_membership, role_required
from .forms import OrganizationForm
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
        "active_page": "overview",
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


def _superadmin_only(request):
    if not (request.user.is_superuser or request.user.is_platform_admin):
        raise PermissionDenied


@login_required
def superadmin_organizations(request):
    _superadmin_only(request)
    query = request.GET.get("q", "").strip()
    organizations = Organization.objects.annotate(
        active_member_count=Count(
            "memberships", filter=Q(memberships__is_active=True), distinct=True
        ),
        active_student_count=Count(
            "students", filter=Q(students__is_active=True), distinct=True
        ),
    )
    if query:
        organizations = organizations.filter(
            Q(name__icontains=query) | Q(slug__icontains=query)
        )
    page = Paginator(organizations.order_by("name"), 15).get_page(request.GET.get("page"))
    return render(
        request,
        "tenants/superadmin_organizations.html",
        {"active_page": "organizations", "organizations": page, "query": query},
    )


@login_required
def superadmin_organization_create(request):
    _superadmin_only(request)
    return _superadmin_organization_form(request)


@login_required
def superadmin_organization_edit(request, organization_id):
    _superadmin_only(request)
    organization = get_object_or_404(Organization, pk=organization_id)
    return _superadmin_organization_form(request, organization)


def _superadmin_organization_form(request, organization=None):
    _superadmin_only(request)
    is_new = organization is None
    form = OrganizationForm(request.POST or None, instance=organization)
    if request.method == "POST" and form.is_valid():
        organization = form.save()
        catat_audit(
            action="organization_created" if is_new else "organization_updated",
            object_type="Organization",
            object_id=organization.pk,
            organization=organization,
            actor=request.user,
            metadata={"name": organization.name, "slug": organization.slug},
        )
        action_label = "ditambahkan" if is_new else "diperbarui"
        messages.success(
            request, f"Organisasi {organization.name} berhasil {action_label}."
        )
        return redirect("tenants:superadmin_organizations")
    return render(
        request,
        "tenants/superadmin_organization_form.html",
        {
            "active_page": "organizations",
            "form": form,
            "organization": organization,
            "is_new": is_new,
        },
    )


@login_required
def dashboard_siswa(request):
    membership = get_active_membership(request.user)
    if membership is None:
        return render(request, "tenants/no_membership.html", status=403)
    ctx = build_student_dashboard_context(membership)
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
    organization = request.organization
    context = build_pembina_context(request.membership, organization)
    today = context["today"]
    today_days = AttendanceDay.objects.filter(
        organization=organization, work_date=today, student__is_active=True
    )
    status_counts = {
        row["status"]: row["total"]
        for row in today_days.values("status").annotate(total=Count("id"))
    }
    checked_in = status_counts.get(AttendanceDay.Status.PRESENT, 0) + status_counts.get(
        AttendanceDay.Status.LATE, 0
    )
    context.update({
        "role_label": "Admin Sekolah",
        "is_school_admin": request.membership.role == "admin",
        "organization": organization,
        "present_on_time": status_counts.get(AttendanceDay.Status.PRESENT, 0),
        "late_today": status_counts.get(AttendanceDay.Status.LATE, 0),
        "absent_recorded": status_counts.get(AttendanceDay.Status.ABSENT, 0),
        "excused_today": status_counts.get(AttendanceDay.Status.EXCUSED, 0),
        "recorded_today": sum(status_counts.values()),
        "checked_in_today": checked_in,
        "attendance_rate": round(checked_in / context["total_siswa"] * 100, 1)
        if context["total_siswa"] else 0,
        "active_location_count": AttendanceLocation.objects.filter(
            organization=organization, is_active=True
        ).count(),
        "today_activity": today_days.select_related(
            "student", "check_in_location", "check_out_location"
        ).order_by("-updated_at")[:8],
        "recent_corrections": AuditLog.objects.filter(
            organization=organization,
            action__in=("attendance_corrected", "attendance_status_recorded"),
        ).select_related("actor").order_by("-created_at")[:4],
    })

    groups = organization.students.filter(is_active=True).values("group").annotate(
        total=Count("id")
    ).order_by("group")
    attended_by_group = dict(
        today_days.filter(status__in=[AttendanceDay.Status.PRESENT, AttendanceDay.Status.LATE])
        .values("student__group").annotate(total=Count("id"))
        .values_list("student__group", "total")
    )
    context["group_summaries"] = [
        {
            "name": row["group"] or "Belum dikelompokkan",
            "total": row["total"],
            "attended": attended_by_group.get(row["group"], 0),
            "rate": round(attended_by_group.get(row["group"], 0) / row["total"] * 100, 1)
            if row["total"] else 0,
        }
        for row in groups
    ]
    try:
        context["attendance_policy"] = organization.attendance_policy
    except AttendancePolicy.DoesNotExist:
        context["attendance_policy"] = None
    context["active_locations"] = AttendanceLocation.objects.filter(
        organization=organization, is_active=True
    ).order_by("name")[:4]
    return render(request, "dashboard/admin.html", context)


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
