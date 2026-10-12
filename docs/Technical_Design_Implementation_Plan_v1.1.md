---
title: "TECHNICAL DESIGN & IMPLEMENTATION PLAN"
subtitle: "Platform Absensi dan Manajemen Teaching Factory (TeFa)"
author: "Dokumen Teknis — v1.1 (gabungan)"
date: "12 Oktober 2026"
---

# Informasi Dokumen & Changelog

| Atribut | Isi |
|---|---|
| Nama produk | Platform Absensi dan Manajemen TeFa (nama kerja) |
| Versi dokumen | TDIP 1.1 |
| Referensi | PRD Platform Absensi TeFa v1.0 (12 Oktober 2026) |
| Status | Dokumen teknis pendamping PRD; nilai dari usulan PRD ditandai **(default, bisa diubah)** |
| Bahasa | Bahasa Indonesia |
| Deployment awal | VPS Tencent 43.157.205.8, user `tefa`, folder `~/ganeshatech-presensi` |

**Changelog:**

- **v1.0 (Dokumen A)** — baseline teknis agent utama: kuat pada deployment VPS spesifik (aturan keras VPS bersama, struktur server, provisioning, port 8010, cron backup), suite pengujian isolasi tenant, constraint DB konkret, desain frontend, observabilitas.
- **v1.0 (Dokumen B / Codex)** — baseline teknis Codex: kuat pada pola otorisasi per request, checklist isolasi tenant, tabel API endpoint + contoh request/response + tabel error code, pipeline media tajam (larangan SVG, anti-DoS, file yatim), template task AI coding agent, keputusan terbuka DEC-01..13, kehati-hatian versi software, catatan QRIS ≠ autodebit, `session_key` di AttendanceDay.
- **v1.1 (gabungan)** — menggabungkan keduanya: substansi utama mengikuti Dokumen B, seluruh bagian deployment VPS spesifik Dokumen A dipertahankan sebagai bagian tersendiri (§6). Duplikasi dihilangkan; tidak ada klaim/fitur baru di luar kedua dokumen.

> **Konvensi:** kebutuhan MUST/SHOULD mengikuti makna pada PRD. Nilai konfigurasi default adalah titik awal untuk divalidasi, bukan keputusan final. Dokumen ini tidak mengubah kebutuhan PRD; jika ada konflik, PRD yang berlaku. Konflik teknis dicatat di bagian keputusan dan diputuskan sebelum kode terdampak ditulis.

# 1. Tujuan dan Prinsip Teknis

Dokumen ini menerjemahkan PRD v1.0 menjadi keputusan teknis konkret dan rencana implementasi: arsitektur sistem, skema data awal (model, constraint, indeks), desain API `/api/v1/`, alur teknis inti (absensi, geofence, foto, koreksi, billing), struktur proyek, deployment, strategi pengujian, keamanan, observabilitas, backup, dan urutan pengerjaan bertahap (pilot TeFa → SaaS komersial).

Yang **tidak** termasuk: desain UI final (mengikuti PRD §8), pilihan provider pembayaran final (PRD §17), dan implementasi aplikasi mobile.

## 1.1 Prinsip wajib

1. **Backend adalah sumber kebenaran.** Waktu resmi, validasi geofence, hak akses, transisi status absensi, batas paket, dan status pembayaran ditentukan server. Frontend hanya mengumpulkan input dan menampilkan hasil.
2. **Multi-tenant sejak migrasi pertama.** Setiap data milik pelanggan memiliki hubungan tenant yang jelas. Semua operasi baca/tulis memeriksa keanggotaan dan izin di backend.
3. **Modular monolith terlebih dahulu.** Satu aplikasi Django dengan batas modul yang jelas. Jangan memulai dengan microservices, Kubernetes, atau infrastruktur kompleks yang belum diperlukan.
4. **API-ready, bukan API demi API.** Logika bisnis tidak bergantung pada halaman HTML; endpoint API memakai service yang sama dengan antarmuka web.
5. **Privasi sejak desain.** Ambil data seperlunya, simpan foto yang sudah diproses, batasi akses media, definisikan retensi.
6. **Keputusan mudah diubah.** Storage dan payment gateway memakai adapter; nama provider tidak ditanam ke logika inti.
7. **Perubahan kecil dan terlacak.** Implementasi dibagi menjadi tugas terbatas; satu tugas tidak boleh diam-diam merombak aplikasi secara keseluruhan.
8. **Tidak membuat klaim anti-kecurangan absolut.** GPS browser dapat dimanipulasi; foto selfie bukan liveness detection. Sistem tidak mengklaim anti-spoofing GPS atau verifikasi wajah (PRD §11.1).

# 2. Keputusan Arsitektur

## 2.1 Keputusan utama

| ID | Keputusan | Alasan | Status |
|---|---|---|---|
| ARC-01 | Django sebagai backend dan web framework utama (monolith modular, apps per domain). | Auth, ORM, migrasi, admin, templating; skala kecil, tim kecil. | Direkomendasikan |
| ARC-02 | DRF untuk endpoint `/api/v1/`, versioning sejak awal. | Kontrak API konsisten untuk web dan calon mobile. | Direkomendasikan |
| ARC-03 | Django Templates + JS modular (vanilla ES modules, tanpa bundler) + CSS responsif. | Cepat untuk MVP; kamera/geolocation/kompresi cukup dengan API browser. | Direkomendasikan |
| ARC-04 | PostgreSQL satu-satunya datastore; media di luar DB. | Constraint, transaksi, relasi, indeks, laporan; binari besar tidak di DB (PRD §9.1). | Direkomendasikan |
| ARC-05 | Shared database/shared schema multi-tenant via kolom `organization_id` + manager/queryset yang memaksa scope. | Ringan operasional; wajib disertai tenant-scoping ketat. Row-Level Security ditunda hingga ada kebutuhan. | Direkomendasikan dengan kontrol ketat |
| ARC-06 | Custom User model sebelum migrasi pertama. | Menghindari migrasi sulit jika model identitas berubah setelah data tersedia. | Wajib |
| ARC-07 | Session cookie + CSRF untuk web; token (DRF TokenAuthentication atau SimpleJWT) untuk konsumen non-browser nanti. | Web memakai autentikasi Django; skema token mobile diputuskan saat klien mobile dibangun. | Direkomendasikan |
| ARC-08 | Lapisan storage abstrak (Django `STORAGES`); media lokal privat untuk pilot, object storage privat untuk SaaS komersial bila memungkinkan. | IMG-08: perpindahan media tanpa merombak domain absensi. | Wajib disiapkan sejak awal |
| ARC-09 | Payment gateway via adapter interface `PaymentProvider`. | Provider dapat diganti tanpa mengubah logika invoice/langganan (BILL-05). | Wajib sebelum billing |
| ARC-10 | Redis/worker (Celery) ditunda; pekerjaan asinkron pilot dilakukan sinkron atau management command. | PRD §10.2 menyatakan belum wajib untuk pilot. | Ditunda |

## 2.2 Hal yang sengaja belum dibangun

- Tidak ada microservices pada versi awal.
- Redis, Celery/background worker, dan message broker tidak wajib pada MVP.
- Tidak ada real-time GPS tracking; lokasi diambil saat siswa melakukan absensi.
- Tidak ada pengenalan wajah atau liveness detection secara default.
- Tidak ada penyimpanan file yang diakses publik tanpa otorisasi.
- Tidak ada recurring payment yang diasumsikan didukung semua metode QRIS.
- Tidak ada native Android/iOS di fase web awal.

# 3. Diagram Arsitektur dan Alur Data

## 3.1 Arsitektur sistem

```text
[Browser HP siswa/pembina/admin]
        │  HTTPS
        ▼
[Nginx (reverse proxy, TLS, static, body size limit)]
        ▼
[Gunicorn] ──► [Django app — modular monolith]
                ├── core/accounts/tenants   (auth, role, tenant context)
                ├── attendance              (lokasi, jadwal, sesi, record, koreksi)
                ├── media_photos            (MediaAsset, validasi/normalisasi, storage adapter)
                ├── reports                 (dashboard, rekap, ekspor CSV/XLSX)
                ├── audit                   (AuditLog)
                ├── billing                 (Plan, Subscription, Invoice, PaymentTransaction, webhook)  [Tahap B]
                └── notifications           (in-app; kanal eksternal menyusul)                                [P1]
        ▼                         ▼
[PostgreSQL]              [Media storage privat: filesystem lokal → S3-compatible]

PAYMENT GATEWAY (fase SaaS) ── HTTPS webhook ──►
  /api/v1/webhooks/payments/{provider}/ : verify → deduplicate → recheck → update
```

