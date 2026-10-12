---
title: "TECHNICAL DESIGN & IMPLEMENTATION PLAN"
subtitle: "Platform Absensi dan Manajemen Teaching Factory (TeFa)"
author: "Dokumen Teknis — v1.0"
date: "12 Oktober 2026"
---

# Informasi Dokumen

| Atribut | Isi |
|---|---|
| Nama produk | Platform Absensi dan Manajemen TeFa (nama kerja) |
| Versi dokumen | TDIP 1.0 |
| Referensi | PRD Platform Absensi TeFa v1.0 (12 Oktober 2026) |
| Status | Dokumen teknis pendamping PRD; nilai yang berasal dari usulan PRD ditandai **(default, bisa diubah)** |
| Bahasa | Bahasa Indonesia |
| Deployment awal | VPS Tencent 43.157.205.8, user `tefa`, folder `~/ganeshatech-presensi` |

> **Konvensi:** kebutuhan MUST/SHOULD mengikuti makna pada PRD. Nilai konfigurasi default adalah titik awal untuk divalidasi, bukan keputusan final. Dokumen ini tidak mengubah kebutuhan PRD; jika ada konflik, PRD yang berlaku.

# 1. Tujuan dan Ruang Lingkup Dokumen

Dokumen ini menerjemahkan PRD v1.0 menjadi keputusan teknis konkret dan rencana implementasi:

1. Arsitektur sistem dan pemecahan modul aplikasi Django.
2. Skema data awal (model, constraint, indeks) untuk pilot dan fondasi SaaS.
3. Desain API internal yang akan dipakai web sekarang dan aplikasi mobile nanti.
4. Alur teknis inti: absensi, geofence, foto, koreksi, billing.
5. Struktur proyek, konfigurasi environment, dan deployment di VPS yang sama dengan layanan lain.
6. Strategi pengujian, keamanan, observabilitas, backup, dan urutan pengerjaan bertahap (Tahap A pilot → Tahap B SaaS komersial).

Yang **tidak** termasuk: desain UI final (mengikuti PRD §8), pilihan provider pembayaran final (PRD §17), dan implementasi aplikasi mobile.

# 2. Ringkasan Arsitektur

## 2.1 Diagram logis

```
[Browser HP siswa/pembina/admin]
        │  HTTPS
        ▼
[Nginx (reverse proxy, TLS, static)]
        ▼
[Gunicorn] ──► [Django app]
                ├── core          (settings, urls, wsgi)
                ├── accounts      (User, Membership, auth, role)
                ├── tenants       (Organization, isolasi, status tenant)
                ├── attendance    (lokasi, jadwal, sesi, record, koreksi)
                ├── media_photos  (MediaAsset, validasi/normalisasi, storage abstrak)
                ├── reports       (dashboard, rekap, ekspor CSV/XLSX)
                ├── audit         (AuditLog)
                ├── billing       (Plan, Subscription, Invoice, PaymentTransaction, webhook)  [Tahap B]
                └── notifications (in-app; kanal eksternal menyusul)                          [P1]
        ▼
[PostgreSQL]        [Media storage: filesystem lokal → S3-compatible (abstraksi Django STORAGES)]
```

## 2.2 Keputusan arsitektur

| # | Keputusan | Alasan | Sumber |
|---|---|---|---|
| A1 | Django monolith modular (apps per domain), tanpa microservice | Skala kecil, tim kecil, PRD §10.2 | PRD §10.2 |
| A2 | Django Templates server-rendered + JS modular (vanilla ES modules) untuk web siswa/pembina | Cepat untuk MVP; kamera/geolocation/kompresi cukup dengan API browser | PRD §10.2 |
| A3 | DRF untuk endpoint `/api/v1/` yang dipakai web dan calon mobile | Konsistensi logika bisnis lintas klien | PRD §10.2, §10.3 |
| A4 | PostgreSQL sebagai satu-satunya datastore; media di luar DB | Data relasional + multi-tenant; binari besar tidak di DB (PRD §9.1) | PRD §10.2, §9.1 |
| A5 | Isolasi tenant via kolom `organization_id` + manager/queryset yang memaksa scope | Sederhana dan dapat diuji untuk skala ini; Row-Level Security ditunda hingga ada kebutuhan | PRD §6.2 |
| A6 | Redis/worker (Celery) ditunda; pekerjaan asinkron pilot dilakukan sinkron atau management command | PRD §10.2 menyatakan belum wajib untuk pilot | PRD §10.2 |
| A7 | Storage file via `STORAGES` Django (filesystem lokal default, S3-compatible via django-storages nanti) | IMG-08: abstraksi storage tanpa ubah logika | PRD §6.6 IMG-08 |
| A8 | Pembayaran via adapter interface `PaymentProvider` (implementasi provider menyusul, Tahap B) | BILL-05 | PRD §6.8 |
| A9 | API versioning `/api/v1/` sejak awal | PRD §10.3 | PRD §10.3 |

