from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("dashboard/pembina/", views.PembinaDashboardView.as_view(), name="dashboard_pembina"),
    path("rekap/", views.RekapLaporanView.as_view(), name="rekap"),
    path("rekap/csv/", views.RekapCsvView.as_view(), name="rekap_csv"),
    path("koreksi/<uuid:pk>/", views.KoreksiAttendanceView.as_view(), name="koreksi"),
]
