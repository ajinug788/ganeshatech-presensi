"""URL API Tahap 5 — di-include di /api/v1/attendance/ (TDIP §9.1)."""
from django.urls import path

from . import api

app_name = "api_attendance"

urlpatterns = [
    path("check-in/", api.CheckInView.as_view(), name="check_in"),
    path("check-out/", api.CheckOutView.as_view(), name="check_out"),
    path("me/history/", api.MyHistoryView.as_view(), name="history"),
]