# 3. Lingkungan Deployment (VPS bersama)

## 3.1 Batasan VPS

VPS Tencent `43.157.205.8` juga menjalankan:
- Company profile website di `~/ganesha-tech`
- Flask WA app di `/opt/ganeshatech-wa`

Aturan keras:
1. Tidak boleh mengubah konfigurasi, file, port, atau layanan milik dua aplikasi lain itu.
2. Semua milik proyek ini berada di bawah user `tefa`, folder `~/ganeshatech-presensi`.
3. Port dan nama service unik; tidak memakai port yang sudah dipakai aplikasi lain (cek `sudo ss -tlnp` sebelum menetapkan).
4. Nginx hanya ditambah server block baru dengan `server_name` berbeda; jangan menyentuh konfigurasi existing.

## 3.2 Struktur server

```
/home/tefa/ganeshatech-presensi/
├── repo/          # git working tree (branch main)
├── venv/          # virtualenv terpisah khusus proyek ini (Python 3.12)
├── media/         # foto terproses (di luar webroot publik) — IMG-07
├── static/        # collectstatic output
├── logs/
├── backups/       # output pg_dump terjadwal
└── .env           # konfigurasi sensitif (600, milik tefa)
```

## 3.3 Langkah provisioning (dilakukan sekali, terdokumentasi sebagai script/checklist)

1. `sudo apt update && sudo apt install -y postgresql postgresql-contrib` — PostgreSQL perlu diinstall di VPS.
2. Buat DB + user khusus: `CREATE DATABASE ganeshatech_presensi; CREATE USER presensi_app WITH PASSWORD <dari .env>; GRANT ...` — password di-generate, disimpan di `.env`, tidak pernah masuk repo.
3. `python3 -m venv ~/ganeshatech-presensi/venv` (TIDAK memakai venv milik aplikasi lain).
4. Install dependensi: `pip install -r requirements/production.txt`.
5. Gunicorn sebagai systemd unit user baru: `presensi.service` (User=tefa, WorkingDirectory=repo, socket/port lokal unik, mis. 127.0.0.1:8010 — final setelah cek port bebas).
6. Nginx: server block baru, proxy_pass ke Gunicorn, `client_max_body_size` disetel ke batas upload foto + margin (default 5 MB, bisa diubah), TLS via certbot untuk domain produksi.
7. Firewall: buka hanya 80/443; PostgreSQL hanya listen `127.0.0.1`.
8. Cron user tefa: backup `pg_dump` harian + rotasi, housekeeping media/retensi.

## 3.4 Environment

| Env | Lokasi | Tujuan |
|---|---|---|
| development | lokal/VM pengembang | iterasi fitur |
| production | VPS 43.157.205.8, user `tefa` | pilot TeFa, lalu SaaS |

(Staging ditambahkan sebelum Tahap B bila memungkinkan; sampai itu, pengujian perilaku berbahaya dilakukan lokal dengan dump data anonim.)

Konfigurasi via `.env` (django-environ): `SECRET_KEY`, `DATABASE_URL`, `DEBUG`, `ALLOWED_HOSTS`, `MEDIA_*`, batas upload, flag fitur billing, kredensial payment gateway (Tahap B). Tidak ada secret di repo (PRD §11 poin 4, §13.2).

# 4. Stack dan Versi

