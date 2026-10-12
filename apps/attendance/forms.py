"""Forms master data Tahap 3 (siswa, lokasi, kebijakan)."""
from django import forms

from .models import AttendanceLocation, AttendancePolicy, Shift, StudentProfile

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
