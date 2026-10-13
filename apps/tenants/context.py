"""Tenant context & otorisasi (TDIP v1.2 §7).

Prinsip: membership aktif di-resolve server-side dari user yang
terautentikasi — JANGAN percaya organization_id/slug dari request body
atau URL.
"""
from django.core.exceptions import PermissionDenied


def get_active_membership(user, organization=None):
    """Resolve membership aktif user.

    - Bila `organization` diberikan: hanya membership AKTIF pada org itu
      yang dikembalikan (memverifikasi klaim tenant, bukan mempercayainya).
    - Bila tidak: membership aktif pertama dari organisasi berstatus
      aktif (satu user bisa punya banyak membership di masa depan).
    """
    if not user or not user.is_authenticated:
        return None

    qs = user.memberships.select_related("organization").filter(
        is_active=True, organization__status="active"
    )
    if organization is not None:
        # Verifikasi keanggotaan pada tenant spesifik; ID/slug di URL bukan bukti izin.
        return qs.filter(organization=organization).first()
    return qs.order_by("created_at").first()


class TenantRequiredMixin:
    """Mixin view: wajib login + punya membership aktif.

    Menyimpan membership aktif di `self.membership` dan organisasi
    aktif di `self.organization` untuk dipakai scoping queryset.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(request.get_full_path())
        self.membership = get_active_membership(request.user)
        if self.membership is None:
            raise PermissionDenied("Anda tidak punya keanggotaan organisasi aktif.")
        self.organization = self.membership.organization
        return super().dispatch(request, *args, **kwargs)


def role_required(*roles):
    """Dekorator view: butuh membership aktif dengan salah satu role.

    Contoh: @role_required("admin", "pembina")
    """

    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login

                return redirect_to_login(request.get_full_path())
            membership = get_active_membership(request.user)
            if membership is None:
                raise PermissionDenied("Anda tidak punya keanggotaan organisasi aktif.")
            if roles and membership.role not in roles:
                raise PermissionDenied("Role Anda tidak memiliki akses ke halaman ini.")
            request.membership = membership
            request.organization = membership.organization
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


class RoleRequiredMixin(TenantRequiredMixin):
    """Versi class-based dari role_required: set `allowed_roles = (...)`."""

    allowed_roles = ()

    def dispatch(self, request, *args, **kwargs):
        # Cek role SEBELUM super().dispatch(): super() sudah menjalankan
        # handler view dan selalu mengembalikan response, sehingga cek
        # setelahnya tidak pernah dieksekusi (bug lama).
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(request.get_full_path())
        self.membership = get_active_membership(request.user)
        if self.membership is None:
            raise PermissionDenied("Anda tidak punya keanggotaan organisasi aktif.")
        self.organization = self.membership.organization
        request.membership = self.membership
        request.organization = self.organization
        if self.allowed_roles and self.membership.role not in self.allowed_roles:
            raise PermissionDenied("Role Anda tidak memiliki akses ke halaman ini.")
        return super().dispatch(request, *args, **kwargs)