| Komponen | Pilihan | Catatan |
|---|---|---|
| Python | 3.12 | sesuai VPS |
| Django | 5.x LTS | admin, auth, migrasi |
| DRF | 3.15+ | API `/api/v1/` |
| PostgreSQL | 16 (versi default repo apt; minimum 14) | TZ-aware timestamps |
| Gunicorn + Nginx | sesuai apt/pip | PRD §10.2 |
| PIL (Pillow) | untuk validasi/decode & normalisasi foto | IMG-04/05 |
| openpyxl | ekspor XLSX (opsional pilot) | REP-03 |
| redis/Celery | TIDAK di pilot | A6 |
| django-storages | Tahap B (object storage) | A7 |

`requirements/base.txt`, `requirements/production.txt`, `requirements/dev.txt` terpisah.

# 5. Desain Data

## 5.1 Prinsip

- Semua tabel milik tenant punya `organization` FK (indexed). Query hanya lewat manager yang memaksa scope tenant (A5).
- Timestamps: `models.DateTimeField` TZ-aware (UTC di DB); tampilan dikonversi ke zona waktu tenant (PRD §7.1).
- Uang: `DecimalField(max_digits=12, decimal_places=0)` untuk IDR (rupiah bulat) — PRD §9.1.
- Foto: hanya metadata di DB (MediaAsset), binari di storage backend — PRD §9.1.
- Audit log tidak di-CASCADE-delete.

## 5.2 Model Tahap A (pilot)

`tenants.Organization`
- `id (uuid)`, `name`, `slug (unique)`, `status` [active, suspended, closed], `timezone` (default `Asia/Jakarta`), `settings JSONB` (radius default, akurasi maks, jam efektif), `created_at`.

`accounts.User`
- Custom user (AbstractBaseUser + PermissionsMixin): `username (unique)`, `password (hash)`, `is_platform_admin`, `is_active`, `created_at`. Siswa login pakai ID siswa sebagai username — **(default, bisa diubah; PRD §17)**.

`accounts.Membership` — (unique `[organization, user]`)
- `organization`, `user`, `role` [admin, pembina, siswa, billing], `scope JSONB` (kelompok/lokasi yang ditugaskan), `is_active`.

`attendance.StudentProfile`
- `organization`, `user (OneToOne, nullable untuk data siswa tanpa akun)`, `student_number (unique per org)`, `full_name`, `group` (kelas/kelompok, nullable), `is_active`.

`attendance.AttendanceLocation`
- `organization`, `name`, `latitude (DecimalField 9,6)`, `longitude`, `radius_m` (default 100 — **default, bisa diubah**), `max_accuracy_m` (default 50 — **default, bisa diubah**), `is_active`.

`attendance.AttendancePolicy` (Tahap A: satu per org)
- `organization`, `days_active` (array int), `check_in_start`, `check_in_end`, `check_out_start`, `check_out_end`, `late_tolerance_min`, `locations M2M` (null = semua lokasi aktif).

`attendance.AttendanceDay` (Workday/Session ringkasan — unique `[organization, student, work_date]`)
- `student`, `work_date (date)`, `status` [belum_masuk, sudah_masuk, sudah_pulang, perlu_ditinjau, dikoreksi], `check_in FK null`, `check_out FK null`.

`attendance.AttendanceRecord`
- `organization`, `student`, `kind` [in, out], `occurred_at (server time, indexed)`, `device_time (nullable, pendukung)`, `location FK`, `latitude`, `longitude`, `gps_accuracy_m`, `distance_m`, `validation` [valid, out_of_radius, low_accuracy, no_gps, invalid_photo, ...], `is_valid (bool)`, `photo FK (MediaAsset, nullable bila foto gagal)`, `idempotency_key (unique per [student, kind, work_date])`, `client_request_id`.

`media_photos.MediaAsset`
- `organization`, `storage_key (unique)`, `mime_type`, `width`, `height`, `size_bytes`, `checksum (sha256)`, `uploaded_at`, `retention_policy FK null`.

`attendance.AttendanceCorrection`
- `record FK`, `field_changed`, `old_value JSONB`, `new_value JSONB`, `reason (required)`, `actor FK User`, `created_at`. Record asli tidak pernah dihapus (PRD §7.8).

`audit.AuditLog`
- `organization (nullable untuk tindakan platform)`, `actor (nullable)`, `action`, `object_type`, `object_id`, `reason`, `metadata JSONB (tanpa data sensitif)`, `created_at (indexed)`. Write-only dari UI; append-only di level aplikasi (AUD-02).

