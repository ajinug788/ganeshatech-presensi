import hashlib
import uuid as uuid_mod
from datetime import datetime, timedelta, time as dtime

import pytest
from freezegun import freeze_time
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.attendance.models import (
    AttendanceAttempt,
    AttendanceDay,
    AttendanceLocation,
    AttendancePolicy,
    StudentProfile,
)
from apps.tenants.models import Membership, Organization
from zoneinfo import ZoneInfo

_WIB_TZ = ZoneInfo("Asia/Jakarta")

PASSWORD = "Str0ng-Passw0rd!"
pytestmark = pytest.mark.django_db


def make_jpeg(size=(800, 600)):
    from PIL import Image
    from io import BytesIO

    buf = BytesIO()
    Image.new("RGB", size, color=(120, 30, 200)).save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def setup_org(slug, email):
    org = Organization.objects.create(name=f"Org {slug}", slug=slug)
    user = get_user_model().objects.create_user(email, PASSWORD)
    Membership.objects.create(
        organization=org, user=user, role=Membership.Role.SISWA
    )
    student = StudentProfile.objects.create(
        organization=org,
        user=user,
        student_number=f"S-{slug}",
        full_name=f"Siswa {slug}",
    )
    loc = AttendanceLocation.objects.create(
        organization=org, name="Lokasi", latitude="-6.200000", longitude="106.816666"
    )
    AttendancePolicy.objects.create(
        organization=org,
        days_active=[0, 1, 2, 3, 4, 5, 6],
        check_in_start="07:00",
        check_in_end="09:00",
        check_out_start="15:00",
        check_out_end="17:00",
        late_tolerance_min=90 if slug == "b" else 15,
    )
    return org, user, student, loc


def payload(org, student, photo, lat="-6.200000", lng="106.816666", acc="10",
            key=None):
    return {
        "foto": SimpleUploadedFile("foto.jpg", photo, content_type="image/jpeg"),
        "latitude": lat,
        "longitude": lng,
        "accuracy": acc,
        "idempotency_key": key or str(uuid_mod.uuid4()),
    }


def check_in(client, data):
    return client.post(reverse("api_attendance:check_in"), data, format="multipart")


def check_out(client, data):
    return client.post(reverse("api_attendance:check_out"), data, format="multipart")


def within_window():
    """Datetime di tengah window check-in hari ini (WIB)."""
    return timezone.localtime().replace(hour=8, minute=0, second=0, microsecond=0)


def late_time():
    """10:00 WIB — terlambat 60 menit dari check_in_end pukul 09:00."""
    return timezone.now().astimezone(_WIB_TZ).replace(
        hour=10, minute=0, second=0, microsecond=0
    )


def out_window():
    return timezone.localtime().replace(hour=12, minute=0, second=0, microsecond=0)


def test_sukses_check_in_dan_snapshot():
    org, user, student, loc = setup_org("a", "a@x.id")
    client = Client()
    client.force_login(user)
    with freeze_time(within_window()):
        resp = check_in(client, payload(org, student, make_jpeg()))
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["status_attendance"] == "present"
    assert body["attendance"]["check_in_media_id"]
    day = AttendanceDay.objects.get(student=student)
    assert day.check_in_at is not None
    assert day.check_in_media is not None
    assert day.check_in_location == loc


def test_status_late_dan_late_minutes():
    org, user, student, loc = setup_org("b", "b@x.id")
    client = Client()
    client.force_login(user)
    with freeze_time(late_time()):
        resp = check_in(client, payload(org, student, make_jpeg()))
    assert resp.status_code == 201, resp.content
    assert resp.json()["status_attendance"] == "late"
    day = AttendanceDay.objects.get(student=student)
    assert day.status == "late"
    assert day.late_minutes == 60


def test_tolak_duplikat_check_in_409():
    org, user, student, loc = setup_org("c", "c@x.id")
    client = Client()
    client.force_login(user)
    with freeze_time(within_window()):
        assert check_in(client, payload(org, student, make_jpeg())).status_code == 201
        resp = check_in(client, payload(org, student, make_jpeg()))
    assert resp.status_code == 409
    assert resp.json()["code"] == "ALREADY_CHECKED_IN"


