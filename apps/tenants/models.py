"""Model tenant: Organization + Membership (TDIP v1.2 §8.2, ARC-05)."""
import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Organization(models.Model):
    """Satu sekolah/unit TeFa pelanggan (tenant)."""

    class Status(models.TextChoices):
        AKTIF = "active", _("Aktif")
        DITANGGUHKAN = "suspended", _("Ditangguhkan")
        DITUTUP = "closed", _("Ditutup")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("nama organisasi"), max_length=200)
    slug = models.SlugField(_("slug"), unique=True, max_length=100)
    status = models.CharField(
        _("status"), max_length=20, choices=Status.choices, default=Status.AKTIF
    )
    timezone = models.CharField(_("zona waktu"), max_length=64, default="Asia/Jakarta")
    # Pengaturan tenant: radius default, akurasi maks, jam efektif, dsb.
    settings = models.JSONField(_("pengaturan"), default=dict, blank=True)
    created_at = models.DateTimeField(_("dibuat"), auto_now_add=True)

    class Meta:
        verbose_name = _("organisasi")
        verbose_name_plural = _("organisasi")
        ordering = ["name"]

    def __str__(self):
        return self.name


class Membership(models.Model):
    """Keanggotaan user pada satu organisasi dengan role (TDIP §7.1)."""

    class Role(models.TextChoices):
        ADMIN = "admin", _("Admin organisasi")
        PEMBINA = "pembina", _("Pembina")
        SISWA = "siswa", _("Siswa")
        BILLING = "billing", _("Billing")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("organisasi"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("pengguna"),
    )
    role = models.CharField(_("role"), max_length=20, choices=Role.choices)
    # Kelompok/lokasi yang ditugaskan (mis. {"groups": ["10A"]}) — nullable.
    scope = models.JSONField(_("scope"), null=True, blank=True)
    is_active = models.BooleanField(_("aktif"), default=True)
    created_at = models.DateTimeField(_("dibuat"), auto_now_add=True)

    class Meta:
        verbose_name = _("membership")
        verbose_name_plural = _("membership")
        # Invarian TDIP §8.2: satu user satu membership per organisasi.
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"], name="uniq_membership_org_user"
            )
        ]
        indexes = [
            models.Index(fields=["organization", "role"]),
        ]

    def __str__(self):
        return f"{self.user} @ {self.organization} ({self.role})"