## 5.3 Model Tahap B (SaaS)

`billing.Plan` — `code (unique)`, `name`, `price_amount`, `period` [monthly], `limits JSONB` (max_siswa, max_lokasi, max_admin, storage_mb), `features JSONB`, `is_active`.
`billing.Subscription` — `organization (unique aktif)`, `plan`, `status` [trial, pending_payment, active, past_due, suspended, cancelled, expired], `period_start`, `period_end`, `grace_days (default 7 — default, bisa diubah; PRD §17)`, state machine transisi eksplisit (BILL-02).
`billing.Invoice` — `number (unique, format PNS-YYYYMM-XXXX)`, `organization`, `amount`, `currency (IDR)`, `issued_at`, `due_at`, `status` [draft, unpaid, paid, overdue, cancelled].
`billing.PaymentTransaction` — `invoice`, `provider`, `external_id`, `method` [qris, va, ewallet], `amount`, `status` [pending, settled, failed, expired, refunded], `confirmed_at`. Amount/status yang sudah `settled` tidak dapat diedit (BILL-10).
`billing.PaymentWebhookEvent` — `provider_event_id (unique → idempotensi)`, `payload JSONB`, `received_at`, `processed_status`, `transaction FK null` (BILL-08).
`notifications.Notification` — `recipient`, `channel` [in_app], `kind`, `payload JSONB`, `read_at`, `created_at`.

## 5.4 Constraint & indeks penting

- `AttendanceRecord`: `UNIQUE (student, kind, work_date_key)` — mencegah absen ganda untuk sesi yang sama (ATT-04, aturan bisnis 4); `work_date_key` dihitung dari zona waktu tenant. Operasi absen dibungkus transaksi + `select_for_update` pada `AttendanceDay` untuk mencegah race request bersamaan.
- Indeks: `(organization, occurred_at)`, `(student, work_date)`, `(organization, status)`, `Invoice.number` unique, `PaymentWebhookEvent.provider_event_id` unique.
- FK semua dengan `on_delete=PROTECT` untuk record absensi/audit.

# 6. Desain API (`/api/v1/`)

Autentikasi: session-based untuk web server-rendered; token (DRF TokenAuthentication atau SimpleJWT) untuk konsumen non-browser (mobile nanti). Semua endpoint memvalidasi tenant dari membership user, bukan parameter klien (TEN-03/04).

| Endpoint | Metode | Peran | Catatan |
|---|---|---|---|
| `/api/v1/auth/login/`, `/logout/` | POST | semua | rate limit percobaan gagal (AUTH-07) |
| `/api/v1/attendance/status/` | GET | siswa | status hari ini + tombol yang relevan |
| `/api/v1/attendance/check-in/`, `/check-out/` | POST | siswa | multipart: foto + koordinat + accuracy + client_request_id |
| `/api/v1/attendance/me/` | GET | siswa | riwayat sendiri (ATT-07) |
| `/api/v1/attendance/records/` | GET | pembina/admin | filter tanggal, siswa, kelompok, lokasi, status (ATT-08) |
| `/api/v1/attendance/records/{id}/corrections/` | POST | pembina/admin | alasan wajib (ATT-09) |
| `/api/v1/students/` CRUD, `/import/` | | admin | import CSV/XLSX P1 (USER-03) |
| `/api/v1/locations/` CRUD | | admin | GEO-01 |
| `/api/v1/reports/daily/`, `/export/?format=csv` | GET | pembina/admin | REP-02/03 |
| `/api/v1/photos/{id}/` (auth view, bukan static) | GET | sesuai peran/tenant | streaming file terotorisasi (IMG-07) |
| `/api/v1/billing/...` (invoices, subscription) | | admin/billing | Tahap B |
| `/billing/webhook/{provider}/` | POST | provider (signature) | idempotent, tanpa session auth (BILL-07/08) |

Format error konsisten: `{"code": "OUT_OF_RADIUS", "message_id": "...", "detail": "..."}` — message_id dipetakan ke teks Indonesia di frontend (GEO-08, §8).

# 7. Alur Teknis Inti

## 7.1 Absensi masuk (check-in)

