"""
Custom User model — email-only authentication (TDIP v1.2, DEC-01).

User adalah identitas login global (lintas tenant); keanggotaan organisasi
diatur oleh tenants.Membership. Tidak ada username; identifier login adalah
email (unik platform-wide, dinormalisasi lowercase).
"""
import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.mail import send_mail
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Email wajib diisi.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("is_platform_admin", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_platform_admin", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser harus is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser harus is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    # Field username bawaan AbstractBaseUser tidak dipakai (DEC-01).
    username = None

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(
        _("email address"),
        unique=True,
        error_messages={"unique": _("Email ini sudah terdaftar.")},
    )
    # DEC-01: verifikasi email sebelum akun aktif.
    email_verified_at = models.DateTimeField(null=True, blank=True)
    is_platform_admin = models.BooleanField(
        _("platform admin"),
        default=False,
        help_text=_("Admin platform (superadmin SaaS), bukan role organisasi."),
    )
    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Akses Django admin site."),
    )
    is_active = models.BooleanField(_("active"), default=True)
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def __str__(self):
        return self.email

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email).lower()

    def get_full_name(self):
        return self.email

    def get_short_name(self):
        return self.email

    def email_user(self, subject, message, from_email=None, **kwargs):
        send_mail(subject, message, from_email, [self.email], **kwargs)