## 3.2 Alur request absensi masuk/pulang

1. Browser meminta foto dari kamera dan koordinat melalui izin perangkat.
2. JavaScript memperkecil dan mengompres foto sebelum upload bila didukung browser. Kegagalan kompresi tidak boleh menyebabkan foto berukuran bebas; fallback server tetap dibatasi.
3. Browser mengirim foto, latitude, longitude, akurasi GPS, jenis absensi, dan idempotency key melalui HTTPS.
4. Backend mengidentifikasi user dan membership tenant dari sesi/token terautentikasi. `tenant_id` dari request tidak boleh dipercaya.
5. Backend memeriksa role, status tenant/langganan, sesi kerja, kebijakan, lokasi yang diizinkan, dan validitas file.
6. Backend menghitung jarak ke titik lokasi dan menerapkan aturan geofence serta akurasi.
7. Backend menggunakan transaksi database/constraint untuk mencegah dua check-in/check-out yang sama.
8. Jika semua valid, media disimpan melalui storage adapter dan event absensi dicatat dengan waktu server.
9. Jika terjadi kegagalan, response menyatakan alasan yang dapat ditindaklanjuti. Tidak boleh menampilkan berhasil sebelum commit data berhasil.
10. Jika file tersimpan tetapi penyimpanan catatan database gagal, lakukan kompensasi: hapus file yatim atau tandai untuk cleanup.

## 3.3 Alur pembayaran

1. Sistem membuat invoice lokal dengan nomor unik dan nominal yang disepakati.
2. Billing adapter meminta transaksi ke provider dan menyimpan ID provider serta detail status.
3. UI menampilkan instruksi pembayaran provider; redirect kembali ke situs hanya untuk UX, bukan sumber kebenaran transaksi.
4. Webhook masuk melalui HTTPS, divalidasi signature/keaslian sesuai dokumentasi provider, lalu transaksi dikonfirmasi ulang melalui API provider bila dibutuhkan.
5. Event webhook dideduplikasi; nominal, currency, order ID, merchant/provider reference, dan status harus cocok.
6. Setelah status terminal yang sah, service billing mengubah transaksi, invoice, dan periode subscription secara atomik/idempotent.
7. Webhook duplikat, out-of-order, atau gagal sementara tidak boleh mengaktifkan langganan dua kali atau menimpa status final secara keliru.

# 4. Stack Teknologi dan Kebijakan Versi

| Komponen | Pilihan | Catatan |
|---|---|---|
| Python | 3.12 | sesuai VPS; kunci versi lingkungan pada dokumentasi proyek |
| Django | 5.x LTS (patch terbaru yang kompatibel saat bootstrap) | Per 12 Oktober 2026 halaman resmi mencantumkan 5.2 LTS (extended support s.d. April 2028, patch 5.2.18). Verifikasi ulang sebelum bootstrap/upgrade; jangan mengarang nomor versi. |
| DRF | 3.15+ versi stabil yang kompatibel | Pin di lock file; permission default tertutup, izin diatur per endpoint. |
| PostgreSQL | 16 (versi default repo apt; minimum versi mayor yang masih didukung, jangan EOL) | TZ-aware timestamps. |
| Gunicorn + Nginx | sesuai apt/pip | TLS, static, body size limit, timeout, proxy headers eksplisit. |
| Pillow | validasi/decode & normalisasi foto | IMG-04/05. |
| openpyxl | ekspor XLSX (opsional pilot) | REP-03. |
| redis/Celery | TIDAK di pilot | ARC-10. |
| django-storages | Tahap B (object storage) | ARC-08. |

**Catatan versi:** pemilihan patch aktual wajib dikonfirmasi saat membuat environment baru karena rilis keamanan dapat berubah. Rujuk halaman unduhan dan kebijakan dukungan resmi (§22).

`requirements/base.txt`, `requirements/production.txt`, `requirements/dev.txt` terpisah (atau `pyproject.toml` terpin — pilih satu pendekatan, konsisten).

## 4.1 Default keamanan Django/DRF

- `DEBUG=False` di production; `ALLOWED_HOSTS` dan trusted origins eksplisit.
- Secret key dan kredensial database/provider via environment/secret store, bukan file yang dikomit.
- Semua endpoint API memiliki permission yang disengaja; hindari default DRF yang bisa membuka akses publik.
- CSRF untuk operasi state-changing berbasis cookie; TLS/HTTPS; cookie Secure/HttpOnly/SameSite; rate limiting; validasi input.
- Media privat tidak dilayani sebagai direktori publik langsung.

# 5. Struktur Proyek yang Diusulkan

Struktur berikut adalah target modular; tidak perlu seluruh modul dibangun sekaligus.

```text
tefa-attendance/
├── manage.py
├── pyproject.toml / requirements/  # pilih satu, terpin
├── .env.example                    # nama variabel saja; tanpa secret
├── .gitignore
├── README.md
├── docs/
│   ├── PRD.md
│   ├── TECHNICAL_DESIGN.md         # dokumen ini
│   ├── MANUAL_QA_CHECKLIST.md
│   └── decisions/                  # ADR
├── config/                         # settings: base/local/staging/production; urls, wsgi, asgi
├── apps/
│   ├── core/                       # health check, shared utilities, common errors
│   ├── accounts/                   # custom User, login/session, password reset
│   ├── tenants/                    # Organization, Membership, tenant context/permissions
│   ├── attendance/                 # StudentProfile, policy, location, schedule, day, record, corrections
│   ├── media_photos/               # MediaAsset, validasi/normalisasi, storage adapter
│   ├── reports/                    # query/report/export
│   ├── audit/                      # audit event and review helpers
│   ├── billing/                    # Plan, Subscription, Invoice, PaymentTransaction [Tahap B]
│   └── notifications/              # in-app; channels later
├── templates/                      # base, auth, student, staff, organization_admin, platform_admin
├── static/
│   ├── css/
│   ├── js/
│   │   ├── modules/                # camera.js, geo.js, compress.js, attendance.js, dashboard.js
│   │   └── app.js
│   └── img/
├── private_media/                  # development only; di .gitignore
└── scripts/                        # import/export/maintenance; no secrets
```

## 5.1 Aturan pembagian kode

- Model menyimpan data dan constraint; hindari menaruh seluruh aturan bisnis di template atau signal.
- Logika inti absensi berada dalam service/domain module yang bisa dipakai view HTML dan API.
- View/API view bertanggung jawab pada parsing request, pemanggilan service, dan response.
- Serializer/form memvalidasi input struktural; aturan lintas model/tenant divalidasi ulang di service/backend.
- Query data tenant ter-scope sedini mungkin di `get_queryset()`/repository/service; jangan hanya disembunyikan di frontend.
- Jangan membuat abstraksi generik terlalu dini; abstraksi dibuat saat ada lebih dari satu implementasi nyata atau batas yang jelas (storage/payment provider).

# 6. Lingkungan Deployment (VPS bersama) — spesifik proyek

> Bagian ini WAJIB dipatuhi apa pun keputusan lain dalam dokumen ini.

## 6.1 Batasan VPS

VPS Tencent `43.157.205.8` juga menjalankan:
- Company profile website di `~/ganesha-tech`
- Flask WA app di `/opt/ganeshatech-wa`

**Aturan keras:**
1. Tidak boleh mengubah konfigurasi, file, port, atau layanan milik dua aplikasi lain itu.
2. Semua milik proyek ini berada di bawah user `tefa`, folder `~/ganeshatech-presensi`.
3. Port dan nama service unik; tidak memakai port yang sudah dipakai aplikasi lain (cek `sudo ss -tlnp` sebelum menetapkan).
4. Nginx hanya ditambah server block baru dengan `server_name` berbeda; jangan menyentuh konfigurasi existing.

## 6.2 Struktur server

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

