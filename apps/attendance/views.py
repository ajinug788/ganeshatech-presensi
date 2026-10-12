"""CRUD master data Tahap 3 — server-rendered, admin organisasi saja.

Semua queryset ter-scope organization dari membership aktif
(TenantRequiredMixin + RoleRequiredMixin, TDIP §7.3).
"""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.audit.services import catat_audit
from apps.tenants.context import RoleRequiredMixin

from .forms import AttendanceLocationForm, AttendancePolicyForm, StudentForm
from .models import AttendanceLocation, AttendancePolicy, StudentProfile
from .services import provision_student


class AdminRequiredMixin(RoleRequiredMixin):
    """Mixin dasar semua endpoint master data: hanya admin organisasi."""

    allowed_roles = ("admin",)


# ---------------------------------------------------------------- Siswa


class StudentListView(AdminRequiredMixin, ListView):
    model = StudentProfile
    template_name = "attendance/student_list.html"
    paginate_by = 20

    def get_queryset(self):
        from django.db.models import Q

        qs = self.organization.students.select_related("user")
        q = self.request.GET.get("q", "").strip()
        group = self.request.GET.get("group", "").strip()
        status = self.request.GET.get("status", "").strip()
        if q:
            qs = qs.filter(Q(full_name__icontains=q) | Q(student_number__icontains=q))
        if group:
            qs = qs.filter(group=group)
        if status == "active":
            qs = qs.filter(is_active=True)
        elif status == "inactive":
            qs = qs.filter(is_active=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        ctx["group"] = self.request.GET.get("group", "")
        ctx["status"] = self.request.GET.get("status", "")
        ctx["groups"] = (
            self.organization.students.order_by("group")
            .values_list("group", flat=True)
            .distinct()
        )
        return ctx


class StudentCreateView(AdminRequiredMixin, CreateView):
    model = StudentProfile
    form_class = StudentForm
    template_name = "attendance/student_form.html"

    def get_success_url(self):
        return reverse_lazy("attendance:student_list")

    def form_valid(self, form):
        # organization dari membership aktif, bukan input klien (TEN-03).
        # Email unik platform-wide; bila sudah ada, tolak di level form.
        email = form.cleaned_data.get("email")
        if email and get_user_model().objects.filter(email=email.lower()).exists():
            form.add_error("email", "Email ini sudah terdaftar.")
            return self.form_invalid(form)
        student, temp_password = provision_student(
            organization=self.organization,
            student_number=form.cleaned_data["student_number"],
            full_name=form.cleaned_data["full_name"],
            group=form.cleaned_data["group"] or None,
            email=getattr(form, "email_for_account", None),
            actor=self.request.user,
        )
        if temp_password:
            messages.info(
                self.request,
                f"Password sementara akun {student.user.email}: {temp_password} "
                "(tampilkan sekali; wajib diganti saat login pertama).",
            )
        else:
            messages.success(self.request, "Siswa berhasil ditambahkan.")
        return redirect(self.get_success_url())


class StudentDetailView(AdminRequiredMixin, DetailView):
    model = StudentProfile
    template_name = "attendance/student_detail.html"

    def get_object(self, queryset=None):
        return get_object_or_404(
            StudentProfile, pk=self.kwargs["pk"], organization=self.organization
        )


class StudentUpdateView(AdminRequiredMixin, UpdateView):
    model = StudentProfile
    form_class = StudentForm
    template_name = "attendance/student_form.html"
    success_url = reverse_lazy("attendance:student_list")

    def get_object(self, queryset=None):
        return get_object_or_404(
            StudentProfile, pk=self.kwargs["pk"], organization=self.organization
        )

    def form_valid(self, form):
        with transaction.atomic():
            student = form.save(commit=False)
            # organization & user tidak boleh berubah via form.
            student.organization_id = self.organization.pk
            student.save()
        catat_audit(
            action="student_updated",
            object_type="attendance.StudentProfile",
            object_id=student.pk,
            organization=self.organization,
            actor=self.request.user,
            metadata={"student_number": student.student_number},
        )
        messages.success(self.request, "Data siswa diperbarui.")
        return redirect(self.success_url)


class StudentDeleteView(AdminRequiredMixin, DeleteView):
    model = StudentProfile
    template_name = "attendance/student_confirm_delete.html"
    success_url = reverse_lazy("attendance:student_list")

    def get_object(self, queryset=None):
        return get_object_or_404(
            StudentProfile, pk=self.kwargs["pk"], organization=self.organization
        )

    def form_valid(self, form):
        obj = self.get_object()
        catat_audit(
            action="student_deleted",
            object_type="attendance.StudentProfile",
            object_id=obj.pk,
            organization=self.organization,
            actor=self.request.user,
            metadata={"student_number": obj.student_number},
        )
        # Nonaktifkan alih-alih hard-delete (data absensi terkait).
        obj.is_active = False
        obj.save(update_fields=["is_active", "updated_at"])
        messages.success(self.request, "Siswa dinonaktifkan.")
        return redirect(self.success_url)


# ---------------------------------------------------------------- Lokasi


class LocationListView(AdminRequiredMixin, ListView):
    model = AttendanceLocation
    template_name = "attendance/location_list.html"
    paginate_by = 20

    def get_queryset(self):
        return self.organization.attendance_locations.all()


class LocationCreateView(AdminRequiredMixin, CreateView):
    model = AttendanceLocation
    form_class = AttendanceLocationForm
    template_name = "attendance/location_form.html"
    success_url = reverse_lazy("attendance:location_list")

    def form_valid(self, form):
        form.instance.organization = self.organization
        response = super().form_valid(form)
        catat_audit(
            action="location_created",
            object_type="attendance.AttendanceLocation",
            object_id=self.object.pk,
            organization=self.organization,
            actor=self.request.user,
            metadata={"name": self.object.name},
        )
        messages.success(self.request, "Lokasi berhasil ditambahkan.")
        return response


class LocationUpdateView(AdminRequiredMixin, UpdateView):
    model = AttendanceLocation
    form_class = AttendanceLocationForm
    template_name = "attendance/location_form.html"
    success_url = reverse_lazy("attendance:location_list")

    def get_object(self, queryset=None):
        return get_object_or_404(
            AttendanceLocation, pk=self.kwargs["pk"], organization=self.organization
        )

    def form_valid(self, form):
        response = super().form_valid(form)
        catat_audit(
            action="location_updated",
            object_type="attendance.AttendanceLocation",
            object_id=self.object.pk,
            organization=self.organization,
            actor=self.request.user,
            metadata={"name": self.object.name},
        )
        messages.success(self.request, "Lokasi diperbarui.")
        return response


class LocationDeleteView(AdminRequiredMixin, DeleteView):
    model = AttendanceLocation
    template_name = "attendance/location_confirm_delete.html"
    success_url = reverse_lazy("attendance:location_list")

    def get_object(self, queryset=None):
        return get_object_or_404(
            AttendanceLocation, pk=self.kwargs["pk"], organization=self.organization
        )

    def form_valid(self, form):
        obj = self.get_object()
        catat_audit(
            action="location_deleted",
            object_type="attendance.AttendanceLocation",
            object_id=obj.pk,
            organization=self.organization,
            actor=self.request.user,
            metadata={"name": obj.name},
        )
        # Nonaktifkan alih-alih hard-delete (record absensi merujuk lokasi).
        obj.is_active = False
        obj.save(update_fields=["is_active", "updated_at"])
        messages.success(self.request, "Lokasi dinonaktifkan.")
        return redirect(self.success_url)


# ---------------------------------------------------------------- Policy


class PolicyView(AdminRequiredMixin, UpdateView):
    """Satu kebijakan per organisasi (Tahap A): get-or-create + update."""

    model = AttendancePolicy
    form_class = AttendancePolicyForm
    template_name = "attendance/policy_form.html"
    success_url = reverse_lazy("attendance:policy")

    def get_object(self, queryset=None):
        policy, _created = AttendancePolicy.objects.get_or_create(
            organization=self.organization,
            defaults={
                "days_active": [0, 1, 2, 3, 4],
                "check_in_start": "07:00",
                "check_in_end": "09:00",
                "check_out_start": "15:00",
                "check_out_end": "17:00",
            },
        )
        return policy

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.organization
        return kwargs

    def form_valid(self, form):
        form.instance.organization = self.organization
        response = super().form_valid(form)
        catat_audit(
            action="policy_updated",
            object_type="attendance.AttendancePolicy",
            object_id=self.object.pk,
            organization=self.organization,
            actor=self.request.user,
        )
        messages.success(self.request, "Kebijakan absensi disimpan.")
        return response
