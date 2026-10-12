from django import forms

from apps.attendance.models import AttendanceDay


class AttendanceStatusForm(forms.Form):
    status = forms.ChoiceField(
        label="Keterangan",
        choices=(
            (AttendanceDay.Status.ABSENT, "Tidak hadir"),
            (AttendanceDay.Status.EXCUSED, "Izin"),
        ),
    )
    reason = forms.CharField(
        label="Catatan verifikasi",
        min_length=5,
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Tuliskan sumber konfirmasi atau alasan pencatatan."}),
        help_text="Catatan ini disimpan di audit log bersama nama admin dan waktu pencatatan.",
    )
