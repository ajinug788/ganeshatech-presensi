"""CRUD master data Tahap 3 — server-rendered, admin organisasi saja.

Semua queryset ter-scope organization dari membership aktif
(TenantRequiredMixin + RoleRequiredMixin, TDIP §7.3).
"""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from apps.audit.services import catat_audit
from apps.media_assets.services import hapus_file
from apps.tenants.context import RoleRequiredMixin

from .forms import (
    AttendanceLocationForm,
    AttendancePolicyForm,
    ShiftForm,
    StudentEmailForm,
    StudentForm,
    StudentGroupShiftForm,
    StudentPasswordChangeForm,
    StudentProfilePhotoForm,
    StudentSelfShiftForm,
)
from .models import (
    AttendanceDay,
    AttendanceLocation,
    AttendancePolicy,
    Shift,
    StudentProfile,
)
from .services import (
    AttendanceError,
    _store_photo,
    assign_student_shift,
    bulk_assign_shift,
    change_student_email,
    provision_student,
    reset_student_password,
    self_assign_shift,
    set_student_account_active,
    delete_leave,
    unassign_supervisor,
)


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

        qs = self.organization.students.select_related("user", "profile_photo")
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
        order = self.request.GET.get("order", "")
        allowed = {"nis": "student_number", "nama": "full_name", "kelompok": "group"}
        if order.lstrip("-").strip("-") in allowed:
            field = allowed[order.lstrip("-")]
            qs = qs.order_by(("-" + field) if order.startswith("-") else field)
        else:
            qs = qs.order_by("full_name")
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        ctx["group"] = self.request.GET.get("group", "")
        ctx["status"] = self.request.GET.get("status", "")
        ctx["order"] = self.request.GET.get("order", "")
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

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.organization
        return kwargs

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

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.organization
        return kwargs

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


# ---------------------------------------------------------------- Shift


class ShiftListView(AdminRequiredMixin, ListView):
    model = Shift
    template_name = "attendance/shift_list.html"
    paginate_by = 20

    def get_queryset(self):
        return self.organization.shifts.all()


