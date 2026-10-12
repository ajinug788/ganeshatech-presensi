"""Dashboard placeholder per role + contoh view ter-scope tenant."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .context import TenantRequiredMixin, get_active_membership, role_required


@login_required
def dashboard_siswa(request):
    membership = get_active_membership(request.user)
    if membership is None:
        return render(request, "tenants/no_membership.html", status=403)
    return render(request, "tenants/dashboard.html", {"membership": membership, "role_label": "Siswa"})


@login_required
@role_required("pembina")
def dashboard_pembina(request):
    return render(request, "tenants/dashboard.html", {"membership": request.membership, "role_label": "Pembina"})


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
