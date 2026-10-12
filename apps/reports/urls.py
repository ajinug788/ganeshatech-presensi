from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("dashboard/pembina/", views.PembinaDashboardView.as_view(), name="dashboard_pembina"),
    path("audit/", views.AuditHistoryView.as_view(), name="audit_history"),
    path("status-siswa/<uuid:student_id>/", views.AttendanceStatusCreateView.as_view(), name="status_record"),
    path("rekap/", views.RekapLaporanView.as_view(), name="rekap"),
    path("rekap/csv/", views.RekapCsvView.as_view(), name="rekap_csv"),
    path("koreksi/<uuid:pk>/", views.KoreksiAttendanceView.as_view(), name="koreksi"),
]