## 6.3 Langkah provisioning (dilakukan sekali, terdokumentasi sebagai script/checklist)

1. `sudo apt update && sudo apt install -y postgresql postgresql-contrib` — PostgreSQL perlu di-install di VPS.
2. Buat DB + user khusus: `CREATE DATABASE ganeshatech_presensi; CREATE USER presensi_app WITH PASSWORD <dari .env>; GRANT ...` — password di-generate, disimpan di `.env`, tidak pernah masuk repo.
3. `python3 -m venv ~/ganeshatech-presensi/venv` (TIDAK memakai venv milik aplikasi lain).
4. Install dependensi: `pip install -r requirements/production.txt`.
5. Gunicorn sebagai systemd unit user baru: `presensi.service` (User=tefa, WorkingDirectory=repo, socket/port lokal unik, mis. `127.0.0.1:8010` — final setelah cek port bebas).
6. Nginx: server block baru, proxy_pass ke Gunicorn, `client_max_body_size` disetel ke batas upload foto + margin (default 5 MB, bisa diubah), TLS via certbot untuk domain produksi.
7. Firewall: buka hanya 80/443; PostgreSQL hanya listen `127.0.0.1`.
8. Cron user tefa: backup `pg_dump` harian + rotasi, housekeeping media/retensi.

Catatan tambahan dari prinsip umum deployment (Dokumen B §13.2, diterapkan dalam kerangka aturan keras di atas): jalankan sebagai user non-root dengan izin minimum; migration sebagai langkah deployment yang disengaja (bukan dari beberapa worker sekaligus); private media tidak masuk `collectstatic`; health check sederhana yang tidak membocorkan environment/secret; siapkan rollback aplikasi dan backup sebelum migrasi berisiko.

## 6.4 Environment

| Env | Lokasi | Tujuan |
|---|---|---|
| development | lokal/VM pengembang | iterasi fitur; data dummy, sandbox provider bila billing; jangan data siswa nyata |
| staging | ditambahkan sebelum Tahap B bila memungkinkan | simulasi manual: HTTPS, DEBUG=False, DB/file terpisah, secret staging |
| production | VPS 43.157.205.8, user `tefa` | pilot TeFa, lalu SaaS |

Sampai staging tersedia, pengujian perilaku berbahaya dilakukan lokal dengan dump data anonim.

Konfigurasi via `.env` (django-environ): `SECRET_KEY`, `DATABASE_URL`, `DEBUG`, `ALLOWED_HOSTS`, `MEDIA_*`, batas upload, flag fitur billing, kredensial payment gateway (Tahap B). Tidak ada secret di repo (PRD §11 poin 4, §13.2). `.env.example` hanya berisi placeholder/nama variabel.

# 7. Desain Multi-Tenant dan Otorisasi

## 7.1 Model akses

- `User` adalah identitas login global.
- `Organization` mewakili satu sekolah/unit TeFa pelanggan.
- `Membership` menghubungkan user dengan tenant dan role (`admin`, `pembina`, `siswa`, `billing`) dengan flag aktif.
- `PLATFORM_ADMIN` adalah role platform yang cakupannya terpisah dan tidak otomatis memberi hak membaca foto/koordinat tanpa kebutuhan yang sah.
- `StudentProfile` terhubung ke membership siswa; data siswa spesifik organisasi berada pada profile tersebut.
- Jika user memiliki lebih dari satu membership di masa depan, tenant aktif dipilih dengan aman lalu diverifikasi; tenant ID/slug dari URL bukan bukti izin.

## 7.2 Pola wajib untuk setiap request (7 langkah)

1. Autentikasi request.
2. Tentukan actor dan membership aktif untuk tenant yang diminta.
3. Periksa role serta izin atas tindakan.
4. Ambil object melalui queryset yang sudah terbatasi ke tenant yang sah.
5. Validasi relasi semua object input agar berasal dari tenant yang sama.
6. Lakukan operasi dan tulis audit log bila sensitif.
7. Kembalikan hanya field yang sesuai dengan peran pengguna.

## 7.3 Checklist isolasi tenant

- Jangan percaya `tenant_id` dari body request.
- Semua endpoint list/detail/ubah/hapus melakukan tenant scoping.
- Semua file/media URL diverifikasi terhadap tenant dan record pemilik.
- ID object yang sulit ditebak bukan pengganti izin akses.
- Cache key, ekspor laporan, background job, dan webhook juga harus membawa tenant/reference yang tervalidasi.
- Uji manual harus mencoba membaca/mengubah object tenant lain dengan mengganti ID di URL/body.
- Bila risiko multi-tenant menjadi paling tinggi menjelang komersialisasi, pertimbangkan PostgreSQL Row-Level Security sebagai lapisan tambahan setelah implementasi dipahami; jangan menganggap RLS aktif jika belum dikonfigurasi.

# 8. Desain Data

## 8.1 Prinsip

- Semua tabel milik tenant punya `organization` FK (indexed). Query hanya lewat manager yang memaksa scope tenant (ARC-05).
- Timestamps TZ-aware (UTC di DB); tampilan dikonversi ke zona waktu tenant (PRD §7.1).
- Uang: rupiah bulat via `DecimalField` yang tepat atau integer; tidak memakai float (PRD §9.1).
- Foto: hanya metadata di DB (MediaAsset), binari di storage backend.
- Audit log tidak di-CASCADE-delete; jangan hard-delete attendance/audit records via UI operasional.

## 8.2 Model Tahap A (pilot)

Ini rancangan awal untuk memandu model Django; nama tabel/field boleh disesuaikan implementasi asalkan relasi dan invariannya dipertahankan.

`tenants.Organization`
- `id (uuid)`, `name`, `slug (unique)`, `status` [active, suspended, closed], `timezone` (default `Asia/Jakarta`), `settings JSONB` (radius default, akurasi maks, jam efektif), `created_at`.

`accounts.User`
- Custom user (AbstractBaseUser + PermissionsMixin): `username (unique)`, `password (hash)`, `is_platform_admin`, `is_active`, `created_at`. Siswa login pakai ID siswa sebagai username — **(default, bisa diubah; PRD §17 / DEC-01)**.

`accounts.Membership` — unique `[organization, user]`
- `organization`, `user`, `role` [admin, pembina, siswa, billing], `scope JSONB` (kelompok/lokasi yang ditugaskan), `is_active`.

`attendance.StudentProfile`
- `organization`, `user (OneToOne, nullable untuk data siswa tanpa akun)`, `student_number (unique per org)`, `full_name`, `group` (kelas/kelompok, nullable), `is_active`.

`attendance.AttendanceLocation`
- `organization`, `name`, `latitude (DecimalField 9,6)`, `longitude`, `radius_m` (default 100 — **default, bisa diubah**), `max_accuracy_m` (default 50 — **default, bisa diubah**), `is_active`. Indeks tenant/status; validasi koordinat/radius di model/service.

`attendance.AttendancePolicy` (Tahap A: satu per org)
- `organization`, `days_active` (array int), `check_in_start`, `check_in_end`, `check_out_start`, `check_out_end`, `late_tolerance_min`, `locations M2M` (null = semua lokasi aktif). Revisi kebijakan sebaiknya dapat ditelusuri. Desain shift malam lintas tengah malam ditunda sampai aturan disetujui (DEC-05).

`attendance.AttendanceDay` (ringkasan workday/session — unique `[organization, student, work_date, session_key]`)
- `organization`, `student`, `work_date (date)`, `session_key` (key sesi sesuai model jadwal; satu sesi untuk pilot), `status` [belum_masuk, sudah_masuk, sudah_pulang, perlu_ditinjau, dikoreksi], `check_in FK null`, `check_out FK null`. Indeks tanggal/tenant.

`attendance.AttendanceRecord`
- `organization`, `student`, `kind` [in, out], `occurred_at (server time, indexed)`, `device_time (nullable, pendukung/diagnostik saja)`, `location FK`, `latitude`, `longitude`, `gps_accuracy_m`, `distance_m`, `validation` [valid, out_of_radius, low_accuracy, no_gps, invalid_photo, ...], `is_valid (bool)`, `photo FK (MediaAsset, nullable bila foto gagal)`, `idempotency_key (unique per [student, kind, work_date])`, `client_request_id`.

