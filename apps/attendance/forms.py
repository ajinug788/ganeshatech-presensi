"""Forms master data Tahap 3 (siswa, lokasi, kebijakan)."""
from datetime import timedelta

from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.utils import timezone

from apps.tenants.models import Membership

from .models import (
    AttendanceLocation,
    AttendancePolicy,
    LeaveRequest,
    Shift,
    StudentProfile,
)

DAYS = [
    (0, "Senin"), (1, "Selasa"), (2, "Rabu"), (3, "Kamis"),
    (4, "Jumat"), (5, "Sabtu"), (6, "Minggu"),
]


class StudentForm(forms.ModelForm):
    """Form siswa; email opsional → provisioning akun via service."""

    email = forms.EmailField(
        required=False,
        label="Email (opsional — bila diisi, akun siswa dibuat otomatis)",
    )
    reason = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = StudentProfile
        fields = ["student_number", "full_name", "group", "is_active"]
        # 'email' TIDAK di Meta.fields: field non-model akan dibuang
        # ModelForm._post_clean dari cleaned_data bila ikut di sana.

    def clean_email(self):
        # ModelForm._post_clean membuang field non-model dari cleaned_data;
        # simpan di atribut form agar view tetap bisa membacanya.
        self.email_for_account = self.cleaned_data.get("email") or None
        return self.email_for_account

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.user_id:
            # Akun sudah ada: tampilkan email, tidak boleh diubah via form.
            self.fields["email"].disabled = True
            self.fields["email"].initial = self.instance.user.email


