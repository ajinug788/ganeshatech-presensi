"""View streaming foto terotorisasi (TDIP v1.2 §9.1, IMG-07).

Tidak ada akses publik: cek login + tenant (membership aktif) + role.
Siswa melihat foto profil ATAU foto absen miliknya sendiri; 404 bila aset
bukan milik tenant/pengguna.
"""
from django.db.models import Q
from django.http import FileResponse, Http404
from django.views.generic import View

from apps.media_assets.models import MediaAsset
from apps.media_assets.services import _key_to_path  # internal reuse, modul sama
from apps.tenants.context import get_active_membership

# Role yang boleh melihat foto (pembina/admin melihat bukti absensi siswa).
_ALLOWED_ROLES = {"admin", "pembina"}


class ProtectedPhotoView(View):
    """GET /photos/<uuid:asset_id>/ — streaming file dengan otorisasi penuh."""

    def get(self, request, asset_id):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(request.get_full_path())

        membership = get_active_membership(request.user)
        if membership is None:
            raise Http404()

        # Queryset ter-scope tenant: aset tenant lain tidak terlihat → 404.
        try:
            asset = MediaAsset.objects.get(
                pk=asset_id, organization=membership.organization
            )
        except (MediaAsset.DoesNotExist, ValueError):
            raise Http404()

        if membership.role not in _ALLOWED_ROLES and membership.role != "siswa":
            raise Http404()
        if membership.role == "siswa":
            # Siswa boleh melihat foto profilnya sendiri ATAU foto absen
            # dirinya sendiri (check-in/check-out) — riwayat tautkan ini.
            from apps.attendance.models import AttendanceDay

            owns_photo = membership.organization.students.filter(
                user=request.user, profile_photo=asset
            ).exists()
            if not owns_photo:
                owns_photo = AttendanceDay.objects.filter(
                    Q(check_in_media=asset) | Q(check_out_media=asset),
                    student__user=request.user,
                    organization=membership.organization,
                ).exists()
            if not owns_photo:
                raise Http404()

        path = _key_to_path(asset.storage_key)
        if not path.is_file():
            raise Http404()

        response = FileResponse(path.open("rb"), content_type=asset.mime_type)
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, max-age=0, no-store"
        return response