`media_photos.MediaAsset`
- `organization`, `storage_key (unique)`, `mime_type (hasil verifikasi)`, `width`, `height`, `size_bytes`, `checksum (sha256)`, `uploaded_at`, `retention_policy FK null`. File privat; jangan simpan URL publik permanen atau path absolut lokal sebagai satu-satunya referensi.

`attendance.AttendanceCorrection`
- `record FK`, `field_changed`, `old_value JSONB`, `new_value JSONB`, `reason (required)`, `actor FK User`, `created_at`. Koreksi tidak menghilangkan jejak nilai sebelumnya; record asli tidak pernah dihapus (PRD §7.8).

`audit.AuditLog`
- `organization (nullable untuk tindakan platform)`, `actor (nullable)`, `action`, `object_type`, `object_id`, `reason`, `metadata JSONB (tanpa secret/payload penuh/foto/koordinat presisi)`, `created_at (indexed)`. Write-only dari UI; append-only di level aplikasi (AUD-02).

## 8.3 Model Tahap B (SaaS)

`billing.Plan` — `code (unique)`, `name`, `price_amount`, `period` [monthly], `limits JSONB` (max_siswa, max_lokasi, max_admin, storage_mb), `features JSONB`, `is_active`. Harga/batas efektif untuk subscription harus dapat ditelusuri.

`billing.Subscription` — `organization (unique aktif)`, `plan`, `status` [trial, pending_payment, active, past_due, suspended, cancelled, expired], `period_start`, `period_end`, `grace_days (default 7 — default, bisa diubah; DEC-08)`. State machine transisi eksplisit di satu service, bukan mengganti status bebas dari view (BILL-02).

`billing.Invoice` — `number (unique, format PNS-YYYYMM-XXXX)`, `organization`, `amount`, `currency (IDR)`, `issued_at`, `due_at`, `status` [draft, unpaid, paid, overdue, cancelled].

`billing.PaymentTransaction` — `invoice`, `provider`, `external_id (provider reference unik per provider)`, `method` [qris, va, ewallet], `amount`, `status` [pending, settled, failed, expired, refunded], `confirmed_at`. Amount/status yang sudah `settled` tidak dapat diedit (BILL-10).

`billing.PaymentWebhookEvent` — `provider_event_id (unique → idempotensi)`, `payload JSONB (redacted)`, `received_at`, `processed_status`, `transaction FK null` (BILL-08).

`notifications.Notification` — `recipient`, `channel` [in_app], `kind`, `payload JSONB`, `read_at`, `created_at`. Bukan dependensi keberhasilan transaksi inti.

## 8.4 Constraint & indeks penting

- `AttendanceRecord`: `UNIQUE (student, kind, work_date_key)` — mencegah absen ganda untuk sesi yang sama (ATT-04, aturan bisnis 4); `work_date_key` dihitung dari zona waktu tenant. Operasi absen dibungkus transaksi + `select_for_update` pada `AttendanceDay` untuk mencegah race request bersamaan. Constraint unik pada event check-in/check-out mencegah dua request paralel lolos bersama.
- Indeks: `(organization, occurred_at)`, `(student, work_date)`, `(organization, status)`, `Invoice.number` unique, `PaymentWebhookEvent.provider_event_id` unique.
- FK dengan `on_delete=PROTECT` untuk record absensi/audit.
- Retry dengan idempotency key yang sama setelah timeout (server sudah commit) mengembalikan hasil sebelumnya, bukan event baru.

# 9. Desain API v1 (`/api/v1/`)

Autentikasi: session-based untuk web server-rendered; token (DRF TokenAuthentication/SimpleJWT) untuk konsumen non-browser nanti. Semua endpoint memvalidasi tenant dari membership user, bukan parameter klien (TEN-03/04). Kontrak di bawah boleh dipertajam saat implementasi, tetapi makna otorisasi dan status response tetap konsisten.

## 9.1 Daftar endpoint awal

| Method | Endpoint | Pengguna | Fungsi |
|---|---|---|---|
| `GET` | `/api/v1/me/` | Semua login | Info user, membership/role aktif, organisasi aktif. |
| `POST` | `/api/v1/auth/login/` | Semua | Membuat sesi web; rate limit percobaan gagal (AUTH-07). |
| `POST` | `/api/v1/auth/logout/` | Semua login | Mengakhiri sesi. |
| `GET` | `/api/v1/attendance/today/` | Siswa/pembina/admin | Status absensi hari ini sesuai hak akses + tombol relevan. |
| `POST` | `/api/v1/attendance/check-in/`, `/check-out/` | Siswa | Multipart: foto + koordinat + accuracy + `client_request_id`. |
| `GET` | `/api/v1/attendance/my-records/` | Siswa | Riwayat absensi milik sendiri (ATT-07). |
| `GET` | `/api/v1/attendance/records/` | Pembina/admin | Filter tanggal, siswa, kelompok, lokasi, status + pagination (ATT-08). |
| `POST` | `/api/v1/attendance/records/{id}/corrections/` | Pembina/admin | Koreksi dengan alasan wajib (ATT-09). |
| `GET/POST/PATCH` | `/api/v1/students/` + detail, `/import/` | Admin | CRUD profil siswa; import CSV/XLSX P1 (USER-03). |
| `GET/POST/PATCH` | `/api/v1/locations/` | Admin | CRUD lokasi geofence (GEO-01). |
| `GET/PATCH` | `/api/v1/attendance-policy/` | Admin | Pengaturan absensi tenant. |
| `GET` | `/api/v1/reports/attendance/`, `/export/?format=csv` | Pembina/admin | Laporan dan ekspor (REP-02/03). |
| `GET` | `/api/v1/photos/{id}/` (auth view, bukan static) | Sesuai peran/tenant | Streaming file terotorisasi (IMG-07). |
| — | `/api/v1/billing/...` (invoices, subscription) | Admin/billing | Tahap B. |
| `POST` | `/api/v1/webhooks/payments/{provider}/` | Provider (signature) | Endpoint publik tapi wajib verifikasi; idempotent, tanpa session auth (BILL-07/08). |

## 9.2 Request absensi

Kirim sebagai `multipart/form-data` agar file tidak perlu dikodekan base64 dalam JSON.

```text
photo                binary JPEG setelah kompresi browser
latitude             decimal
longitude            decimal
accuracy_m           decimal
client_request_id    UUID / idempotency key
client_captured_at   optional; hanya diagnostik, bukan waktu resmi
```

Jangan mengambil `student_id` atau `tenant_id` dari payload sebagai otoritas. Bila ada location ID, backend memastikan lokasi aktif, milik/diizinkan bagi tenant, dan sesuai schedule siswa itu.

## 9.3 Response sukses contoh

```json
{
  "status": "accepted",
  "attendance_event_id": "<server-generated-id>",
  "event_type": "CHECK_IN",
  "server_time": "<ISO-8601 timestamp with timezone>",
  "location_validation": {
    "valid": true,
    "distance_m": 18.4,
    "accuracy_m": 12.0
  }
}
```

Nilai di atas hanya ilustrasi format; server menghasilkan ID, waktu, jarak, dan status sebenarnya. Jangan mengembalikan storage key privat atau koordinat siswa lain.

## 9.4 Kode kegagalan konsisten

| Kode | Makna / tindakan UI |
|---|---|
| `AUTH_REQUIRED` | Login ulang. |
| `TENANT_ACCESS_DENIED` | Pengguna tidak memiliki akses ke organisasi tersebut. |
| `LOCATION_PERMISSION_REQUIRED` | Aktifkan izin lokasi lalu coba ulang. |
| `LOCATION_UNAVAILABLE` | Aktifkan layanan lokasi atau pindah ke area dengan sinyal lebih baik. |
| `GPS_ACCURACY_TOO_LOW` | Tunggu akurasi membaik dan ambil lokasi kembali. |
| `OUTSIDE_GEOFENCE` | Pengguna berada di luar radius absensi yang berlaku. |
| `PHOTO_REQUIRED` / `INVALID_PHOTO` | Ambil ulang atau pilih alur kamera yang didukung. |
| `ALREADY_CHECKED_IN` / `ALREADY_CHECKED_OUT` | Tampilkan status yang sudah tersimpan; jangan mengulang mutasi. |
| `CHECK_IN_REQUIRED` | Lakukan absen masuk atau hubungi pembina jika ada kasus khusus. |
| `ATTENDANCE_WINDOW_CLOSED` | Tampilkan aturan/jadwal dan alur koreksi yang sah. |
| `SUBSCRIPTION_RESTRICTED` | Tampilkan status layanan dan instruksi billing sesuai kebijakan. |
| `RATE_LIMITED` | Minta pengguna menunggu sebelum mencoba kembali. |

