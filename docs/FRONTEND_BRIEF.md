# BRIEF — AI Coding Agent FRONTEND
## Platform Absensi TeFa — Dashboard Siswa + Alur Absensi

> **Untuk agent:** baca brief ini penuh sebelum menulis kode. Ini kontrak kerjamu.
> Tugas: implementasi frontend (templates + CSS + JS). **JANGAN** menyentuh backend.

---

## 1. Konteks proyek (wajib paham)

Platform absensi Teaching Factory: siswa absen masuk/pulang lewat browser HP dengan **foto selfie + GPS geofence**. Website mobile-first, bahasa Indonesia, basis pelajar SMK.

Sumber kebenaran (WAJIB dibaca dari repo):
- `docs/PRD_Platform_Absensi_TeFa_v1.0.md` — §5 alur pengguna, §8 UX, §11 keamanan
- `docs/Technical_Design_Implementation_Plan_v1.2.md` — **§9 Desain API** (kontrakmu), **§10 Frontend** (struktur kerjamu), **§17 kriteria penerimaan**

Kondisi repo saat ini: fondasi Django sudah jalan (Tahap 1 selesai). Backend API `/api/v1/` **belum diimplementasikan** — kamu mengerjakan frontend **dari kontrak API di TDIP §9** dengan data dummy, sehingga bisa paralel.

## 2. Stack & batasan teknis (TIDAK Boleh dilanggar)

| Aturan | Detail |
|---|---|
| Frontend stack | Django Templates (server-rendered) + **JS modular native (ES modules, tanpa bundler)** + CSS responsif. Bukan React/Vue/SPA. |
| Design system | Sudah ada `static/css/base.css` (variable warna, .card, .btn, form). Perluas, jangan ganti fondasi. Mobile-first. |
| **File yang boleh kamu sentuh** | `templates/`, `static/css/`, `static/js/` SAJA |
| **File yang DILARANG disentuh** | `apps/**`, `config/**`, `requirements/**`, migrasi, `pytest.ini` — kalau butuh data/endpoint baru, CATAT di laporan, jangan buat sendiri |
| Validasi | Semua aturan bisnis (geofence, waktu, idempotensi) di server. JS hanya mengumpulkan input & UX. Jangan duplikasi logika validasi di JS. |
| Bahasa UI | Indonesia. Format tanggal/angka Indonesia. Zona waktu Asia/Jakarta. |
| Aksesibilitas | Kontras cukup, label form jelas, fokus keyboard, pesan status tidak hanya mengandalkan warna. |
| Git | `git pull` sebelum mulai; kerja di task terpisah; commit terpisah frontend saja; jangan commit backend. |

## 3. Struktur yang harus kamu buat (TDIP §10)

```
templates/
├── base.html                 # sudah ada — perluas nav/user area
├── accounts/
│   └── login.html            # Layar 1: login email + password
├── attendance/
│   ├── student_home.html     # Layar 2: dashboard siswa
│   ├── capture.html          # Layar 2b: wizard absen (inti!)
│   └── history.html          # riwayat absensi siswa
└── dashboard/
    └── pembina.html          # Layar 3: dashboard pembina

static/css/
└── base.css                  # sudah ada; tambah komponen (tabel, badge, stepper)

static/js/
├── camera.js         # getUserMedia kamera depan (facingMode: 'user'), fallback <input capture>
├── geo.js            # getCurrentPosition (high accuracy, timeout ~10s), pesan error BERBEDA per kegagalan
├── compress.js       # canvas resize sisi terpanjang ≤1280px → toBlob('image/jpeg', 0.78)
├── attendance.js     # orkestrasi wizard + submit + idempotency key + lock tombol
└── dashboard.js      # filter/tabel pembina (fetch + render)
```

## 4. Tugas utama: alur absensi (jantung pilot)

Wizard di `capture.html` + `attendance.js`, tahapan yang harus TAMPIL jelas ke siswa:

1. **Izin kamera** → kalau ditolak: pesan "izinkan kamera untuk absen" + tombol coba lagi. Fallback: `<input type="file" accept="image/*" capture="user">`.
2. **Preview foto** → siswa bisa ambil ulang sebelum kirim.
3. **Ambil lokasi** → tampilkan status: "mencari lokasi…", sukses (akurasi ±X m), atau error spesifik.
4. **Kirim** → upload multipart, tombol **terkunci** saat in-flight + indikator proses; cegah klik ganda.
5. **Hasil** → sukses (tampilkan waktu server) ATAU pesan gagal yang jelas. **Kegagalan TIDAK PERNAH ditampilkan sebagai sukses.**

Pesan error per kode API (TDIP §9.4) — petakan ke teks Indonesia + tindakan berikutnya, minimal:

