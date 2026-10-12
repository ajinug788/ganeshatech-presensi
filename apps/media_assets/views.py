"""View streaming foto terotorisasi (TDIP v1.2 §9.1, IMG-07).

Tidak ada akses publik: cek login + tenant (membership aktif) + role +
kepemilikan foto terhadap tenant sebelum streaming file. 404 bila bukan
milik tenant (tanpa membocorkan keberadaan aset).
"""
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
        if membership is None or membership.role not in _ALLOWED_ROLES:
            raise Http404()

        # Queryset ter-scope tenant: aset tenant lain tidak terlihat → 404.
        try:
            asset = MediaAsset.objects.get(
                pk=asset_id, organization=membership.organization
            )
        except (MediaAsset.DoesNotExist, ValueError):
            raise Http404()

        path = _key_to_path(asset.storage_key)
        if not path.is_file():
            raise Http404()

        response = FileResponse(path.open("rb"), content_type=asset.mime_type)
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, max-age=0, no-store"
        return response
