"""MediaAsset — metadata foto terproses (TDIP v1.2 §8.2, §11).

Hanya metadata di DB; binari ada di storage backend (private_media),
diakses via storage_key, bukan path absolut atau URL publik.
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class MediaAsset(models.Model):
    """Satu foto terproses (dinormalisasi ke JPEG) milik satu tenant."""

    class RetentionState(models.TextChoices):
        ACTIVE = "active", _("Aktif")
        PENDING_DELETE = "pending_delete", _("Menunggu Penghapusan")
        DELETED = "deleted", _("Terhapus")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="media_assets",
        verbose_name=_("organisasi"),
    )
    storage_key = models.CharField(_("storage key"), max_length=255, unique=True)
    mime_type = models.CharField(_("mime type (hasil verifikasi)"), max_length=100)
    width = models.PositiveIntegerField(_("lebar (px)"), null=True, blank=True)
    height = models.PositiveIntegerField(_("tinggi (px)"), null=True, blank=True)
    size_bytes = models.PositiveBigIntegerField(_("ukuran (byte)"), null=True, blank=True)
    checksum = models.CharField(_("checksum sha256"), max_length=64, db_index=True)
    uploaded_at = models.DateTimeField(_("diunggah"), auto_now_add=True)
    retention_state = models.CharField(
        _("status retensi"),
        max_length=30,
        choices=RetentionState.choices,
        default=RetentionState.ACTIVE,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="media_assets_uploaded",
        verbose_name=_("diunggah oleh"),
    )

    class Meta:
        verbose_name = _("aset media")
        verbose_name_plural = _("aset media")
        indexes = [
            models.Index(fields=["organization", "uploaded_at"]),
        ]

    def __str__(self):
        return f"{self.storage_key} @ {self.organization_id}"