Format respons: `{"code": "...", "message_id": "...", "detail": "..."}` — `message_id` dipetakan ke teks Indonesia di frontend (GEO-08). HTTP status konsisten: `400` input tidak valid, `401/403` autentikasi/otorisasi, `409` konflik/duplikasi, `413` file terlalu besar, `429` rate limit, `5xx` kegagalan server. Jangan menyertakan stack trace ke pengguna.

# 10. Desain Alur Absensi dan Geofence

## 10.1 Alur frontend (check-in)

1. Frontend (`attendance.js` + modul ES): minta izin kamera + geolocation; tangkap frame dari `getUserMedia` (facingMode user; fallback `<input capture>` bila tak didukung — IMG-01). Situs wajib HTTPS pada staging/production. Tampilkan preview agar siswa dapat mengambil ulang sebelum mengirim.
2. Kompresi di browser: canvas resize sisi terpanjang ≤ 1280 px → `canvas.toBlob('image/jpeg', 0.78)` (**default, bisa diubah**; PRD IMG-03). Jika browser tidak mendukung, kirim file asli dan biarkan backend normalisasi.
3. Dapatkan `getCurrentPosition` (high accuracy, timeout ~10 s); kirim `lat, lng, accuracy, client_request_id`.
4. Upload multipart ke `/api/v1/attendance/check-in/` dengan tombol terkunci saat in-flight dan indikator proses.
5. Respons: konfirmasi + `occurred_at` server, atau error terkode. Kegagalan tidak pernah dikirim sebagai sukses (PRD §5.1.9).

Check-out: sama, plus precheck bahwa ada check-in sah untuk `work_date` dan belum ada check-out (ATT-02), kecuali lewat koreksi resmi.

## 10.2 Pipeline backend (semua server-side, validasi urut)

1. Autentikasi + membership tenant aktif; pastikan tenant aktif dan kebijakan langganan tidak membatasi absensi (Tahap B).
2. Pastikan jenis absensi diizinkan untuk workday/session saat ini.
3. Rate-limit per user; cek `client_request_id` idempotensi.
4. Validasi struktur file dan batas upload awal sebelum proses berat.
5. Validasi koordinat: angka finite, rentang lat/lng masuk akal.
6. Validasi akurasi GPS tersedia dan tidak melewati ambang.
7. Ambil lokasi aktif melalui relasi tenant/schedule, bukan ID tidak terpercaya.
8. Hitung jarak haversine server-side ke lokasi yang berlaku; bandingkan terhadap `radius_m`; cek `accuracy ≤ max_accuracy_m` (GEO-04/05).
9. Validasi jadwal: apakah `now` (di TZ tenant) dalam jendela check-in/check-out; tentukan `work_date`.
10. Validasi konten foto: decode Pillow, cek tipe aktual/decoder, ukuran maks, jumlah pixel, gambar korup; strip EXIF; normalisasi/orientasi; simpan via storage backend → MediaAsset (IMG-04/05/06). Bila foto gagal → tolak, tidak ada record sah.
11. Transaksi: kunci `AttendanceDay` (`select_for_update`), cek belum ada check-in/out sah, buat `AttendanceRecord` + update `AttendanceDay.status` (ATT-01..04).
12. Tulis hasil validasi (jarak, akurasi, keputusan) ke record (GEO-06). Log tanpa koordinat presisi/data pribadi.
13. Commit transaction sebelum response sukses; tangani file yatim bila kegagalan lintas storage/database.

## 10.3 Kebijakan geofence awal

- Default: radius 100 m, akurasi GPS maksimum 50 m; dapat diubah admin sesuai hak akses (DEC-04).
- Titik pusat, radius, dan ambang akurasi disimpan di database, bukan hard-coded dalam JavaScript.
- Jarak dihitung server; nilai jarak dari browser tidak dipercaya.
- `accuracy_m` adalah perkiraan ketidakpastian lokasi, bukan bukti posisi akurat.
- MVP: terima bila koordinat dalam radius dan akurasi memenuhi batas; catat sebagai kebijakan v1. Penyesuaian (mis. margin batas) dibahas setelah uji lapangan.
- Jika akurasi terlalu rendah, lokasi kosong, atau izin ditolak: jangan catat event sebagai absensi sah.
- Tidak ada continuous tracking; ambil lokasi hanya saat absensi.
- Foto + GPS tidak menjamin identitas/posisi bebas manipulasi; sediakan kontrol pembina dan alur koreksi.

## 10.4 Koreksi pembina

POST corrections → validasi peran; simpan old/new value; update status AttendanceDay ke `dikoreksi`; record asli dipertahankan; tulis AuditLog (pelaku, waktu, objek, alasan) — ATT-09, AUD-01.

# 11. Desain Foto dan Media Storage

## 11.1 Pipeline gambar

1. Kamera depan via API browser; fallback input kamera pada browser tertentu; HTTPS wajib.
2. Kompresi browser: target sisi terpanjang maks 1280 px, kualitas JPEG awal 75–80; target tipikal 100–300 KB (target optimasi, bukan jaminan).
3. Hard limit upload awal (default 5 MB, bisa diubah) dan batas dimensi/pixel untuk melindungi server dari file ekstrem.
4. Backend memeriksa file signature/decoder, ukuran, tipe didukung, jumlah pixel, gambar korup. Jangan percaya nama file atau Content-Type browser saja.
5. Backend mengorientasikan gambar, mengonversi ke format disetujui, menghapus EXIF/metadata, lalu membuat output normalisasi.
6. Simpan output terproses saja sebagai default. Foto asli tidak disimpan kecuali ada keputusan produk, alasan sah, dan kebijakan retensi terpisah.
7. Simpan metadata + private storage key di `MediaAsset`.
8. Thumbnail di dashboard; foto penuh hanya untuk pengguna berhak.

## 11.2 Batas keamanan media

- Storage private; `MEDIA_ROOT` tidak diekspos via URL publik tanpa authorization.
- Endpoint foto memeriksa tenant, role, dan relasi foto dengan event sebelum mengirim file atau membuat signed URL singkat.
- Terapkan batas upload di reverse proxy (Nginx `client_max_body_size`) dan backend.
- **Jangan menerima SVG atau tipe file aktif lain** untuk bukti absensi; batasi ke format raster yang didukung.
- Batasi durasi pemrosesan dan ukuran gambar sebelum decode untuk menekan risiko DoS.
- Jangan mencatat isi foto ke log atau menyisipkan foto sebagai base64 dalam database/log.
- Definisikan retensi foto dan penghapusan terjadwal sebelum rilis komersial.
- Kebijakan cleanup file yatim dan retensi yang dapat dikonfigurasi.

## 11.3 Estimasi storage (perencanaan kapasitas)

`foto per bulan = siswa aktif × foto per hari × hari operasional`. Contoh PRD: 100 siswa × 2 foto/hari × 25 hari = 5.000 foto/bulan; rata-rata 200 KB ≈ 1 GB/bulan sebelum overhead, thumbnail, backup. Pantau kapasitas per tenant; jangan pakai contoh ini sebagai angka final kapasitas VPS.

## 11.4 Strategi storage bertahap

- **Development:** filesystem lokal di folder privat, `.gitignore`.
- **Pilot:** storage privat persisten bila backup dan disk dipantau (filesystem lokal di VPS, §6.2).
- **SaaS komersial:** object storage privat bila biaya/konektivitas sesuai; akses via mekanisme berizin/signed URL berumur pendek (DEC-09).
- Hindari foto sebagai public static asset.

# 12. Desain Langganan dan Pembayaran (Tahap B)

Billing dikerjakan setelah alur absensi stabil, tetapi antarmuka billing dan tenant ID mengikuti batas domain sejak awal.

