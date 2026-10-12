"""Dashboard placeholder per role + contoh view ter-scope tenant."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.attendance.models import AttendanceDay
from apps.reports.views import build_pembina_context, build_student_home_context
from .context import TenantRequiredMixin, get_active_membership, role_required


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
    """Dashboard admin/billing (mockup Web Builder, data nyata)."""
    from apps.reports.views import build_admin_context

    ctx = build_admin_context(request.membership, request.organization)
    ctx["role_label"] = "Admin"
    return render(request, "dashboard/admin.html", ctx)


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
