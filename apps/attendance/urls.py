from django.urls import path

from . import views

app_name = "attendance"

urlpatterns = [
    # Siswa
    path("students/", views.StudentListView.as_view(), name="student_list"),
    path("students/baru/", views.StudentCreateView.as_view(), name="student_create"),
    path("students/<uuid:pk>/", views.StudentDetailView.as_view(), name="student_detail"),
    path("students/<uuid:pk>/ubah/", views.StudentUpdateView.as_view(), name="student_update"),
    path("students/<uuid:pk>/hapus/", views.StudentDeleteView.as_view(), name="student_delete"),
    # Lokasi
    path("locations/", views.LocationListView.as_view(), name="location_list"),
    path("locations/baru/", views.LocationCreateView.as_view(), name="location_create"),
    path("locations/<uuid:pk>/ubah/", views.LocationUpdateView.as_view(), name="location_update"),
    path("locations/<uuid:pk>/hapus/", views.LocationDeleteView.as_view(), name="location_delete"),
    # Kebijakan (satu per org)
    path("policy/", views.PolicyView.as_view(), name="policy"),
    # Halaman siswa: wizard absen & riwayat
    path("absen/capture/", views.capture_page, name="capture"),
    path("absen/riwayat/", views.history_page, name="history_page"),
]
