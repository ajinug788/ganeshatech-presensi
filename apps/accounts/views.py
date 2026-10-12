"""Login/logout berbasis email (DEC-01) + redirect dashboard per role."""
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.views import View

from apps.audit.services import catat_audit
from apps.tenants.context import get_active_membership

from . import ratelimit

# View dashboard per role (placeholder Tahap 2).
DASHBOARD_BY_ROLE = {
    "siswa": reverse_lazy("tenants:dashboard_siswa"),
    "pembina": reverse_lazy("reports:dashboard_pembina"),
    "admin": reverse_lazy("tenants:dashboard_admin"),
    "billing": reverse_lazy("tenants:dashboard_admin"),
}


class LoginView(View):
    """Form login email+password dengan rate limit ringan per user+IP."""

    template_name = "accounts/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return HttpResponseRedirect(self._dashboard_url(request))
        return render(request, self.template_name, {"form": AuthenticationForm()})

    def post(self, request):
        identifier = (request.POST.get("username") or "").strip()
        # Field "username" pada AuthenticationForm berisi email (DEC-01).
        blocked = ratelimit.check_request(request, identifier or request.META.get("REMOTE_ADDR", ""))
        form = AuthenticationForm(request, data=request.POST)
        if blocked:
            form.errors.clear()
            return render(
                request,
                self.template_name,
                {"form": form, "rate_limited": blocked},
                status=429,
            )

        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            ratelimit.reset_failures(
                identifier, ratelimit._client_ip(request)
            )
            catat_audit(
                action="login",
                object_type="User",
                object_id=user.pk,
                actor=user,
                organization=get_active_membership(user).organization
                if get_active_membership(user)
                else None,
            )
            return HttpResponseRedirect(self._dashboard_url(request))

        # Login gagal: catat untuk rate limit (AUTH-07).
        ip = ratelimit._client_ip(request)
        ident = identifier or request.META.get("REMOTE_ADDR", "")
        ratelimit.register_failure(ident, ip)
        return render(request, self.template_name, {"form": form}, status=401)

    def _dashboard_url(self, request):
        membership = get_active_membership(request.user)
        if membership is None:
            return reverse("tenants:no_membership")
        return str(DASHBOARD_BY_ROLE.get(membership.role, reverse("tenants:no_membership")))


class LogoutView(View):
    def post(self, request):
        user = request.user if request.user.is_authenticated else None
        if user:
            catat_audit(action="logout", object_type="User", object_id=user.pk, actor=user)
        auth_logout(request)
        return HttpResponseRedirect(reverse("accounts:login"))

    # Logout via GET tidak diizinkan (CSRF).
    def get(self, request):
        return redirect_to_login(request.get_full_path())