1. Frontend (`attendance.js` modul): minta izin kamera + geolocation; tangkap frame dari `getUserMedia` (facingMode user; fallback `<input capture>` bila tak didukung — IMG-01).
2. Kompresi di browser: canvas resize sisi terpanjang ≤ 1280 px → `canvas.toBlob('image/jpeg', 0.78)` (**default, bisa diubah**; PRD IMG-03). Jika browser tidak mendukung, kirim file asli dan biarkan backend normalisasi.
3. Dapatkan `getCurrentPosition` (high accuracy, timeout ~10 s); kirim `lat, lng, accuracy, client_request_id`.
4. Upload multipart ke `/api/v1/attendance/check-in/` dengan tombol terkunci saat in-flight dan indikator proses (§8).
5. Backend pipeline (semua server-side):
   a. Autentikasi + membership tenant aktif (cek status langganan, Tahap B).
   b. Rate-limit per user; cek `client_request_id` idempotensi.
   c. Validasi konten foto: decode Pillow, cek tipe aktual, ukuran maks; strip EXIF; normalisasi ulang bila perlu; simpan via storage backend → MediaAsset (IMG-04/05/06). Bila foto gagal → tolak, tidak ada record sah.
   d. Validasi lokasi: hitung jarak haversine ke lokasi yang berlaku (dari policy/membership); bandingkan terhadap `radius_m`; cek `accuracy ≤ max_accuracy_m` (GEO-04/05).
   e. Validasi jadwal: apakah `now` (di TZ tenant) berada dalam jendela check-in; tentukan `work_date`.
   f. Transaksi: kunci `AttendanceDay`, cek belum ada check-in sah, buat `AttendanceRecord` + update `AttendanceDay.status` (ATT-01..04).
   g. Tulis hasil validasi (jarak, akurasi, keputusan) ke record (GEO-06). Log tanpa koordinat presisi/data pribadi (§11 poin 12).
6. Respons: konfirmasi + `occurred_at` server, atau error terkode. Kegagalan tidak pernah dikirim sebagai sukses (PRD §5.1.9).

Check-out: sama, plus precheck bahwa ada check-in sah untuk `work_date` dan belum ada check-out (ATT-02, §5.2).

## 7.2 Koreksi pembina

POST corrections → validasi peran; simpan old/new value; update status AttendanceDay ke `dikoreksi`; record asli dipertahankan; tulis AuditLog (pelaku, waktu, objek, alasan) — ATT-09, AUD-01.

## 7.3 Billing & webhook (Tahap B)

1. Invoice dibuat saat langganan baru/perpanjangan (status `unpaid`).
2. Adapter `PaymentProvider` interface: `create_payment(invoice)`, `verify_webhook(headers, body) -> NormalizedEvent`. Implementasi provider pertama ditentukan setelah evaluasi PRD §17.
3. Webhook endpoint: verifikasi signature → simpan `PaymentWebhookEvent` (unique event id; duplikat → 200 tanpa efek) → cocokkan invoice + nominal + status → tandai transaction `settled` → aktivasi/perpanjangan subscription. Hanya jalur ini yang mengaktifkan langganan (BILL-07/09).
4. Cron harian (management command): tandai invoice overdue, transisi subscription `active → past_due → suspended` sesuai grace, kirim notifikasi in-app (BILL-11/12). Data tenant tidak dihapus.
5. Rekonsiliasi: superadmin command/query + tindakan manual tercatat di AuditLog (BILL-13).

## 7.4 Ekspor laporan

Streaming CSV via `csv.writer` (pagination query, tanpa memuat semua baris); XLSX via openpyxl untuk dataset kecil. Ekspor tercatat di audit bila memuat data sensitif.

# 8. Frontend (Django Templates + JS modular)

```
templates/
├── base.html                 # layout mobile-first, CSS responsif
├── attendance/
│   ├── student_home.html     # status hari ini, tombol besar Absen Masuk/Pulang
│   ├── capture.html          # wizard: izin kamera → foto → lokasi → kirim → hasil
│   └── history.html
├── dashboard/
│   ├── pembina.html          # tabel filter/pagination/thumbnail (IMG-09)
│   └── admin.html
└── ...
static/js/
├── camera.js     # getUserMedia, capture, fallback input capture
├── geo.js        # getCurrentPosition, pesan error berbeda per kegagalan (GEO-08)
├── compress.js   # canvas resize + toBlob
├── attendance.js # orchestrasi + submit + idempotency key + lock tombol
└── dashboard.js
```

