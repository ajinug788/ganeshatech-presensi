from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from apps.core.views import health

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="accounts:login", permanent=False), name="home"),
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
    path(
        "api/v1/attendance/",
        include(("apps.attendance.api_urls", "attendance"), namespace="api_attendance"),
    ),
    path("reports/", include("apps.reports.urls")),
    path("", include("apps.tenants.urls")),
    # API v1 (DRF) menyusul di Tahap berikutnya:
    # path("api/v1/", include(...)),
]
