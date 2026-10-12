"""Model Tahap 3 — Master data (TDIP v1.2 §8.2).

StudentProfile, AttendanceLocation, AttendancePolicy. Semua tabel milik
tenant punya organization FK (ARC-05).
"""
import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.tenants.models import Organization


def validate_days_active(value):
    """days_active: list int 0-6 (0=Senin .. 6=Minggu)."""
    if not isinstance(value, list):
        raise ValidationError(_("days_active harus berupa list angka."))
    for day in value:
        if not isinstance(day, int) or not 0 <= day <= 6:
            raise ValidationError(_("Setiap hari harus bilangan bulat 0-6."))
    if len(set(value)) != len(value):
        raise ValidationError(_("Tidak boleh ada hari yang duplikat."))


class StudentProfile(models.Model):
    """Profil siswa per organisasi; user nullable (siswa tanpa akun)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="students",
        verbose_name=_("organisasi"),
    )
    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_profiles",
        verbose_name=_("akun pengguna"),
        help_text=_("Kosong bila siswa belum punya akun (provisioning nanti)."),
    )
    student_number = models.CharField(_("nomor induk siswa"), max_length=50)
    full_name = models.CharField(_("nama lengkap"), max_length=200)
    group = models.CharField(_("kelas/kelompok"), max_length=100, null=True, blank=True)
    is_active = models.BooleanField(_("aktif"), default=True)
    created_at = models.DateTimeField(_("dibuat"), auto_now_add=True)
    updated_at = models.DateTimeField(_("diubah"), auto_now=True)

    class Meta:
        verbose_name = _("profil siswa")
        verbose_name_plural = _("profil siswa")
        ordering = ["full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "student_number"],
                name="uniq_student_number_per_org",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "is_active"]),
            models.Index(fields=["organization", "group"]),
        ]

    def __str__(self):
        return f"{self.student_number} - {self.full_name}"

    def clean(self):
        super().clean()
        if self.user_id:
            existing = StudentProfile.objects.filter(user=self.user)
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError(_("Siswa ini sudah terhubung ke profil lain."))


class AttendanceLocation(models.Model):
    """Lokasi geofence absensi (GEO-01)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="attendance_locations",
        verbose_name=_("organisasi"),
    )
    name = models.CharField(_("nama lokasi"), max_length=200)
    latitude = models.DecimalField(
        _("latitude"),
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        _("longitude"),
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    radius_m = models.PositiveIntegerField(
        _("radius (meter)"),
        default=100,
        help_text=_("Default 100 m (DEC-04); dapat diubah admin."),
    )
    max_accuracy_m = models.PositiveIntegerField(
        _("akurasi GPS maksimum (meter)"),
        default=50,
        help_text=_("Default 50 m (DEC-04); dapat diubah admin."),
    )
    is_active = models.BooleanField(_("aktif"), default=True)
    created_at = models.DateTimeField(_("dibuat"), auto_now_add=True)
    updated_at = models.DateTimeField(_("diubah"), auto_now=True)

    class Meta:
        verbose_name = _("lokasi absensi")
        verbose_name_plural = _("lokasi absensi")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["organization", "is_active"]),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        # Validasi koordinat/radius (TDIP §8.2): juga di sini, bukan hanya form.
        if self.latitude is not None and not (-90 <= self.latitude <= 90):
            raise ValidationError({"latitude": _("Latitude harus -90..90.")})
        if self.longitude is not None and not (-180 <= self.longitude <= 180):
            raise ValidationError({"longitude": _("Longitude harus -180..180.")})
        if self.radius_m is not None and self.radius_m <= 0:
            raise ValidationError({"radius_m": _("Radius harus lebih dari 0 meter.")})
        if self.max_accuracy_m is not None and self.max_accuracy_m <= 0:
            raise ValidationError(
                {"max_accuracy_m": _("Akurasi maksimum harus lebih dari 0 meter.")}
            )


class AttendancePolicy(models.Model):
    """Kebijakan absensi per organisasi (Tahap A: satu per org)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name="attendance_policy",
        verbose_name=_("organisasi"),
    )
    # JSON list int 0-6 agar kompatibel SQLite dev; ArrayField PostgreSQL menyusul.
    days_active = models.JSONField(
        _("hari aktif"), default=list, validators=[validate_days_active]
    )
    check_in_start = models.TimeField(_("mulai check-in"))
    check_in_end = models.TimeField(_("akhir check-in"))
    check_out_start = models.TimeField(_("mulai check-out"))
    check_out_end = models.TimeField(_("akhir check-out"))
    late_tolerance_min = models.PositiveIntegerField(
        _("toleransi terlambat (menit)"), default=15
    )
    # Kosong = semua lokasi aktif berlaku.
    locations = models.ManyToManyField(
        AttendanceLocation,
        blank=True,
        related_name="policies",
        verbose_name=_("lokasi yang berlaku"),
        help_text=_("Kosong = semua lokasi aktif organisasi berlaku."),
    )
    created_at = models.DateTimeField(_("dibuat"), auto_now_add=True)
    updated_at = models.DateTimeField(_("diubah"), auto_now=True)

    class Meta:
        verbose_name = _("kebijakan absensi")
        verbose_name_plural = _("kebijakan absensi")

    def __str__(self):
        return f"Kebijakan absensi {self.organization}"

    def clean(self):
        super().clean()
        validate_days_active(self.days_active)
        if self.check_in_start and self.check_in_end and self.check_in_start >= self.check_in_end:
            raise ValidationError(
                {"check_in_end": _("Akhir check-in harus setelah mulai check-in.")}
            )
        if (
            self.check_out_start
            and self.check_out_end
            and self.check_out_start >= self.check_out_end
        ):
            raise ValidationError(
                {"check_out_end": _("Akhir check-out harus setelah mulai check-out.")}
            )