- Tidak ada framework build (no bundler) pada pilot; ES modules native.
- Semua validasi bisnis tetap server-side; JS hanya pengumpulan data dan UX.
- Format tanggal/angka/mata uang Indonesia; zona waktu tenant konsisten (§8).
- Aksesibilitas dasar: label, kontras, fokus, pesan status non-warna (§8).

# 9. Keamanan (implementasi konkret dari PRD §11)

| Area | Implementasi |
|---|---|
| Password | hasher default Django (Argon2/PBKDF2); tidak pernah plaintext (AUTH-04) |
| Sesi | `SESSION_COOKIE_AGE` terbatas, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, HTTPS wajib (AUTH-05) |
| CSRF/XSS/SQLi | mekanisme bawaan Django; template autoescape; ORM saja |
| Upload | batas ukuran (default 5 MB, bisa diubah), validasi konten Pillow, strip EXIF, file di luar webroot, akses via view terotorisasi (IMG-04/05/07) |
| IDOR / lintas tenant | queryset selalu difilter organization dari membership; pengujian khusus (lihat §11) |
| Rate limit | login & absensi per user/IP (django-ratelimit atau middleware ringan) (AUTH-07) |
| Secret | `.env` + izin 600; tidak di repo; webhook secret terpisah |
| Logging | tanpa foto/koordinat presisi/kredensial; audit log append-only |
| Kartu pembayaran | tidak pernah disentuh sistem; provider-hosted saja (§11 poin 9) |
| EXIF | dihapus saat normalisasi (§11 poin 11) |

Catatan batas: sistem tidak mengklaim anti-spoofing GPS atau verifikasi wajah (PRD §11.1); pesan produk mengikuti batasan ini.

# 10. Observabilitas & Backup

- Logging: `logs/django.log` rotasi; request lambat (>500 ms) dan error dicatat; Sentry opsional Tahap B.
- Metrik: p95 latensi API (log-based/ statistik nginx), ukuran foto rata-rata (agregat MediaAsset), tingkat keberhasilan absensi, pertumbuhan storage — sesuai indikator PRD §14.
- Backup: cron harian `pg_dump -Fc` ke `~/ganeshatech-presensi/backups/`, retensi 14 hari (**default, bisa diubah**), salinan luar-VPS bila tersedia; prosedur pemulihan terdokumentasi + diuji minimal sekali sebelum pilot dinyatakan selesai (PRD §13.1).
- RPO target 24 jam (daily dump); RTO final ditentukan sebelum komersial (PRD §12).

# 11. Strategi Pengujian

| Lapisan | Cakupan | Alat |
|---|---|---|
| Unit | validasi geofence (haversine, boundary radius/accuracy), state machine subscription, idempotensi, kompresi/normalisasi foto, number format uang | pytest + pytest-django |
| Integrasi API | seluruh endpoint DRF: happy path + error codes + otorisasi peran | DRF test client |
| Isolasi tenant (wajib, PRD §13.2) | suite khusus: user tenant A mencoba baca/tulis semua objek tenant B via URL/API → harus 403/404; dijalankan otomatis tiap CI | pytest |
| Duplikasi absensi | uji request paralel/retry menghasilkan tepat satu record sah (ATT-04) | pytest + threading |
| Webhook | signature salah, duplikat, out-of-order, nominal beda → tidak aktivasi ganda (BILL-08) | pytest |
| Manual perangkat nyata | berbagai HP/browser, titik di dalam/luar radius, GPS indoor bengkel, izin ditolak, jaringan lambat (PRD §15) | checklist pilot |

CI minimal: run test + migrasi check + audit isolasi tenant pada setiap push (GitHub Actions atau script lokal; tidak ada deploy otomatis tanpa persetujuan).

# 12. Rencana Implementasi Bertahap

Urutan mengikuti PRD §16; setiap tahap punya kriteria selesai (DoD PRD §19).

**Tahap A — Pilot (TeFa SMK Ganesha Tama sebagai organisasi pertama)**

