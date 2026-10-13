def total_siswa(request):
    """Jumlah siswa aktif organisasi — dipakai sidebar admin (base.html),
    disamakan dengan sidebar Ringkasan (admin.html)."""
    org = getattr(request, "organization", None)
    if org is None:
        return {}
    try:
        return {"total_siswa": org.students.filter(is_active=True).count()}
    except Exception:
        return {}


PAGE_TITLES = {
    "rekap": "Rekap absensi",
    "rekap_csv": "Laporan & ekspor CSV",
    "koreksi": "Koreksi absensi",
    "riwayat_koreksi": "Riwayat koreksi & audit",
    "student_list": "Master siswa",
    "student_create": "Master siswa",
    "student_detail": "Master siswa",
    "student_update": "Master siswa",
    "student_delete": "Master siswa",
    "student_shift": "Master siswa",
    "location_list": "Titik geofence",
    "location_create": "Titik geofence",
    "location_update": "Titik geofence",
    "location_delete": "Titik geofence",
    "shift_list": "Pengaturan shift",
    "shift_create": "Pengaturan shift",
    "shift_update": "Pengaturan shift",
    "shift_delete": "Pengaturan shift",
    "student_group_shift": "Pengaturan shift",
    "policy": "Kebijakan organisasi",
    "leave_review_list": "Tinjau izin",
}


def page_title(request):
    match = getattr(request, "resolver_match", None)
    name = match.url_name if match else None
    return {"page_title": PAGE_TITLES.get(name, "")}
