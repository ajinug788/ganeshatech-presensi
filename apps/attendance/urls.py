from django.urls import path

from . import views
app_name = "attendance"

urlpatterns = [
    # Siswa
    path("profil/", views.StudentProfileView.as_view(), name="student_profile"),
    path("students/", views.StudentListView.as_view(), name="student_list"),
    path("students/baru/", views.StudentCreateView.as_view(), name="student_create"),
    path("students/<uuid:pk>/", views.StudentDetailView.as_view(), name="student_detail"),
    path("students/<uuid:pk>/ubah/", views.StudentUpdateView.as_view(), name="student_update"),
    path("students/<uuid:pk>/hapus/", views.StudentDeleteView.as_view(), name="student_delete"),
    # Akun siswa (AUTH-02)
    path(
        "students/<uuid:pk>/akun/status/",
        views.StudentAccountActiveView.as_view(),
        name="student_account_active",
    ),
    path(
        "students/<uuid:pk>/akun/reset-password/",
        views.StudentResetPasswordView.as_view(),
        name="student_reset_password",
    ),
    path(
        "students/<uuid:pk>/akun/email/",
        views.StudentChangeEmailView.as_view(),
        name="student_change_email",
    ),
    path(
        "students/<uuid:pk>/shift/",
        views.StudentShiftView.as_view(),
        name="student_shift",
    ),
    # Lokasi
    path("locations/", views.LocationListView.as_view(), name="location_list"),
    path("locations/baru/", views.LocationCreateView.as_view(), name="location_create"),
    path("locations/<uuid:pk>/ubah/", views.LocationUpdateView.as_view(), name="location_update"),
    path("locations/<uuid:pk>/hapus/", views.LocationDeleteView.as_view(), name="location_delete"),
    # Kebijakan (satu per org)
    path("policy/", views.PolicyView.as_view(), name="policy"),
    # Shift (multi-shift)
    path("shifts/", views.ShiftListView.as_view(), name="shift_list"),
    path("shifts/baru/", views.ShiftCreateView.as_view(), name="shift_create"),
    path("shifts/<uuid:pk>/ubah/", views.ShiftUpdateView.as_view(), name="shift_update"),
    path("shifts/<uuid:pk>/hapus/", views.ShiftDeleteView.as_view(), name="shift_delete"),
    path(
        "shifts/penetapan/",
        views.StudentGroupShiftView.as_view(),
        name="student_group_shift",
    ),
    path(
        "shift/pilih/",
        views.shift_self_select,
        name="shift_self_select",
    ),
    # Halaman siswa: wizard absen & riwayat
    path("absen/capture/", views.capture_page, name="capture"),
    path("absen/riwayat/", views.history_page, name="history_page"),
    # Impor siswa (USER-03)
    path("students/impor/", views.StudentImportView.as_view(), name="student_import"),
    path("students/impor/hasil/", views.StudentImportResultView.as_view(), name="student_import_result"),
    # Pengajuan izin/sakit (ATT-11)
    path("izin/ajukan/", views.LeaveRequestCreateView.as_view(), name="leave_request_create"),
    path("izin/tinjau/", views.LeaveReviewListView.as_view(), name="leave_review_list"),
    path("izin/<uuid:pk>/tinjau/", views.LeaveReviewActionView.as_view(), name="leave_review_action"),
    # Penugasan pembina (USER-04)
    path("pembina-penjaga/", views.SupervisorManageView.as_view(), name="supervisor_manage"),

]