| Kode | Pesan UI |
|---|---|
| `LOCATION_PERMISSION_REQUIRED` | "Aktifkan izin lokasi, lalu coba lagi." |
| `LOCATION_UNAVAILABLE` | "Lokasi tidak terdeteksi. Pastikan GPS aktif / cari area terbuka." |
| `GPS_ACCURACY_TOO_LOW` | "Sinyal GPS lemah (akurasi ±X m). Tunggu sebentar, lalu coba lagi." |
| `OUTSIDE_GEOFENCE` | "Kamu berada di luar area absensi." |
| `PHOTO_REQUIRED` / `INVALID_PHOTO` | "Foto tidak valid. Ambil ulang selfie." |
| `ALREADY_CHECKED_IN` / `ALREADY_CHECKED_OUT` | Tampilkan status tersimpan, jangan minta absen lagi. |
| `CHECK_IN_REQUIRED` | "Kamu belum absen masuk hari ini. Hubungi pembina jika ada kendala." |
| `ATTENDANCE_WINDOW_CLOSED` | "Di luar jam absensi. Lihat jadwal / hubungi pembina." |
| `RATE_LIMITED` | "Terlalu sering. Tunggu sebentar, lalu coba lagi." |
| `AUTH_REQUIRED` | Arahkan ke halaman login. |
| jaringan gagal/timeout | "Koneksi terputus. Cek internet, lalu coba lagi." |

**Idempotency:** tiap upaya absen generate `client_request_id` (crypto.randomUUID) sekali per percobaan; simpan di sessionStorage sampai respons final; retry pakai key yang sama.

## 5. Kontrak API yang kamu konsumsi (ringkasan — detail di TDIP §9)

Base: `/api/v1/` (belum ada — pakai **data dummy** + fitur switch, lihat §7).

| Endpoint | Metode | Kebutuhan frontend |
|---|---|---|
| `/auth/login/` | POST | email + password (Bukan username/ID siswa!) |
| `/attendance/today/` | GET | status hari ini → tentukan tombol aktif (masuk/pulang/sudah lengkap) |
| `/attendance/check-in/`, `/check-out/` | POST | multipart: `photo`, `latitude`, `longitude`, `accuracy_m`, `client_request_id` |
| `/attendance/my-records/` | GET | tabel riwayat + pagination |
| `/attendance/records/` | GET | pembina: filter tanggal/siswa/kelompok/status + pagination |
| `/attendance/records/{id}/corrections/` | POST | pembina: form koreksi, alasan WAJIB |
| `/photos/{id}/` | GET | `<img>` bukti foto (endpoint terotorisasi, bukan file publik) |

Response sukses check-in contoh:
```json
{"status": "accepted", "attendance_event_id": "...", "event_type": "CHECK_IN",
 "server_time": "<ISO-8601>", "location_validation": {"valid": true, "distance_m": 18.4, "accuracy_m": 12.0}}
```
Error format: `{"code": "OUT_OF_GEOFENCE", "message": "...", "detail": "..."}` — tampilkan berdasarkan `code`, jangan parse teks.

## 6. Layar & konten

**Layar 1 — Login** (`accounts/login.html`): field email + password, link lupa password, error state "email atau password salah" (generik — jangan bocorkan yang mana salah).

**Layar 2 — Dashboard siswa** (`student_home.html`): kartu status hari ini (belum masuk / sudah masuk jam 08:03 / sudah pulang), tombol BESAR Absen Masuk / Absen Pulang sesuai status (yang tidak relevan nonaktif), ringkasan kehadiran minggu ini, link riwayat.

**Layar 2b — Wizard absen** (`capture.html`): stepper 4 langkah (Kamera → Foto → Lokasi → Konfirmasi), tiap langkah punya state gagal. Prioritas kamera depan.

**Layar 3 — Dashboard pembina** (`pembina.html`): kartu ringkasan (hadir/belum/pulang/perlu ditinjau), tabel siswa (foto thumbnail kecil, nama, jam masuk, jam pulang, status badge, jarak dari lokasi), pencarian + filter tanggal/kelompok/status, pagination, tombol lihat foto (modal/detail), aksi koreksi (modal: nilai baru + alasan wajib).

## 7. Karena API belum ada: mode dummy

Buat `static/js/api.js` — satu modul yang membungkus semua `fetch`:
- `?dummy=1` (atau konstanta file) → balas data dummy dengan delay simulasi, termasuk skenario gagal yang bisa dipilih (out of radius, akurasi rendah, dsb) untuk demo/tes.
- Implementasi nyata (fetch ke `/api/v1/`) sudah tertulis tapi memang akan gagal sampai backend siap — itu tidak masalah.
- Ini penting: saat backend jadi, frontend tinggal mematikan dummy, tanpa refactor.

## 8. Definition of Done (cek sebelum laporkan selesai)

- [ ] Semua layar di atas ada + navigasi bisa dicoba
- [ ] Alur absen lengkap: izin → kamera depan → preview/retake → lokasi → submit terkunci → hasil
- [ ] Setiap kode error §4 punya pesan Indonesia + tindakan lanjut
- [ ] Idempotency key bekerja (retry tidak membuat dua percobaan)
- [ ] Dummy mode bisa mensimulasikan sukses & tiap skenario gagal
- [ ] Mobile-first: dicoba minimal di viewport 360px; desktop tetap wajar
- [ ] Tidak ada file di luar `templates/` + `static/` yang berubah
- [ ] Tidak ada data siswa nyata/foto asli — dummy saja
- [ ] Laporan: daftar file dibuat/diubah, cara menjalankan, kebutuhan API/endpoint yang kamu catat, asumsi. **Jangan klaim sudah dites ke backend nyata.**