## 12.1 Status langganan

Status minimal: `PENDING_PAYMENT`, `ACTIVE`, `PAST_DUE`, `SUSPENDED`, `CANCELLED`, `EXPIRED`; `TRIAL` hanya jika model trial disetujui. Transisi sah didefinisikan di satu service/domain module (BILL-02).

## 12.2 Komponen billing

Plan dan usage limits; Subscription dengan periode + grace; Invoice nomor unik/nominal IDR/jatuh tempo/status; PaymentTransaction dengan provider reference/method/nominal/status; PaymentWebhookEvent untuk idempotensi dan investigasi; provider adapter; mekanisme rekonsiliasi transaksi tertunda/notifikasi tidak diterima.

## 12.3 Aturan QRIS dan webhook

- Jangan membangun rails pembayaran QRIS sendiri; gunakan payment gateway yang sesuai dan menyetujui kebutuhan merchant.
- **QRIS ≠ autodebit:** QRIS dapat dipakai untuk pembayaran invoice bulanan bila didukung konfigurasi/provider; jangan mengasumsikan QRIS melakukan autodebit berulang otomatis.
- Webhook endpoint terjangkau provider via HTTPS, tetapi tidak dipercaya hanya karena dapat diakses publik.
- Verifikasi signature/credential sesuai spesifikasi resmi provider; bila perlu query status server-to-server.
- Cocokkan invoice/order ID, nominal, currency, merchant/account, provider reference, dan status transaksi.
- Simpan ID event/provider; pemrosesan idempotent. Duplikat → 200 tanpa efek.
- Jangan mengaktifkan subscription dari browser redirect saja; hanya webhook terverifikasi yang mengaktifkan (BILL-07/09).
- Secret provider hanya di environment production, tidak masuk Git/frontend.
- Tentukan biaya, settlement, refund, metode aktif, test/sandbox, dan syarat merchant sebelum memilih provider final (DEC-06).

## 12.4 Alur harian (Tahap B)

- Invoice dibuat saat langganan baru/perpanjangan (status `unpaid`).
- Adapter `PaymentProvider`: `create_payment(invoice)`, `verify_webhook(headers, body) -> NormalizedEvent`.
- Cron harian (management command): tandai invoice overdue, transisi `active → past_due → suspended` sesuai grace, kirim notifikasi in-app (BILL-11/12). Data tenant tidak dihapus.
- Rekonsiliasi: superadmin command/query + tindakan manual tercatat di AuditLog (BILL-13).

# 13. Keamanan, Privasi, dan Operasional

## 13.1 Kontrol minimum (implementasi konkret PRD §11)

| Area | Implementasi |
|---|---|
| HTTPS | Seluruh halaman, API, dan webhook (TLS via certbot, §6.3). |
| Password | Hasher default Django (Argon2/PBKDF2); tidak pernah plaintext (AUTH-04). |
| Sesi | `SESSION_COOKIE_AGE` terbatas, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, SameSite sesuai. |
| CSRF/XSS/SQLi | Mekanisme bawaan Django; template autoescape; ORM saja (tanpa raw SQL tanpa kebutuhan jelas). |
| Upload | Batas ukuran (default 5 MB), validasi konten Pillow, strip EXIF, file di luar webroot, akses via view terotorisasi (IMG-04/05/07). |
| IDOR / lintas tenant | Queryset selalu difilter organization dari membership; pengujian khusus (§16). |
| Rate limit | Login, absensi, upload, reset kredensial, webhook — per user/IP (django-ratelimit atau middleware ringan) (AUTH-07). |
| Permissions | Default-deny; setiap endpoint publik dinyatakan eksplisit. |
| Secret | `.env` + izin 600; tidak di repo; webhook secret terpisah; `.env`, dump DB, foto, file rahasia di luar Git. |
| Logging | Request ID, user/tenant id seperlunya, status, durasi, error; tanpa password/token/foto/koordinat presisi; audit log append-only. |
| Audit trail | Perubahan role, koreksi absensi, aturan lokasi, status tenant, invoice/payment/subscription, tindakan admin penting. |
| Kartu pembayaran | Tidak pernah disentuh sistem; provider-hosted saja (§11 poin 9). |

Catatan batas: sistem tidak mengklaim anti-spoofing GPS atau verifikasi wajah (PRD §11.1); pesan produk mengikuti batasan ini.

## 13.2 Kebijakan data

Sebelum produksi, pemilik produk menetapkan: tujuan pemrosesan, dasar/otorisasi, pemberitahuan kepada siswa/wali bila relevan, hak akses, retensi foto/lokasi, prosedur koreksi/penghapusan/ekspor, kontak pengaduan, backup lifecycle, respons insiden (DEC-10, DEC-11). Karena pengguna dapat berupa pelajar, lakukan tinjauan privasi dan hukum sebelum menerima organisasi eksternal.

## 13.3 Backup dan pemulihan

- Database: cron harian `pg_dump -Fc` ke `~/ganeshatech-presensi/backups/` (§6.2/§6.3), retensi 14 hari (**default, bisa diubah**), salinan luar-VPS bila tersedia; kredensial backup terpisah dari server aplikasi bila memungkinkan.
- Foto: lifecycle/retensi dan kebutuhan backup disesuaikan kebijakan layanan.
- Prosedur pemulihan terdokumentasi (restore, urutan recovery, siapa yang berwenang) + diuji minimal sekali sebelum pilot selesai; simulasi pemulihan terulang sebelum komersial (PRD §13.1). Backup yang tidak pernah diuji belum membuktikan sistem dapat dipulihkan.
- RPO target 24 jam (daily dump); RTO final ditentukan sebelum komersial (PRD §12).

# 14. Observabilitas

- Logging: `logs/django.log` rotasi; request lambat (>500 ms) dan error dicatat; Sentry opsional Tahap B.
- Metrik: p95 latensi API (log/nginx), ukuran foto rata-rata (agregat MediaAsset), tingkat keberhasilan absensi, pertumbuhan storage — sesuai indikator PRD §14.
- Health check sederhana yang tidak membocorkan environment/secret.
- Monitoring production (Tahap 10): disk, object storage, error log, uptime, expiry TLS.

# 15. Strategi Pengujian

| Lapisan | Cakupan | Alat |
|---|---|---|
| Unit | validasi geofence (haversine, boundary radius/accuracy), state machine subscription, idempotensi, kompresi/normalisasi foto, number format uang | pytest + pytest-django |
| Integrasi API | seluruh endpoint DRF: happy path + error codes + otorisasi peran | DRF test client |
| Isolasi tenant (wajib, PRD §13.2) | suite khusus: user tenant A mencoba baca/tulis semua objek tenant B via URL/API → harus 403/404; dijalankan otomatis tiap CI | pytest |
| Duplikasi absensi | request paralel/retry menghasilkan tepat satu record sah (ATT-04) | pytest + threading |
| Webhook | signature salah, duplikat, out-of-order, nominal beda → tidak aktivasi ganda (BILL-08) | pytest |
| Manual perangkat nyata | berbagai HP/browser, titik dalam/luar radius, GPS indoor bengkel, izin ditolak, jaringan lambat, refresh saat upload, check-out tanpa check-in, akses objek tenant lain (PRD §15) | checklist pilot |

CI minimal: run test + migrasi check + audit isolasi tenant pada setiap push (GitHub Actions atau script lokal; tidak ada deploy otomatis tanpa persetujuan). Catat defect sebagai tugas terpisah; jangan menyatakan QA berhasil tanpa eksekusi nyata.

# 16. Rencana Implementasi Bertahap

Urutan mengikuti PRD §16 dan merupakan urutan dependensi. Coding agent hanya menerima satu tugas aktif pada satu waktu. Setiap tahap punya kriteria selesai (DoD PRD §19; rincian §17). Setelah keputusan login (DEC-01) dan stack minimum dipastikan, mulai dari bootstrap; jangan mulai billing atau mobile sebelum tenant, autentikasi, dan attendance core stabil.

**Tahap 0 — Bootstrap dan keputusan minimum**
- Buat repo/folder proyek + baseline dokumentasi; tetapkan versi Python/Django, dependency locking, cara run lokal.
- `.gitignore`, `.env.example`, README awal, pemisahan settings environment.
- Putuskan identifier login siswa (DEC-01) sebelum model User dibuat; **wajib** custom User model sebelum migrasi pertama.

