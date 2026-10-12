from django.urls import path

from . import views

app_name = "media_assets"

urlpatterns = [
    # Endpoint foto terotorisasi (IMG-07) — di-include di /photos/ dan /api/v1/photos/.
    path("<uuid:asset_id>/", views.ProtectedPhotoView.as_view(), name="photo"),
]
