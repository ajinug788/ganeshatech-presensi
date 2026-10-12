"""Services master data Tahap 3: provisioning siswa + audit helper.

Logika bisnis di sini agar view HTML dan API masa depan memakai jalur yang
sama (TDIP §5.1). Semua operasi tenant-scoped dari penelepon (organization
hasil verifikasi membership, bukan input klien).
"""
import secrets

from django.db import transaction

from apps.accounts.models import User
from apps.audit.services import catat_audit
from apps.tenants.models import Membership

SISWA_TEMP_PASSWORD_LENGTH = 12
_TEMP_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%"


def generate_temp_password(length: int = SISWA_TEMP_PASSWORD_LENGTH) -> str:
    """Password sementara acak (dev convenience; wajib ganti saat login pertama)."""
    return "".join(secrets.choice(_TEMP_ALPHABET) for _ in range(length))


@transaction.atomic
def provision_student(
    *, organization, student_number, full_name, group=None,
    email=None, actor=None,
):
    """Buat StudentProfile; bila email diisi, buat akun + membership siswa.

    Satu transaksi. Password acak dikembalikan SEKALI ke pemanggil untuk
    ditampilkan di halaman sukses (dev convenience) — tidak pernah masuk log
    atau audit. email_verified_at null (DEC-01: verifikasi menyusul).
    """
    temp_password = None
    user = None
    if email:
        email = User.objects.normalize_email(email).lower()
        # Email unik platform-wide; bila sudah ada, jangan buat duplikat.
        if User.objects.filter(email=email).exists():
            raise ValueError("Email sudah terdaftar.")
        temp_password = generate_temp_password()
        user = User.objects.create_user(
            email,
            temp_password,
            email_verified_at=None,
        )
        Membership.objects.create(
            organization=organization, user=user, role=Membership.Role.SISWA
        )

    student = organization.students.create(
        student_number=student_number,
        full_name=full_name,
        group=group,
        user=user,
    )

    catat_audit(
        action="student_created",
        object_type="attendance.StudentProfile",
        object_id=student.pk,
        organization=organization,
        actor=actor,
        metadata={
            "student_number": student_number,
            "has_account": user is not None,
        },
    )
    if user is not None:
        catat_audit(
            action="account_provisioned",
            object_type="accounts.User",
            object_id=user.pk,
            organization=organization,
            actor=actor,
            metadata={"email": email, "role": "siswa"},
        )
    return student, temp_password