class ShiftCreateView(AdminRequiredMixin, CreateView):
    model = Shift
    form_class = ShiftForm
    template_name = "attendance/shift_form.html"
    success_url = reverse_lazy("attendance:shift_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.organization
        return kwargs

    def form_valid(self, form):
        form.instance.organization = self.organization
        response = super().form_valid(form)
        catat_audit(
            action="shift_created",
            object_type="attendance.Shift",
            object_id=self.object.pk,
            organization=self.organization,
            actor=self.request.user,
            metadata={"name": self.object.name},
        )
        messages.success(self.request, "Shift berhasil ditambahkan.")
        return response


class ShiftUpdateView(AdminRequiredMixin, UpdateView):
    model = Shift
    form_class = ShiftForm
    template_name = "attendance/shift_form.html"
    success_url = reverse_lazy("attendance:shift_list")

    def get_object(self, queryset=None):
        return get_object_or_404(
            Shift, pk=self.kwargs["pk"], organization=self.organization
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.organization
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        catat_audit(
            action="shift_updated",
            object_type="attendance.Shift",
            object_id=self.object.pk,
            organization=self.organization,
            actor=self.request.user,
            metadata={"name": self.object.name},
        )
        messages.success(self.request, "Shift diperbarui.")
        return response


class ShiftDeleteView(AdminRequiredMixin, DeleteView):
    model = Shift
    template_name = "attendance/shift_confirm_delete.html"
    success_url = reverse_lazy("attendance:shift_list")

    def get_object(self, queryset=None):
        return get_object_or_404(
            Shift, pk=self.kwargs["pk"], organization=self.organization
        )

    def form_valid(self, form):
        obj = self.get_object()
        catat_audit(
            action="shift_deleted",
            object_type="attendance.Shift",
            object_id=obj.pk,
            organization=self.organization,
            actor=self.request.user,
            metadata={"name": obj.name},
        )
        # Soft-delete: nonaktifkan; siswa tetap fallback ke policy org via _get_rule.
        obj.is_active = False
        obj.save(update_fields=["is_active", "updated_at"])
        messages.success(self.request, "Shift dinonaktifkan.")
        return redirect(self.success_url)


class StudentGroupShiftView(AdminRequiredMixin, FormView):
    """Penetapan shift bulk: pilih grup/kelas → set shift."""

    form_class = StudentGroupShiftForm
    template_name = "attendance/student_group_shift.html"
    success_url = reverse_lazy("attendance:shift_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.organization
        return kwargs

    def form_valid(self, form):
        group = form.cleaned_data["group"]
        shift = form.cleaned_data["shift"]
        students = self.organization.students.filter(group=group)
        count = bulk_assign_shift(
            organization=self.organization,
            queryset=students,
            shift=shift,
            actor=self.request.user,
        )
        messages.success(
            self.request,
            f"Shift {count} siswa di kelas {group} diperbarui.",
        )
        return super().form_valid(form)


# ---------------------------------------------------------------- Akun siswa (AUTH-02)


def _get_student_or_404(self, pk):
    return get_object_or_404(
        StudentProfile, pk=pk, organization=self.organization
    )


class StudentAccountActiveView(AdminRequiredMixin, UpdateView):
    """Nonaktifkan/aktifkan akun siswa via POST {active: 'on'}. 404 lintas tenant."""

    model = StudentProfile
    fields = []
    template_name = "attendance/student_account_confirm.html"
    success_url = reverse_lazy("attendance:student_list")

    def get_object(self, queryset=None):
        return _get_student_or_404(self, self.kwargs["pk"])

    def form_valid(self, form):
        student = self.get_object()
        active = self.request.POST.get("active") == "on"
        try:
            set_student_account_active(
                student=student, active=active, actor=self.request.user
            )
        except ValueError as exc:
            messages.error(self.request, str(exc))
            return redirect("attendance:student_detail", pk=student.pk)
        messages.success(
            self.request,
            "Akun siswa diaktifkan." if active else "Akun siswa dinonaktifkan.",
        )
        return redirect(self.success_url)


class StudentResetPasswordView(AdminRequiredMixin, UpdateView):
    """Reset password: password acak ditampilkan SEKALI di halaman konfirmasi."""

    model = StudentProfile
    fields = []
    template_name = "attendance/student_password_reset.html"
    success_url = reverse_lazy("attendance:student_list")

    def get_object(self, queryset=None):
        return _get_student_or_404(self, self.kwargs["pk"])

    def get(self, request, *args, **kwargs):
        # Halaman konfirmasi (tanpa generate). Password hanya muncul setelah POST.
        self.object = self.get_object()
        return self.render_to_response(self.get_context_data())

    def form_valid(self, form):
        student = self.get_object()
        try:
            new_password = reset_student_password(
                student=student, actor=self.request.user
            )
        except ValueError as exc:
            messages.error(self.request, str(exc))
            return redirect("attendance:student_detail", pk=student.pk)
        return self.render_to_response(
            self.get_context_data(
                one_time_password=new_password, show_password=True
            )
        )


class StudentChangeEmailView(AdminRequiredMixin, UpdateView):
    """Ubah email akun siswa; duplikat platform-wide ditolak."""

    model = StudentProfile
    fields = []
    template_name = "attendance/student_email_form.html"
    success_url = reverse_lazy("attendance:student_list")

    def get_object(self, queryset=None):
        return _get_student_or_404(self, self.kwargs["pk"])

    def post(self, request, *args, **kwargs):
        self.object = student = self.get_object()
        form = StudentEmailForm(request.POST)
        if form.is_valid():
            try:
                change_student_email(
                    student=student,
                    new_email=form.cleaned_data["email"],
                    actor=request.user,
                )
            except ValueError as exc:
                form.add_error("email", str(exc))
            else:
                messages.success(self.request, "Email akun siswa diperbarui.")
                return redirect(self.success_url)
        return self.render_to_response(
            self.get_context_data(form=form, email_form=form)
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("email_form", StudentEmailForm())
        return ctx


class StudentShiftView(AdminRequiredMixin, UpdateView):
    """Penetapan shift per siswa (form siswa)."""

    model = StudentProfile
    fields = []
    template_name = "attendance/student_shift_form.html"
    success_url = reverse_lazy("attendance:student_detail")

    def get_object(self, queryset=None):
        return _get_student_or_404(self, self.kwargs["pk"])

    def get_success_url(self):
        if not getattr(self, "object", None):
            self.object = self.get_object()
        return reverse_lazy("attendance:student_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault(
            "shift_form",
            StudentSelfShiftForm(organization=self.organization),
        )
        return ctx

    def post(self, request, *args, **kwargs):
        student = self.get_object()
        form = StudentSelfShiftForm(
            request.POST, organization=self.organization
        )
        if form.is_valid():
            shift = form.cleaned_data["shift"]
            try:
                assign_student_shift(student=student, shift=shift, actor=request.user)
            except ValueError as exc:
                form.add_error("shift", str(exc))
            else:
                messages.success(request, "Shift siswa diperbarui.")
                return redirect(self.get_success_url())
        return self.render_to_response(
            self.get_context_data(object=student, shift_form=form)
        )


# ---------------------------------------------------------------- Halaman siswa


class StudentProfileView(RoleRequiredMixin, View):
    """Profil akun siswa: email baca-saja, foto profil, dan ubah password."""

    allowed_roles = ("siswa",)
    template_name = "attendance/student_profile.html"

    def get_student(self):
        return get_object_or_404(
            StudentProfile.objects.select_related("profile_photo", "shift"),
            organization=self.organization,
            user=self.request.user,
        )

    def get_context(self, student, *, photo_form=None, password_form=None):
        return {
            "student": student,
            "photo_form": photo_form or StudentProfilePhotoForm(),
            "password_form": password_form
            or StudentPasswordChangeForm(self.request.user),
        }

    def get(self, request, *args, **kwargs):
        student = self.get_student()
        return render(request, self.template_name, self.get_context(student))

    def post(self, request, *args, **kwargs):
        student = self.get_student()
        action = request.POST.get("action")

        if action == "change_password":
            form = StudentPasswordChangeForm(request.user, request.POST)
            if form.is_valid():
                form.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, "Kata sandi berhasil diperbarui.")
                return redirect("attendance:student_profile")
            return render(
                request,
                self.template_name,
                self.get_context(student, password_form=form),
            )

        if action == "remove_photo":
            old_photo = student.profile_photo
            student.profile_photo = None
            student.save(update_fields=["profile_photo", "updated_at"])
            self.cleanup_photo(old_photo)
            messages.success(request, "Foto profil berhasil dihapus.")
            return redirect("attendance:student_profile")

        form = StudentProfilePhotoForm(request.POST, request.FILES)
        if form.is_valid() and form.cleaned_data.get("photo"):
            old_photo = student.profile_photo
            try:
                new_photo = _store_photo(
                    organization=self.organization,
                    user=request.user,
                    django_file=form.cleaned_data["photo"],
                )
            except AttendanceError as exc:
                error_text = {
                    "PHOTO_TOO_LARGE": "Ukuran foto maksimal 2 MB.",
                    "PHOTO_REQUIRED": "Pilih foto yang akan diunggah.",
                    "INVALID_PHOTO": "File harus berupa gambar JPG, PNG, atau WebP yang valid.",
                }.get(exc.code, "Foto tidak dapat diproses.")
                form.add_error("photo", error_text)
            else:
                student.profile_photo = new_photo
                student.save(update_fields=["profile_photo", "updated_at"])
                self.cleanup_photo(old_photo)
                messages.success(request, "Foto profil berhasil diperbarui.")
                return redirect("attendance:student_profile")
        elif form.is_valid():
            form.add_error("photo", "Pilih foto terlebih dahulu.")

        return render(
            request,
            self.template_name,
            self.get_context(student, photo_form=form),
        )

    @staticmethod
    def cleanup_photo(asset):
        if asset is None:
            return
        if AttendanceDay.objects.filter(
            Q(check_in_media=asset) | Q(check_out_media=asset)
        ).exists():
            return
        if StudentProfile.objects.filter(profile_photo=asset).exists():
            return
        try:
            hapus_file(asset.storage_key)
        except FileNotFoundError:
            pass
        asset.delete()


@login_required
def shift_self_select(request):
    """Siswa pilih sendiri shift aktif (bila org.settings['allow_self_shift'])."""
    from apps.tenants.context import get_active_membership

    membership = get_active_membership(request.user)
    if membership is None:
        return render(request, "tenants/no_membership.html", status=403)
    request.membership = membership
    request.organization = membership.organization
    org = membership.organization
    if not org.settings.get("allow_self_shift", False):
        raise PermissionDenied(
            "Organisasi tidak mengizinkan pemilihan shift mandiri."
        )
    student = org.students.filter(user=request.user).first()
    if student is None:
        raise PermissionDenied("Anda bukan siswa di organisasi ini.")
    if request.method == "POST":
        form = StudentSelfShiftForm(request.POST, organization=org)
        if form.is_valid():
            try:
                self_assign_shift(
                    student=student,
                    shift=form.cleaned_data["shift"],
                    actor=request.user,
                )
            except ValueError as exc:
                form.add_error("shift", str(exc))
            else:
                messages.success(request, "Shift berhasil dipilih.")
                return redirect("attendance:shift_self_select")
    else:
        form = StudentSelfShiftForm(organization=org)
    return render(
        request,
        "attendance/shift_self_select.html",
        {"form": form, "student": student},
    )


@login_required
def capture_page(request):
    """Halaman wizard absen (kamera + GPS). JS-nya attendance.js."""
    from apps.tenants.context import get_active_membership

    membership = get_active_membership(request.user)
    if membership is None:
        return render(request, "tenants/no_membership.html", status=403)
    request.membership = membership
    request.organization = membership.organization
    kind = "check_out" if request.GET.get("type") == "checkout" else "check_in"
    return render(request, "attendance/capture.html", {"kind": kind})


@login_required
def history_page(request):
    """Halaman riwayat kehadiran siswa. JS-nya history.js (API me/history)."""
    from apps.tenants.context import get_active_membership

    membership = get_active_membership(request.user)
    if membership is None:
        return render(request, "tenants/no_membership.html", status=403)
    request.membership = membership
    request.organization = membership.organization
    return render(request, "attendance/history.html")


# =====================================================================
# PRD gaps: impor siswa (USER-03), izin/sakit (ATT-11),
# penugasan pembina (USER-04).
# =====================================================================

from .forms import (  # noqa: E402
    LeaveRequestForm,
    LeaveReviewForm,
    StudentImportForm,
    SupervisorAssignForm,
)
from .models import LeaveRequest, SupervisorAssignment  # noqa: E402
from .services import (  # noqa: E402
    apply_leave_approval,
    import_students,
    reject_leave,
)


class StudentImportView(AdminRequiredMixin, FormView):
    """Impor siswa CSV/XLSX (USER-03): all-or-nothing + ringkasan hasil."""

    form_class = StudentImportForm
    template_name = "attendance/student_import.html"

    def get_success_url(self):
        from django.urls import reverse

        return reverse("attendance:student_import_result")

    def form_valid(self, form):
        upload = form.cleaned_data["file"]
        upload.seek(0)
        file_bytes = upload.read()
        try:
            summary = import_students(
                organization=self.organization,
                file_bytes=file_bytes,
                filename=upload.name or "",
                actor=self.request.user,
            )
        except ValueError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        self.request.session["import_summary"] = summary
        return redirect(self.get_success_url())


class StudentImportResultView(AdminRequiredMixin, TemplateView):
    """Halaman ringkasan hasil impor terakhir (dari session)."""

    template_name = "attendance/student_import_result.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        summary = self.request.session.pop("import_summary", None)
        ctx["summary"] = summary
        ctx["accounts_note"] = (
            "Password akun tidak ditampilkan massal; reset password per siswa "
            "dari halaman detail siswa."
        )
        return ctx


class LeaveRequestCreateView(RoleRequiredMixin, CreateView):
    """Siswa mengajukan izin/sakit (ATT-11) — hanya untuk dirinya."""

    allowed_roles = ("siswa", "admin")
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = "attendance/leave_request_form.html"

    def get_student(self):
        student = self.organization.students.filter(user=self.request.user).first()
        if student is None and self.membership.role == "admin":
            return None
        return student

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["my_requests"] = LeaveRequest.objects.filter(
            organization=self.organization,
            student__user=self.request.user,
            archived_at__isnull=True,
        ).order_by("-created_at")
        return ctx

    def form_valid(self, form):
        student = self.organization.students.filter(user=self.request.user).first()
        if student is None:
            raise PermissionDenied("Anda bukan siswa di organisasi ini.")
        leave = form.save(commit=False)
        leave.organization = self.organization
        leave.student = student
        leave.save()
        messages.success(self.request, "Pengajuan izin terkirim, menunggu persetujuan.")
        return redirect("attendance:leave_request_create")


class LeaveReviewListView(RoleRequiredMixin, ListView):
    """Daftar pengajuan izin org (admin/pembina), filter status."""

    allowed_roles = ("admin", "pembina")
    template_name = "attendance/leave_review_list.html"
    paginate_by = 20

    def get_queryset(self):
        qs = LeaveRequest.objects.filter(
            organization=self.organization, archived_at__isnull=True
        ).select_related("student", "reviewed_by")
        status = self.request.GET.get("status", "").strip()
        if status in ("pending", "approved", "rejected"):
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status"] = self.request.GET.get("status", "")
        ctx["order"] = self.request.GET.get("order", "")
        ctx["is_admin"] = self.membership.role == "admin"
        base = LeaveRequest.objects.filter(
            organization=self.organization, archived_at__isnull=True
        )
        ctx["counts"] = {
            "all": base.count(),
            "pending": base.filter(status="pending").count(),
            "approved": base.filter(status="approved").count(),
            "rejected": base.filter(status="rejected").count(),
        }
        return ctx


class LeaveReviewActionView(RoleRequiredMixin, View):
    """APPROVE/REJECT satu pengajuan (POST); siswa tidak bisa (role gate)."""

    allowed_roles = ("admin", "pembina")

    def post(self, request, *args, **kwargs):
        leave = get_object_or_404(
            LeaveRequest, pk=kwargs["pk"], organization=self.organization
        )
        form = LeaveReviewForm(request.POST)
        if not form.is_valid():
            messages.error(request, "; ".join(form.non_field_errors()))
            return redirect("attendance:leave_review_list")
        decision = form.cleaned_data["decision"]
        try:
            if decision == "approve":
                apply_leave_approval(leave_request=leave, actor=request.user)
                messages.success(request, "Pengajuan izin disetujui.")
            else:
                reject_leave(
                    leave_request=leave,
                    actor=request.user,
                    review_note=form.cleaned_data["review_note"],
                )
                messages.success(request, "Pengajuan izin ditolak.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("attendance:leave_review_list")


class LeaveDeleteView(AdminRequiredMixin, View):
    """Hapus permanen pengajuan izin — admin saja (POST)."""

    def post(self, request, *args, **kwargs):
        leave = get_object_or_404(
            LeaveRequest, pk=kwargs["pk"], organization=self.organization
        )
        try:
            delete_leave(leave_request=leave, actor=request.user)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Pengajuan izin dihapus permanen.")
        return redirect("attendance:leave_review_list")


class SupervisorManageView(AdminRequiredMixin, TemplateView):
    """Kelola penugasan pembina per lokasi (USER-04)."""

    template_name = "attendance/supervisor_manage.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["assignments"] = SupervisorAssignment.objects.filter(
            organization=self.organization
        ).select_related("membership__user", "location")
        ctx["form"] = SupervisorAssignForm(organization=self.organization)
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action", "assign")
        if action == "unassign":
            assignment = get_object_or_404(
                SupervisorAssignment, pk=request.POST.get("assignment_pk", ""),
                organization=self.organization,
            )
            unassign_supervisor(
                organization=self.organization, assignment=assignment, actor=request.user
            )
            messages.success(request, "Penugasan pembina dilepas.")
        else:
            form = SupervisorAssignForm(request.POST, organization=self.organization)
            if form.is_valid():
                try:
                    assign_supervisor(
                        organization=self.organization,
                        membership=form.cleaned_data["membership"],
                        location=form.cleaned_data["location"],
                        actor=request.user,
                    )
                except ValueError as exc:
                    messages.error(request, str(exc))
                else:
                    messages.success(request, "Pembina ditugaskan ke lokasi.")
            else:
                messages.error(request, "Data penugasan tidak valid.")
        return redirect("attendance:supervisor_manage")
