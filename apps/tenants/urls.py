from django.urls import path

from . import views

app_name = "tenants"

urlpatterns = [
    path("dashboard/superadmin/", views.dashboard_superadmin, name="dashboard_superadmin"),
    path("dashboard/siswa/", views.dashboard_siswa, name="dashboard_siswa"),
    path("dashboard/pembina/", views.dashboard_pembina, name="dashboard_pembina"),
    path("dashboard/admin/", views.dashboard_admin, name="dashboard_admin"),
    path("tanpa-membership/", views.no_membership, name="no_membership"),
]
