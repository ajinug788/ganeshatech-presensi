from django.contrib import admin
from django.urls import include, path

from apps.core.views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", health, name="health"),
    path("accounts/", include("apps.accounts.urls")),
    path("attendance/", include("apps.attendance.urls")),
    path("photos/", include(("apps.media_assets.urls", "media_assets"), namespace="photos")),
    # Endpoint foto versi API (IMG-07) — masih view terotorisasi yang sama.
    path(
        "api/v1/photos/",
        include(("apps.media_assets.urls", "media_assets"), namespace="api_photos"),
    ),
    path("", include("apps.tenants.urls")),
    # API v1 (DRF) menyusul di Tahap berikutnya:
    # path("api/v1/", include(...)),
]
