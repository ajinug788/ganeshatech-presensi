from django import forms

from .models import Organization


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ("name", "slug", "status", "timezone")
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Contoh: SMK Ganesha TeFa"}),
            "slug": forms.TextInput(attrs={"placeholder": "smk-ganesha-tefa"}),
            "timezone": forms.TextInput(attrs={"placeholder": "Asia/Jakarta"}),
        }
        help_texts = {
            "slug": "Dipakai sebagai identitas unik organisasi.",
            "timezone": "Gunakan nama zona waktu, misalnya Asia/Jakarta.",
        }
