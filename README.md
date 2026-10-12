# GaneshaTech Presensi — Platform Absensi & Manajemen TeFa

Platform web multi-tenant untuk absensi (selfie + GPS geofence) dan manajemen operasional Teaching Factory, dengan fondasi SaaS berlangganan.

## Dokumen Produk

- **PRD:** [docs/PRD_Platform_Absensi_TeFa_v1.0.md](docs/PRD_Platform_Absensi_TeFa_v1.0.md) — baseline produk v1.0 (12 Oktober 2026). Semua coding agent & pengembang wajib membaca PRD ini sebelum mengubah kode (lihat Bagian 18 PRD untuk ketentuan kerja AI coding agent).

## Rencana rilis

| Tahap | Isi |
|---|---|
| A — MVP pilot | Login, lokasi + geofence, absen masuk/pulang (kamera + kompresi browser), validasi server, dashboard, koreksi + audit log |
| B — SaaS v1.0 | Multi-tenant, isolasi data, paket, invoice, pembayaran QRIS via webhook |
| C — Setelah v1.0 | PWA, aplikasi Android/iOS (API sama), uang saku, izin/sakit, notifikasi WA/email |

## Stack (rekomendasi awal PRD §10.2)

Python + Django + Django REST Framework, PostgreSQL, templates server-rendered + JS modular, storage abstraksi (filesystem → object storage), adapter payment gateway.
