from django.contrib import admin

from .models import MediaAsset


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = (
        "storage_key",
        "organization",
        "mime_type",
        "size_bytes",
        "retention_state",
        "uploaded_at",
    )
    list_filter = ("retention_state", "organization")
    search_fields = ("storage_key", "checksum")
    readonly_fields = ("uploaded_at",)
    list_select_related = ("organization",)