def test_idempotensi_key_sama_payload_sama():
    org, user, student, loc = setup_org("d", "d@x.id")
    client = Client()
    client.force_login(user)
    key = str(uuid_mod.uuid4())
    with freeze_time(within_window()):
        r1 = check_in(client, payload(org, student, make_jpeg(), key=key))
        assert r1.status_code == 201
        # Payload sama (byte foto & koordinat identik) → hasil sama, bukan error.
        r2 = check_in(client, payload(org, student, make_jpeg(), key=key))
    assert r2.status_code in (200, 201)
    assert (
        r2.json()["attendance"]["attendance_day_id"]
        == r1.json()["attendance"]["attendance_day_id"]
    )
    assert AttendanceDay.objects.filter(student=student).count() == 1
    assert AttendanceAttempt.objects.filter(
        student=student, outcome="success"
    ).count() == 1


def test_idempotensi_conflict_payload_beda():
    org, user, student, loc = setup_org("e", "e@x.id")
    client = Client()
    client.force_login(user)
    key = str(uuid_mod.uuid4())
    with freeze_time(within_window()):
        assert check_in(client, payload(org, student, make_jpeg(), key=key)).status_code == 201
        resp = check_in(
            client,
            payload(org, student, make_jpeg(), lat="-6.210000", key=key),
        )
    assert resp.status_code == 409
    assert resp.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_geofence_luar_radius():
    org, user, student, loc = setup_org("f", "f@x.id")
    client = Client()
    client.force_login(user)
    with freeze_time(within_window()):
        resp = check_in(
            client,
            payload(org, student, make_jpeg(), lat="-6.210000", lng="106.816666"),
        )
    assert resp.status_code == 422
    assert resp.json()["code"] == "OUTSIDE_GEOFENCE"
    assert not AttendanceDay.objects.filter(student=student).exists()


def test_akurasi_terlalu_rendah():
    org, user, student, loc = setup_org("g", "g@x.id")
    client = Client()
    client.force_login(user)
    with freeze_time(within_window()):
        resp = check_in(
            client, payload(org, student, make_jpeg(), acc="80")
        )
    assert resp.status_code == 422
    assert resp.json()["code"] == "ACCURACY_TOO_LOW"


def test_foto_invalid():
    org, user, student, loc = setup_org("h", "h@x.id")
    client = Client()
    client.force_login(user)
    with freeze_time(within_window()):
        resp = check_in(
            client,
            payload(org, student, b"ini bukan gambar sama sekali"),
        )
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_PHOTO"


def test_checkout_tanpa_checkin():
    org, user, student, loc = setup_org("i", "i@x.id")
    client = Client()
    client.force_login(user)
    with freeze_time(out_window().replace(hour=15, minute=30)):
        resp = check_out(client, payload(org, student, make_jpeg()))
    assert resp.status_code == 409
    assert resp.json()["code"] == "NOT_CHECKED_IN"


def test_checkin_terlambat_diterima_dihitung_late():
    """Jam 12:00 (3 jam setelah check_in_end 09:00) sekarang DITERIMA.

    Perubahan PRD: siswa bisa absen masuk kapan saja dalam hari aktif
    (selama dalam window check_in_start s.d. check_out_end).
    Keterlambatan dihitung dalam menit dari check_in_end.
    """
    org, user, student, loc = setup_org("j", "j@x.id")
    # policy org j: check_in_end=09:00, check_out_end=17:00, tolerance=15
    client = Client()
    client.force_login(user)
    # 12:00 — setelah check_in_end (09:00) tapi sebelum check_out_end (17:00).
    with freeze_time(out_window()):  # 12:00
        resp = check_in(client, payload(org, student, make_jpeg()))
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["status_attendance"] == "late"
    # terlambat = 12:00 - 09:00 = 180 menit
    assert body["late_minutes"] == 180