1. **Fondasi:** scaffold Django (apps §2.1), custom User + Membership, settings/env, PostgreSQL di VPS, design system dasar, CI test.
   Selesai: login/logout berfungsi, migrasi jalan, test hijau.
2. **Master data:** Organization, StudentProfile (+ CRUD admin), AttendanceLocation, AttendancePolicy.
   Selesai: admin bisa kelola siswa & lokasi via admin/template.
3. **Absensi inti:** modul kamera/kompresi/geolocation frontend, endpoint check-in/out, pipeline validasi server, idempotensi, AttendanceDay status.
   Selesai: kriteria PRD §13.1 poin 1–6 lolos pada perangkat nyata.
4. **Dashboard & laporan:** dashboard pembina, filter, riwayat, ekspor CSV, koreksi + audit log.
   Selesai: PRD §13.1 poin 7–8.
5. **Hardening pilot:** pengamanan foto (auth view), rate limit, backup + uji pemulihan terdokumentasi, pengujian GPS bermasalah, perbaikan pesan error.
   Selesai: seluruh PRD §13.1.

**Tahap B — SaaS komersial**

6. **Multi-tenant penuh:** onboarding organisasi, pengujian isolasi otomatis, batas paket ditegakkan backend.
7. **Billing:** Plan/Subscription/Invoice, adapter payment provider (QRIS), webhook idempotent, rekonsiliasi, grace/suspend, notifikasi in-app.
8. **Kesiapan komersial:** privasi/ToS, staging, monitoring, backup teruji, dokumentasi admin & dukungan.
   Selesai: seluruh PRD §13.2.

**Tahap C:** PWA, izin/sakit, uang saku, kanal notifikasi eksternal, mobile (di luar lingkup dokumen ini; API v1 sudah disiapkan).

# 13. Keputusan Terbuka yang Diadopsi sebagai Default

Semua nilai berikut diadopsi dari usulan PRD §17 dan **bisa diubah** oleh pemilik produk:

| Keputusan | Default yang dipakai dokumen ini |
|---|---|
| Metode login siswa | ID siswa (username) + password dibuat admin |
| Radius geofence | 100 m |
| Akurasi GPS maksimum | 50 m |
| Dimensi foto | ≤ 1280 px sisi terpanjang |
| Target ukuran foto | 100–300 KB; batas upload 5 MB |
| Kualitas JPEG | 0.78 |
| Penyimpanan produksi | Filesystem lokal dulu; S3-compatible saat Tahap B bila anggaran memungkinkan |
| Provider pembayaran | Belum dipilih; desain via adapter |
| Masa tenggang | 7 hari |
| Jadwal/shift | Satu sesi harian untuk pilot |
| Format laporan | CSV dasar; XLSX opsional pilot |
| Notifikasi | In-app dulu |
| Port Gunicorn | 127.0.0.1:8010 (cek port bebas saat provisioning) |
| Retensi backup | 14 hari |

# 14. Risiko Teknis & Mitigasi Operasional

| Risiko teknis | Mitigasi dalam desain ini |
|---|---|
| Port/konfigurasi bentrok dengan aplikasi lain di VPS | Cek port sebelum provisioning; systemd unit & venv terpisah; tidak menyentuh `~/ganesha-tech` dan `/opt/ganeshatech-wa` |
| PostgreSQL resource bersama | `shared_buffers` default; hanya listen localhost; monitor ukuran DB |
| Disk penuh karena foto | Kompresi browser + normalisasi server + retensi + monitoring growth (PRD §14) |
| Race absensi paralel | select_for_update + unique constraint (§5.4) |
| Webhook hilang/duplikat | unique event id + rekonsiliasi manual terjadwal |
| Single VPS (no HA) | Diterima untuk pilot; backup harian + prosedur pemulihan; HA dievaluasi sebelum komersial |
| GPS indoor bengkel buruk | Uji lapangan per perangkat/titik; radius/akurasi dapat dikonfigurasi per lokasi; jalur koreksi (PRD §15) |

---

**Akhir dokumen — Technical Design & Implementation Plan v1.0**

Dokumen ini adalah baseline teknis pendamping PRD v1.0. Perubahan keputusan teknis dicatat sebagai revisi dokumen ini agar semua coding agent dan pengembang konsisten dengan PRD.
