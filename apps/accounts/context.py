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