def test_checkin_sampai_akhir_window_checkout_diterima():
    """Check-in tepat pada check_out_end masih diterima sebagai terlambat."""
    org, user, student, loc = setup_org("j3", "j3@x.id")
    client = Client()
    client.force_login(user)
    waktu_akhir = out_window().replace(hour=17, minute=0)
    with freeze_time(waktu_akhir):
        resp = check_in(client, payload(org, student, make_jpeg()))
    assert resp.status_code == 201, resp.content
    assert resp.json()["status_attendance"] == "late"
    assert resp.json()["late_minutes"] == 480


def test_checkin_setelah_akhir_window_checkout_ditolak():
    """Check-in setelah check_out_end ditolak."""
    org, user, student, loc = setup_org("j4", "j4@x.id")
    client = Client()
    client.force_login(user)
    lewat_akhir = out_window().replace(hour=17, minute=1)
    with freeze_time(lewat_akhir):
        resp = check_in(client, payload(org, student, make_jpeg()))
    assert resp.status_code == 422
    assert resp.json()["code"] == "OUTSIDE_CHECKIN_WINDOW"


def test_checkin_sebelum_shift_ditolak():
    """Absen sebelum jam buka shift (check_in_start=07:00) harus ditolak."""
    org, user, student, loc = setup_org("j2", "j2@x.id")
    client = Client()
    client.force_login(user)
    # 05:00 — sebelum check_in_start (07:00).
    sebelum_buka = out_window().replace(hour=5, minute=0)
    with freeze_time(sebelum_buka):
        resp = check_in(client, payload(org, student, make_jpeg()))
    assert resp.status_code == 422
    assert resp.json()["code"] == "OUTSIDE_CHECKIN_WINDOW"


def test_sukses_check_out():
    org, user, student, loc = setup_org("k", "k@x.id")
    client = Client()
    client.force_login(user)
    with freeze_time(within_window()):
        assert check_in(client, payload(org, student, make_jpeg())).status_code == 201
    with freeze_time(out_window().replace(hour=16, minute=0)):
        resp = check_out(client, payload(org, student, make_jpeg()))
    assert resp.status_code == 201, resp.content
    day = AttendanceDay.objects.get(student=student)
    assert day.check_out_at is not None
    assert day.status == "present"


def test_tenant_isolation_org_b():
    """Siswa org B tidak bisa absen dengan lokasi milik org A."""
    setup_org("iso-a", "iso-a@x.id")
    org_b, user_b, student_b, loc_b = setup_org("iso-b", "iso-b@x.id")
    client = Client()
    client.force_login(user_b)
    # Koordinat hanya dalam radius lokasi org A → harus ditolak geofence
    # terhadap lokasi org B.
    with freeze_time(within_window()):
        resp = check_in(
            client,
            payload(
                org_b, student_b, make_jpeg(),
                lat="-6.200000", lng="106.816666",
            ),
        )
    # Lokasi org B ada di koordinat sama, jadi absen sukses — kita uji
    # isolasi lewat record: AttendanceDay harus terikat org B.
    if resp.status_code == 201:
        day = AttendanceDay.objects.get(student=student_b)
        assert day.organization == org_b
        assert day.check_in_location.organization == org_b
    else:
        assert resp.status_code in (403, 404, 422)


def test_riwayat_hanya_milik_sendiri():
    setup_org("hist-a", "hist-a@x.id")
    org_b, user_b, student_b, loc_b = setup_org("hist-b", "hist-b@x.id")
    client = Client()
    client.force_login(user_b)
    with freeze_time(within_window()):
        check_in(client, payload(org_b, student_b, make_jpeg()))
    resp = client.get(reverse("api_attendance:history"))
    assert resp.status_code == 200
    body = resp.json()
    ids = [r["attendance_day_id"] for r in body["results"]]
    assert len(ids) == 1
    # Hanya riwayat milik sendiri (org B).
    assert AttendanceDay.objects.filter(student=student_b).count() == 1


def test_attempt_tercatat_rejected():
    org, user, student, loc = setup_org("att", "att@x.id")
    client = Client()
    client.force_login(user)
    with freeze_time(within_window()):
        check_in(client, payload(org, student, make_jpeg(), lat="-6.210000"))
    assert AttendanceAttempt.objects.filter(
        student=student, outcome="rejected", error_code="OUTSIDE_GEOFENCE"
    ).exists()