class StudentProfilePhotoForm(forms.Form):
    photo = forms.ImageField(
        label="Foto profil",
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": "image/*"}),
        help_text="JPG, PNG, atau WebP. Maksimal 2 MB.",
    )


class StudentPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Kata sandi saat ini"
        self.fields["new_password1"].label = "Kata sandi baru"
        self.fields["new_password2"].label = "Ulangi kata sandi baru"
        # Django's PasswordChangeForm focuses this field by default, which
        # makes browsers jump down to the password card as soon as the page opens.
        self.fields["old_password"].widget.attrs.pop("autofocus", None)


class AttendanceLocationForm(forms.ModelForm):
    reason = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = AttendanceLocation
        fields = [
            "name", "latitude", "longitude", "radius_m", "max_accuracy_m",
            "is_active",
        ]


class AttendancePolicyForm(forms.ModelForm):
    days_active = forms.MultipleChoiceField(
        choices=DAYS, widget=forms.CheckboxSelectMultiple, label="Hari aktif"
    )
    reason = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = AttendancePolicy
        fields = [
            "days_active", "check_in_start", "check_in_end",
            "check_out_start", "check_out_end", "late_tolerance_min",
            "locations",
        ]

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is not None:
            self.fields["locations"].queryset = organization.attendance_locations.all()

    def clean_days_active(self):
        return sorted(int(d) for d in self.cleaned_data["days_active"])


class ShiftForm(forms.ModelForm):
    """Form shift: unik per organisasi (nama) + lokasi dibatasi organisasi."""

    days_active = forms.MultipleChoiceField(
        choices=DAYS, widget=forms.CheckboxSelectMultiple, label="Hari aktif"
    )
    reason = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Shift
        fields = [
            "name", "days_active", "check_in_start", "check_in_end",
            "check_out_start", "check_out_end", "late_tolerance_min",
            "locations", "is_active",
        ]

    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)
        if organization is not None:
            self.fields["locations"].queryset = organization.attendance_locations.all()

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if self.organization is None:
            return name
        qs = Shift.objects.filter(organization=self.organization, name=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Nama shift sudah dipakai di organisasi ini.")
        return name

    def clean_days_active(self):
        return sorted(int(d) for d in self.cleaned_data["days_active"])


class StudentGroupShiftForm(forms.Form):
    """Bulk: pilih grup/kelas → set shift (kosong shift = hapus penetapan)."""

    group = forms.ChoiceField(label="Kelas/kelompok")
    shift = forms.ModelChoiceField(
        queryset=Shift.objects.none(),
        required=False,
        empty_label="(tanpa shift — fallback kebijakan organisasi)",
    )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is not None:
            groups = (
                organization.students.exclude(group__isnull=True)
                .exclude(group="")
                .order_by("group")
                .values_list("group", flat=True)
                .distinct()
            )
            self.fields["group"].choices = [("", "— pilih kelas —")] + [
                (g, g) for g in groups
            ]
            self.fields["shift"].queryset = organization.shifts.filter(
                is_active=True
            )


class StudentEmailForm(forms.Form):
    """Ubah email akun siswa (validasi unik di view/service)."""

    email = forms.EmailField(label="Email baru")


class StudentSelfShiftForm(forms.Form):
    """Siswa pilih sendiri shift aktif organisasi."""

    shift = forms.ModelChoiceField(queryset=Shift.objects.none())

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is not None:
            self.fields["shift"].queryset = organization.shifts.filter(is_active=True)


# ---------------------------------------------------------------- PRD gaps


class StudentImportForm(forms.Form):
    """Impor siswa via CSV/XLSX (USER-03). Validasi ukuran di view/service."""

    file = forms.FileField(label="File CSV/XLSX")

    def clean_file(self):
        f = self.cleaned_data["file"]
        if f and f.size > 1 * 1024 * 1024:
            raise forms.ValidationError("Ukuran file melebihi 1 MB.")
        return f


class LeaveRequestForm(forms.ModelForm):
    """Pengajuan izin/sakit siswa (ATT-11); siswa hanya untuk dirinya."""

    class Meta:
        model = LeaveRequest
        fields = ["kind", "date_from", "date_to", "reason"]
        widgets = {
            "date_from": forms.DateInput(attrs={"type": "date"}),
            "date_to": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        date_from = cleaned.get("date_from")
        date_to = cleaned.get("date_to")
        if date_from and date_to and date_from > date_to:
            raise forms.ValidationError(
                "Tanggal selesai tidak boleh sebelum tanggal mulai."
            )
        # Fleksibel: izin mundur maksimal 1 hari dari hari ini.
        if date_from:
            today = timezone.localdate()
            if date_from < today - timedelta(days=1):
                raise forms.ValidationError(
                    "Tanggal mulai tidak boleh lebih dari 1 hari di masa lampau."
                )
        return cleaned


class LeaveReviewForm(forms.Form):
    """Keputusan admin/pembina atas pengajuan izin."""

    decision = forms.ChoiceField(choices=[("approve", "Setujui"), ("reject", "Tolak")])
    review_note = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3}),
        label="Catatan tinjauan",
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("decision") == "reject" and not (cleaned.get("review_note") or "").strip():
            raise forms.ValidationError("Catatan wajib diisi bila menolak.")
        return cleaned


class SupervisorAssignForm(forms.Form):
    """Assign pembina (membership role=pembina) ke lokasi (USER-04)."""

    membership = forms.ModelChoiceField(queryset=Membership.objects.none(), label="Pembina")
    location = forms.ModelChoiceField(queryset=AttendanceLocation.objects.none(), label="Lokasi")

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is not None:
            self.fields["membership"].queryset = organization.memberships.filter(
                role=Membership.Role.PEMBINA, is_active=True
            ).select_related("user")
            self.fields["location"].queryset = organization.attendance_locations.all()


class OrganizationProfileForm(forms.Form):
    """Profil organisasi (TEN-06): nama, zona waktu, toggle allow_self_shift."""

    TIMEZONE_CHOICES = [
        ("Asia/Jakarta", "Asia/Jakarta (WIB)"),
        ("Asia/Makassar", "Asia/Makassar (WITA)"),
        ("Asia/Jayapura", "Asia/Jayapura (WIT)"),
    ]

    name = forms.CharField(max_length=200, label="Nama organisasi")
    timezone = forms.ChoiceField(choices=TIMEZONE_CHOICES, label="Zona waktu")
    allow_self_shift = forms.BooleanField(
        required=False, label="Izinkan siswa memilih shift sendiri"
    )