**Tahap 1 — Fondasi (Project Foundation)**
- Scaffold Django (apps §3.1), settings base/local/staging/production, custom User + migrasi awal, PostgreSQL lokal, health endpoint, logging dasar, template base + static + halaman error, design system dasar, CI test.
- Selesai: proyek runnable, konfigurasi terdokumentasi, tidak ada secret di repo, login/logout berfungsi, migrasi jalan, test hijau.

**Tahap 2 — Identity, Membership, Tenant Boundary**
- Organization + Membership, login/logout sesi, roles & permission helpers, tenant context yang selalu verifikasi membership server-side, halaman per role, tenant-scoped queryset/service pattern, audit logging perubahan akun/role/status tenant.
- Selesai: akun aktif bisa login; user tidak bisa mengakses tenant yang bukan miliknya.

**Tahap 3 — Master data (Student & Organization Setup)**
- StudentProfile terikat membership+tenant, CRUD siswa + status aktif/nonaktif, pencarian/filter/pagination, AttendanceLocation + AttendancePolicy (koordinat/radius/ambang akurasi, validasi), impor CSV/XLSX setelah CRUD manual stabil.
- Selesai: admin bisa kelola siswa & lokasi.

**Tahap 4 — Media Pipeline**
- Modul JS kamera/preview/kompresi/status proses; model MediaAsset + storage adapter; validasi file server-side, batas upload, normalisasi; hapus EXIF; file tidak dapat diakses publik tanpa izin; akses foto terotorisasi + thumbnail dashboard; kebijakan cleanup file yatim dan retensi.
- Catatan: kamera/geolocation browser butuh HTTPS di staging/production; uji browser mobile aktual dilakukan manual.

**Tahap 5 — Attendance Engine**
- AttendancePolicy/AttendanceDay, AttendanceRecord (in/out), service geofence server-side, urutan validasi + error codes konsisten, transaksi + `select_for_update` + constraint + idempotensi, simpan waktu server/koordinat/accuracy/jarak/keputusan/foto terproses/tenant, endpoint today/check-in/check-out/my-records, check-out membutuhkan check-in sah kecuali koreksi resmi.
- Selesai: kriteria PRD §13.1 poin 1–6 lolos pada perangkat nyata.

**Tahap 6 — Student UI, Dashboard, Reports, Audit**
- Dashboard siswa dengan tombol sesuai status; alur izin kamera/lokasi/preview/validasi/upload; dashboard pembina (filter, pagination, thumbnail); detail dengan bukti foto berizin; koreksi beralasan + audit log; ekspor CSV dulu (XLSX opsional pilot); status gagal/jaringan lambat tanpa sinyal palsu sukses.
- Selesai: PRD §13.1 poin 7–8.

**Tahap 7 — Pilot dan Hardening**
- Pengamanan foto (auth view), rate limit, backup + uji pemulihan terdokumentasi, pengujian GPS bermasalah, perbaikan pesan error.
- Pemeriksaan manual pemilik proyek: ponsel Android/iPhone tersedia, kamera, izin GPS, indoor/outdoor, jaringan lambat, refresh saat upload; dalam/luar radius, akurasi buruk, izin ditolak, GPS tidak tersedia; dua request berdekatan, retry setelah timeout, check-out tanpa check-in, check-in ganda; membuka ID/foto/endpoint tenant lain; ukuran file final, akses foto, rekap, koreksi, audit log, backup dan pemulihan.
- Selesai: seluruh PRD §13.1.

**Tahap 8 — SaaS Multi-tenant & Plan Entitlements**
- Admin platform dan pengelolaan tenant; Plan/Subscription + limits/features; middleware/service menegakkan entitlement di backend; onboarding/invitation organisasi (DEC-03); halaman penggunaan paket; pembatasan tenant suspended/expired tanpa hapus data; ekspor data tenant + kebijakan penutupan/retensi.

**Tahap 9 — Invoice & Payment Gateway**
- Invoice + nomor unik; payment adapter interface; pilih provider setelah evaluasi merchant eligibility, biaya, QRIS/VA/e-wallet, settlement, webhook (DEC-06); checkout dari server; webhook signature validation, query status, deduplication, idempotent billing service; pencocokan invoice/gross amount/currency/provider ID/status; halaman status transaksi & invoice; pengingat jatuh tempo, grace, suspend/expired, rekonsiliasi; sandbox sebelum live; jangan klaim pembayaran berhasil hanya dari redirect browser.

**Tahap 10 — Production Readiness**
- Domain + HTTPS; environment production DEBUG off + secret aman; migrasi terkendali + rollback plan; backup/restore teruji; monitoring disk/storage/error/uptime/TLS; kebijakan privasi, ToS, support contact, retensi foto/lokasi, prosedur incident; batas paket, kapasitas, limit request; uji tenant isolation + alur pembayaran di staging; pilot tenant terbatas sebelum pemasaran luas.
- Selesai: seluruh PRD §13.2.

**Tahap 11 — PWA dan Mobile API (Tahap C)**
Setelah web stabil dan pola penggunaan diketahui (di luar lingkup implementasi dokumen ini; API v1 sudah disiapkan): perkuat API contracts/versioning; tentukan autentikasi mobile (token expiry/refresh atau OAuth/OIDC; jangan simpan password di aplikasi); token revoke, device/session management, penyimpanan token aman; PWA/offline UI terpisah (absensi offline tidak otomatis sah); pilih framework Android/iOS (DEC-13) berdasarkan kebutuhan kamera/lokasi/update/distribusi/pemeliharaan; mobile memakai endpoint dan attendance service yang sama, bukan menduplikasi aturan bisnis.

# 17. Kriteria Penerimaan per Tahap

## 17.1 Project Foundation
- Proyek dijalankan dengan instruksi README; konfigurasi lokal tidak hard-coded ke production.
- Custom User model ditetapkan sebelum migration pertama; database via environment; tidak ada secret/file media nyata di Git.

## 17.2 Tenant & Auth
- Pengguna tidak login tidak bisa membuka halaman privat; role siswa tidak mendapatkan endpoint admin.
- Tenant A tidak dapat membuka data tenant B dengan mengganti URL, ID, parameter, atau body request; semua object dari input diverifikasi terhadap tenant aktif.

## 17.3 Attendance & Media
- Foto diperkecil sebelum dikirim bila browser mendukung; server tetap membatasi dan menormalisasi.
- Foto salah format, korup, terlalu besar, atau pixel ekstrem ditolak dengan pesan aman.
- Backend menentukan jarak dan waktu resmi; absensi di luar radius/akurasi tidak menjadi absensi sah.
- Check-in/out ganda dan retry tidak membuat event ganda.
- Foto hanya dapat dilihat pemilik data dan staf berizin pada tenant yang tepat.
- Koreksi menyimpan alasan dan jejak perubahan.

## 17.4 Billing
- Invoice tidak menjadi paid hanya karena halaman redirect sukses.
- Webhook tidak valid ditolak/diabaikan aman; webhook duplikat tidak memperpanjang subscription dua kali.
- Nominal/currency/provider reference tidak cocok tidak mengaktifkan paket.
- Transaksi tertunda punya status dan jalur rekonsiliasi jelas; subscription expiration tidak menghapus catatan absensi pelanggan.

## 17.5 Production
- HTTPS berlaku untuk web, API, dan webhook; `DEBUG=False`, secret eksternal, host/origin dibatasi.
- Backup dapat dipulihkan mengikuti dokumentasi.
- Log tidak memuat password, token provider, foto, atau koordinat presisi yang tidak perlu.
- Admin mengetahui prosedur pemulihan, penangguhan tenant, incident response, dan ekspor data.

# 18. Instruksi Kerja untuk AI Coding Agent

Bagian ini menyesuaikan workflow implementasi: AI mengerjakan perubahan kode sesuai ruang lingkup; pemeriksaan manual dilakukan bersama pemilik proyek setelahnya. Jangan meminta AI mengklaim hal yang belum dilakukan.

## 18.1 Aturan global

