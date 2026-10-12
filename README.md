# GaneshaTech Presensi — Platform Absensi & Manajemen TeFa

Platform web multi-tenant untuk absensi (selfie + GPS geofence) dan manajemen operasional Teaching Factory, dengan fondasi SaaS berlangganan.

## Dokumen Produk

- **PRD:** [docs/PRD_Platform_Absensi_TeFa_v1.0.md](docs/PRD_Platform_Absensi_TeFa_v1.0.md) — baseline produk v1.0 (12 Oktober 2026)
- **TDIP:** [docs/Technical_Design_Implementation_Plan_v1.2.md](docs/Technical_Design_Implementation_Plan_v1.2.md) — baseline teknis (gabungan; DEC-01: login email-only)

Semua coding agent wajib membaca kedua dokumen sebelum mengubah kode (TDIP §18).

## Menjalankan development (lokal)

```bash
python3.12 -m venv .venv            # atau: uv venv --python 3.12 .venv
.venv/bin/pip install -r requirements/dev.txt
cp .env.example .env                # edit nilai bila perlu
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

Tes: `.venv/bin/python -m pytest -q`

## Struktur (TDIP §5)

- `config/settings/` — base / local / production (secret via `.env`, lihat `.env.example`)
- `apps/` — core, accounts (custom User email-only), tenants, students, attendance, media_assets, reports, audit
- `templates/`, `static/` — Django Templates + JS modular (ARC-03)
- `private_media/` — foto privat, di luar akses publik (IMG-07)

## Status implementasi

- [x] Tahap 0 — Bootstrap (repo, docs, deployment target VPS)
- [x] Tahap 1 — Fondasi (scaffold Django, custom User email-only + migrasi, settings terpisah, health check, logging, base template/CSS, pytest)
- [ ] Tahap 2 — Identity, Membership, Tenant Boundary
- [ ] Tahap 3 — Master data
- [ ] Tahap 4 — Media pipeline
- [ ] Tahap 5 — Attendance engine
- [ ] Tahap 6 — UI, dashboard, laporan, audit
- [ ] Tahap 7 — Pilot & hardening
- [ ] Tahap B — SaaS (multi-tenant penuh, billing QRIS)

## Rencana rilis (PRD §4)

| Tahap | Isi |
|---|---|
| A — MVP pilot | Login, lokasi + geofence, absen masuk/pulang (kamera + kompresi browser), validasi server, dashboard, koreksi + audit log |
| B — SaaS v1.0 | Multi-tenant, isolasi data, paket, invoice, pembayaran QRIS via webhook |
| C — Setelah v1.0 | PWA, aplikasi Android/iOS (API sama), uang saku, izin/sakit, notifikasi WA/email |

## Stack (TDIP §4)

Python 3.12 + Django 5.2 LTS + DRF, PostgreSQL (produksi) / SQLite (dev), templates server-rendered + JS modular, storage abstraksi, adapter payment gateway.
