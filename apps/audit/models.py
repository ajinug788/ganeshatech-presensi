"""Model AuditLog (TDIP v1.2 §8.2, AUD-02): append-only, tanpa data sensitif."""
import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditLog(models.Model):
    """Jejak audit append-only. Write-only dari UI; tidak boleh diubah/dihapus."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Nullable: tindakan platform (di luar tenant) tidak punya organisasi.
    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name=_("organisasi"),
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name=_("aktor"),
    )
    action = models.CharField(_("aksi"), max_length=100)
    object_type = models.CharField(_("tipe objek"), max_length=100)
    object_id = models.CharField(_("id objek"), max_length=100, blank=True)
    reason = models.TextField(_("alasan"), blank=True)
    # Tanpa secret/payload penuh/foto/koordinat presisi — disaring di service.
    metadata = models.JSONField(_("metadata"), default=dict, blank=True)
    created_at = models.DateTimeField(_("waktu"), auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("log audit")
        verbose_name_plural = _("log audit")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "-created_at"]),
            models.Index(fields=["action"]),
        ]

    def delete(self, *args, **kwargs):  # pragma: no cover - penegasan append-only
        raise ValueError("AuditLog bersifat append-only dan tidak dapat dihapus.")

    def save(self, *args, **kwargs):
        if self.pk is not None and not self._state.adding:
            # Cegah edit record yang sudah ada (append-only).
            raise ValueError("AuditLog bersifat append-only dan tidak dapat diubah.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.object_type} {self.object_id}"