1. Baca `PRD.md`, dokumen teknis ini dan dokumentasi proyek sebelum mengubah file.
2. Kerjakan **satu task ID** dari Implementation Backlog per instruksi.
3. **Implementation only; code changes only; no QA/testing; no commit.** Jangan menjalankan rangkaian pengujian, browser test, deployment, atau membuat commit kecuali pemilik proyek secara eksplisit mengubah instruksi.
4. Jangan mengubah file di luar scope tanpa alasan kuat; jika dependensi baru diperlukan, jelaskan kenapa dan tambahkan hanya yang dibutuhkan.
5. Jangan merombak arsitektur, mengganti stack, mengganti custom User model, mereset database, **atau menyentuh `~/ganesha-tech` dan `/opt/ganeshatech-wa` di VPS** tanpa persetujuan.
6. Jangan membuat klaim seolah fitur sudah diuji. Akhiri dengan ringkasan perubahan dan langkah manual berikutnya.
7. Jangan menyertakan secret, data siswa nyata, foto, atau lokasi riil di source code, prompt, fixture publik, atau log.
8. Pertahankan tenant isolation, server-side validation, idempotensi, dan audit trail.
9. Jika kebutuhan belum pasti, gunakan asumsi paling aman yang mudah diubah dan cantumkan di output; jangan menambah fitur besar di luar PRD.

## 18.2 Template task

```text
PROJECT: Platform Absensi dan Manajemen TeFa
SOURCE OF TRUTH:
- docs/PRD.md
- docs/TECHNICAL_DESIGN.md (dokumen ini)

TASK ID: [isi satu ID dari backlog]
TASK NAME: [nama tugas]
SCOPE:
- [perubahan yang diperbolehkan]
OUT OF SCOPE:
- [fitur yang belum dikerjakan]
ACCEPTANCE REQUIREMENTS:
- [perilaku yang harus tersedia setelah implementasi]
CONSTRAINTS:
- Implementation only; code changes only.
- No QA, tests, browser testing, deployment, or commit.
- Jangan mengubah arsitektur/stack atau file yang tidak terkait tanpa alasan kuat.
- Semua aturan keamanan dan izin harus berada di backend.
- Jangan menyentuh layanan lain di VPS (~/ganesha-tech, /opt/ganeshatech-wa).
DELIVERABLE:
- Implementasi kode untuk tugas ini.
- Ringkasan file yang diubah.
- Migrasi/configuration manual yang diperlukan.
- Asumsi dan langkah manual berikutnya yang belum dilakukan.
- Jangan mengklaim pengujian atau verifikasi yang belum dijalankan.
```

## 18.3 Definition of Done untuk satu task

- Perilaku sesuai acceptance requirements task.
- Perubahan dibatasi pada ruang lingkup yang disetujui.
- Migrasi/konfigurasi yang diperlukan disertakan dan terdokumentasi.
- Otorisasi dan validasi backend tidak dilewati.
- Tidak ada secret/data nyata yang tertinggal.
- Ringkasan perubahan dan pekerjaan manual berikutnya jelas.

# 19. Keputusan Terbuka (DEC-01..13) dan Default Teradopsi

Keputusan berikut tidak menghalangi penulisan fondasi umum, tetapi harus diputuskan sebelum modul terkait masuk implementasi final. Nilai default teradopsi dari usulan PRD §17 dan **bisa diubah** oleh pemilik produk.

| ID | Keputusan | Default yang dipakai dokumen ini | Tenggat keputusan |
|---|---|---|---|
| DEC-01 | Login siswa menggunakan apa? | ID siswa (username) + password dibuat admin | Sebelum custom User/migrasi pertama |
| DEC-02 | Nama produk dan domain | Nama kerja sementara | Sebelum branding/peluncuran publik |
| DEC-03 | Registrasi tenant | Undangan/admin platform dulu; self-service nanti bila perlu | Sebelum tenant onboarding |
| DEC-04 | Radius dan akurasi GPS | Radius 100 m, akurasi maksimum 50 m | Sebelum pilot lapangan |
| DEC-05 | Model shift/jadwal | Satu sesi harian untuk pilot (`session_key` tunggal) | Sebelum model attendance final |
| DEC-06 | Provider payment gateway | Belum dipilih; desain via adapter; evaluasi resmi + sandbox | Sebelum billing |
| DEC-07 | Harga dan batas paket | Belum diputuskan | Sebelum halaman penjualan/billing live |
| DEC-08 | Grace period | 7 hari | Sebelum billing live |
| DEC-09 | Storage foto produksi | Filesystem lokal dulu; object storage privat saat Tahap B bila anggaran memungkinkan | Sebelum komersial |
| DEC-10 | Retensi foto/lokasi | Buat kebijakan tertulis sebelum pelanggan eksternal | Sebelum pilot data nyata/peluncuran umum |
| DEC-11 | Pemberitahuan orang tua/wali dan privasi pengguna pelajar | Ditinjau sesuai konteks pelanggan dan hukum berlaku | Sebelum pelanggan eksternal |
| DEC-12 | Paket annual, refund, upgrade/downgrade, prorata | Tunda setelah invoice bulanan stabil | Setelah v1.0 |
| DEC-13 | Native mobile framework | Belum diputuskan | Setelah web/API tervalidasi |

Default teknis lain yang teradopsi (bisa diubah): dimensi foto ≤ 1280 px sisi terpanjang; target ukuran foto 100–300 KB; batas upload 5 MB; kualitas JPEG 0.78; format laporan CSV dasar (XLSX opsional pilot); notifikasi in-app dulu; port Gunicorn `127.0.0.1:8010` (cek port bebas saat provisioning, §6.3); retensi backup 14 hari.

# 20. Risiko Teknis & Mitigasi Operasional

| Risiko | Mitigasi dalam desain ini |
|---|---|
| Port/konfigurasi bentrok dengan aplikasi lain di VPS | Cek port sebelum provisioning (`sudo ss -tlnp`); systemd unit & venv terpisah; aturan keras §6.1 (tidak menyentuh `~/ganesha-tech` dan `/opt/ganeshatech-wa`) |
| PostgreSQL resource bersama | `shared_buffers` default; hanya listen localhost; monitor ukuran DB |
| Disk penuh karena foto | Kompresi browser + normalisasi server + retensi + monitoring growth (PRD §14) |
| Race absensi paralel | `select_for_update` + unique constraint (§8.4) |
| Webhook hilang/duplikat | Unique event id + rekonsiliasi manual terjadwal |
| Single VPS (no HA) | Diterima untuk pilot; backup harian + prosedur pemulihan; HA dievaluasi sebelum komersial |
| GPS indoor bengkel buruk | Uji lapangan per perangkat/titik; radius/akurasi dapat dikonfigurasi per lokasi; jalur koreksi (PRD §15) |

# 21. Referensi Teknis

Sumber resmi untuk diverifikasi kembali saat implementasi, terutama sebelum memilih versi paket, provider, dan membuat deployment production:

1. Django — download dan supported versions: https://www.djangoproject.com/download/ (per 12 Oktober 2026: Django 5.2 LTS, extended support hingga April 2028, patch 5.2.18; verifikasi ulang saat bootstrap).
2. Django REST Framework — permissions: https://www.django-rest-framework.org/api-guide/permissions/ (setiap endpoint harus punya izin yang disengaja).
3. Django REST Framework — authentication: https://www.django-rest-framework.org/api-guide/authentication/ (authentication ≠ authorization).
4. PostgreSQL — versioning policy: https://www.postgresql.org/support/versioning/ (pilih major yang masih didukung; jangan EOL).
5. Midtrans — HTTP(S) notification/webhook: https://docs.midtrans.com/docs/https-notification-webhooks (URL HTTPS, verifikasi keaslian, redirect browser bukan konfirmasi pembayaran).
6. Bank Indonesia — QRIS: https://www.bi.go.id/id/fungsi-utama/sistem-pembayaran/ritel/kanal-layanan/QRIS/default.aspx (ketentuan dan layanan provider diverifikasi saat memilih payment gateway).

---

**Akhir dokumen — Technical Design & Implementation Plan v1.1**

Dokumen ini adalah baseline teknis pendamping PRD v1.0. Perubahan keputusan teknis dicatat sebagai revisi dokumen ini agar semua coding agent dan pengembang konsisten dengan PRD.
