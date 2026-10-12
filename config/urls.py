from django.contrib import admin
from django.urls import include, path

from apps.core.views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", health, name="health"),
    # API v1 (DRF) menyusul di Tahap berikutnya:
    # path("api/v1/", include(...)),
]
