---
title: "PRODUCT REQUIREMENTS DOCUMENT"
subtitle: "Platform Absensi dan Manajemen Teaching Factory (TeFa)"
author: "Dokumen Produk — Draft v1.0"
date: "12 Oktober 2026"
---

# Informasi Dokumen

| Atribut | Isi |
|---|---|
| Nama produk | Platform Absensi dan Manajemen TeFa (nama kerja) |
| Versi dokumen | PRD 1.0 |
| Status | Draft dasar untuk perencanaan dan implementasi bertahap |
| Tanggal | 12 Oktober 2026 |
| Platform awal | Website responsif, berorientasi penggunaan melalui browser HP |
| Platform lanjutan | PWA, aplikasi Android, dan aplikasi iOS |
| Model bisnis | SaaS dengan paket berlangganan |
| Bahasa utama | Bahasa Indonesia |
| Zona waktu awal | Asia/Jakarta; dapat dikonfigurasi per organisasi bila diperlukan |

> **Cara membaca dokumen:** kebutuhan bertanda **MUST** wajib ada sebelum rilis yang mencakup kebutuhan tersebut. **SHOULD** sangat disarankan tetapi dapat dijadwalkan setelah kebutuhan inti. **COULD** bersifat tambahan. Nilai seperti radius lokasi, ukuran foto, masa tenggang, dan target performa yang disebut sebagai default merupakan nilai awal untuk divalidasi selama pilot, bukan batas yang tidak boleh diubah.

# 1. Ringkasan Eksekutif

Produk ini adalah platform web multi-tenant untuk absensi dan pengelolaan operasional Teaching Factory (TeFa), dengan fondasi komersial sebagai perangkat lunak berlangganan (Software as a Service/SaaS). Siswa melakukan absensi masuk dan pulang melalui browser ponsel menggunakan foto selfie, lokasi GPS, dan pencatatan waktu oleh server. Pembina memantau kehadiran, melakukan koreksi dengan alasan yang tercatat, serta membuat laporan. Pengelola platform dapat mengatur organisasi pelanggan, paket, langganan, invoice, dan transaksi.

Produk dibangun sebagai website terlebih dahulu. Backend menyediakan API yang konsisten agar aplikasi Android dan iOS di kemudian hari menggunakan logika bisnis, aturan akses, dan database yang sama. Sejak awal, desain harus mendukung pemisahan data antarpelanggan, perlindungan foto dan lokasi, kompresi gambar, serta pembayaran melalui penyedia payment gateway yang mendukung kanal Indonesia termasuk QRIS.

Peluncuran dilakukan bertahap. Pilot awal membuktikan alur absensi pada satu organisasi. Rilis komersial menambahkan onboarding banyak organisasi, isolasi tenant, paket berlangganan, invoice, dan verifikasi pembayaran otomatis sebelum pelanggan umum diterima.

# 2. Visi, Masalah, dan Tujuan Produk

## 2.1 Visi

Menyediakan platform absensi dan manajemen TeFa yang mudah digunakan melalui ponsel, memiliki bukti kehadiran yang lebih kuat daripada absensi manual, efisien dalam penggunaan penyimpanan, dan dapat digunakan oleh banyak organisasi dengan model langganan.

## 2.2 Masalah yang ingin diselesaikan

1. Absensi manual sulit dipantau secara langsung dan memerlukan rekap ulang.
2. Bukti kehadiran dapat sulit diverifikasi jika hanya berupa tanda tangan atau pesan.
3. Foto dan lokasi absensi berpotensi menghabiskan penyimpanan apabila tidak diolah sebelum disimpan.
4. Pembina membutuhkan rekap yang dapat ditelusuri dan dikoreksi tanpa menghilangkan riwayat perubahan.
5. Produk yang disewakan kepada banyak sekolah/unit membutuhkan pemisahan data, kontrol paket, penagihan, serta pengelolaan pelanggan.
6. Website yang dibangun tanpa API dan pemisahan logika bisnis dapat menyulitkan pengembangan aplikasi Android/iOS di kemudian hari.

## 2.3 Tujuan

- Memungkinkan siswa melakukan absensi masuk dan pulang melalui web mobile.
- Mengumpulkan foto, waktu server, koordinat, akurasi GPS, dan hasil validasi lokasi untuk setiap absensi yang sah.
- Menolak atau menandai absensi yang tidak memenuhi aturan organisasi, dengan pesan yang mudah dipahami.
- Memungkinkan pembina mengelola siswa, lokasi, jadwal, koreksi, dan laporan.
- Memastikan satu pelanggan tidak dapat melihat atau mengubah data pelanggan lain.
- Mengurangi ukuran foto melalui pengolahan di browser dan normalisasi di backend.
- Menyiapkan fondasi paket langganan, invoice, dan pembayaran digital termasuk QRIS.
- Memisahkan backend dari antarmuka agar aplikasi mobile dapat menggunakan API yang sama.

## 2.4 Bukan tujuan rilis awal

- Menjamin anti-kecurangan 100%; GPS browser dapat dimanipulasi pada perangkat tertentu.
- Mengklaim verifikasi biometrik, pengenalan wajah, atau liveness detection tanpa modul khusus yang dirancang, diuji, dan diberi dasar pemrosesan data yang sesuai.
- Membuat aplikasi native Android/iOS pada rilis pertama.
- Mengimplementasikan penggajian atau uang saku penuh sebagai modul wajib rilis pertama.
- Menjadi sistem akademik lengkap, payroll, ERP bengkel, atau akuntansi umum.
- Mendukung absensi offline yang otomatis dianggap sah tanpa validasi server.

# 3. Sasaran Pengguna dan Peran

Satu instalasi platform dapat memiliki banyak organisasi pelanggan (tenant). Setiap akun biasa harus terikat pada organisasi yang sesuai. Peran platform berbeda dari peran organisasi.

| Peran | Lingkup | Kemampuan utama |
|---|---|---|
| Superadmin platform | Seluruh platform | Mengelola tenant, paket, langganan, pembayaran, status layanan, dan konfigurasi global |
| Admin/Owner organisasi | Satu tenant | Mengelola profil organisasi, pengguna, siswa, lokasi, jadwal, aturan absensi, dan laporan organisasi |
| Pembina/Operator | Satu tenant | Memantau absensi, melihat bukti, mengelola status kehadiran sesuai izin, mengajukan/melakukan koreksi tercatat, dan mengekspor laporan |
| Siswa | Akun sendiri dalam satu tenant | Melakukan absen masuk/pulang dan melihat riwayat absensinya sendiri |
| Kontak billing organisasi | Satu tenant | Melihat paket, invoice, status pembayaran, dan riwayat langganan; dapat digabung dengan Admin pada versi awal |
| Dukungan platform | Sesuai otorisasi khusus | Membantu pemecahan masalah dengan akses minimum dan jejak audit; akses ke foto/lokasi tidak diberikan secara otomatis |

## 3.1 Prinsip otorisasi

- Hak akses ditentukan di backend, bukan hanya dengan menyembunyikan tombol di frontend.
- Akses lintas tenant dilarang secara default.
- Siswa hanya melihat data akunnya sendiri, bukan foto atau catatan siswa lain.
- Pembina hanya mengakses organisasi yang ditugaskan kepadanya.
- Superadmin memiliki akses administratif lintas tenant, tetapi akses terhadap konten sensitif harus dapat diaudit dan dibatasi berdasarkan kebutuhan operasional.
- Perubahan peran, penonaktifan akun, koreksi absensi, dan perubahan data penting dicatat dalam audit log.

# 4. Ruang Lingkup dan Prioritas Rilis

## 4.1 Tahap A — MVP pilot internal

MVP pilot ditujukan untuk membuktikan kebutuhan inti pada satu organisasi terlebih dahulu.

- Login dan pengelolaan akun siswa/pembina.
- Profil organisasi dan setidaknya satu lokasi absensi.
- Pengaturan radius geofence dan ambang akurasi GPS.
- Absensi masuk dan pulang melalui browser ponsel.
- Pengambilan foto kamera dan kompresi sebelum upload.
- Validasi sisi server, pencatatan waktu server, koordinat, dan hasil validasi.
- Dashboard kehadiran hari ini dan pencarian dasar.
- Riwayat absensi dan ekspor laporan dasar.
- Koreksi manual dengan alasan dan audit log.
- Backup dan prosedur pemulihan minimum.

## 4.2 Tahap B — Rilis komersial SaaS v1.0

Sebelum menerima pelanggan eksternal dalam skala komersial, sistem harus menambahkan:

- Multi-tenant dan isolasi data yang dapat dibuktikan.
- Onboarding, pengaturan, dan status tiap organisasi.
- Paket, batas siswa/lokasi/admin/penyimpanan, serta fitur berdasarkan paket.
- Invoice dan langganan bulanan.
- Payment gateway dengan QRIS serta kanal lain sesuai dukungan provider.
- Verifikasi notifikasi server-to-server/webhook, penanganan notifikasi berulang, dan rekonsiliasi status transaksi.
- Pengingat jatuh tempo dan kebijakan masa tenggang.
- Halaman syarat layanan dan kebijakan privasi.
- Monitoring error, audit administratif, dan proses dukungan pelanggan.

## 4.3 Tahap C — Pengembangan setelah v1.0

- PWA yang lebih lengkap, termasuk instalasi shortcut dan notifikasi web jika didukung perangkat/browser.
- Aplikasi Android dan iOS yang memakai API yang sama.
- Modul uang saku/jam kerja dan aturan keterlambatan yang lebih lengkap.
- Pengajuan izin/sakit/cuti oleh siswa dengan alur persetujuan.
- Notifikasi WhatsApp/email/SMS melalui penyedia yang sesuai dan dengan persetujuan yang diperlukan.
- Multi-lokasi dengan penugasan siswa/jadwal per lokasi yang lebih fleksibel.
- Ekspor lanjutan, analitik, dan integrasi sistem sekolah.
- Fitur verifikasi foto lebih lanjut setelah studi kelayakan, privasi, biaya, dan akurasi.

# 5. Alur Pengguna Utama

## 5.1 Alur absensi masuk siswa

1. Siswa membuka website melalui browser ponsel dan login.
2. Sistem menampilkan organisasi, tanggal/waktu lokal, status absensi hari ini, serta tombol yang relevan.
3. Siswa memilih **Absen Masuk**.
4. Browser meminta izin kamera dan lokasi jika belum diberikan.
5. Siswa mengambil selfie melalui kamera. File dikompres sebelum dikirim.
6. Browser memperoleh koordinat dan tingkat akurasi GPS.
7. Server memvalidasi identitas, status langganan organisasi, aturan jadwal, lokasi yang digunakan, jarak, akurasi, format/ukuran foto, dan status absensi sebelumnya.
8. Jika valid, server menyimpan catatan absensi dan referensi foto, lalu mengembalikan konfirmasi beserta waktu server.
9. Jika tidak valid, server tidak membuat absensi sah dan menampilkan alasan yang jelas. Kegagalan tidak boleh ditampilkan sebagai berhasil.

## 5.2 Alur absensi pulang

1. Siswa login dan memilih **Absen Pulang**.
2. Sistem memastikan terdapat absen masuk yang sesuai dan belum ada absen pulang untuk sesi/hari tersebut.
3. Sistem mengulangi pengambilan foto, lokasi, serta validasi server.
4. Server menyimpan waktu pulang dan memperbarui status harian.
5. Jika tidak ada absen masuk atau data mengalami konflik, sistem menolak pengiriman otomatis dan mengarahkan siswa menghubungi pembina atau menggunakan alur koreksi resmi.

## 5.3 Alur koreksi oleh pembina

1. Pembina membuka catatan siswa dan memilih tindakan koreksi yang diizinkan.
2. Sistem meminta nilai baru dan alasan wajib.
3. Backend menyimpan perubahan dan merekam nilai sebelum/sesudah, pelaku, waktu, dan alasan.
4. Catatan asli tidak dihapus tanpa jejak. Laporan menampilkan status data yang sudah dikoreksi.

## 5.4 Alur pelanggan berlangganan

1. Admin organisasi mendaftar atau menerima undangan organisasi.
2. Admin memilih paket dan menyetujui syarat layanan serta kebijakan privasi.
3. Sistem menerbitkan invoice dan menyediakan metode pembayaran yang tersedia.
4. Pelanggan membayar, misalnya melalui QRIS.
5. Backend memverifikasi notifikasi dari payment gateway dan mencocokkan nominal, invoice, referensi transaksi, serta status.
6. Langganan diaktifkan/diperpanjang hanya setelah status pembayaran terkonfirmasi secara tepercaya.
7. Sistem mencatat riwayat transaksi dan mengirim konfirmasi.

# 6. Kebutuhan Fungsional

Prioritas: **P0** = wajib untuk pilot; **P1** = wajib sebelum SaaS komersial; **P2** = peningkatan setelah peluncuran awal.

## 6.1 Akun, autentikasi, dan sesi

| ID | Prioritas | Kebutuhan |
|---|---|---|
| AUTH-01 | P0 | Sistem menyediakan login dan logout yang aman untuk siswa, pembina, dan admin. |
| AUTH-02 | P0 | Admin dapat membuat, mengubah, menonaktifkan, dan mengatur ulang kredensial akun siswa. |
| AUTH-03 | P0 | Siswa hanya dapat melihat dan mengubah informasi profil terbatas yang diizinkan. |
| AUTH-04 | P0 | Password disimpan menggunakan mekanisme hashing aman dari framework; tidak pernah disimpan sebagai teks biasa. |
| AUTH-05 | P0 | Sesi memiliki batas waktu dan mekanisme logout; cookie produksi menggunakan pengaturan aman dan HTTPS. |
| AUTH-06 | P1 | Organisasi memiliki alur pemulihan akun yang sesuai dengan identitas pengguna; bila email siswa tidak tersedia, reset dapat dilakukan admin dengan prosedur audit. |
| AUTH-07 | P1 | Rate limit atau mekanisme perlindungan diterapkan pada percobaan login berulang. |
| AUTH-08 | P1 | Perubahan peran dan status akun tercatat dalam audit log. |

## 6.2 Organisasi dan isolasi tenant

| ID | Prioritas | Kebutuhan |
|---|---|---|
| TEN-01 | P1 | Setiap organisasi memiliki tenant ID unik dan profil sendiri. |
| TEN-02 | P1 | Seluruh data tenant yang relevan memiliki relasi/ruang lingkup organisasi yang jelas. |
| TEN-03 | P1 | Backend memvalidasi akses tenant pada setiap endpoint dan operasi baca/tulis. |
| TEN-04 | P1 | Sistem mencegah akses silang tenant melalui manipulasi URL, ID, parameter query, atau API. |
| TEN-05 | P1 | Superadmin dapat mengaktifkan, membatasi, menangguhkan, atau menutup tenant sesuai kebijakan. |
| TEN-06 | P1 | Organisasi dapat dikonfigurasi dengan nama, zona waktu, lokasi, aturan absensi, dan paket masing-masing. |
| TEN-07 | P1 | Tersedia prosedur ekspor dan penghapusan data tenant sesuai kebijakan retensi dan kewajiban yang berlaku. |

## 6.3 Pengelolaan siswa dan pengguna

| ID | Prioritas | Kebutuhan |
|---|---|---|
| USER-01 | P0 | Admin dapat membuat dan mengubah data siswa minimal berisi ID siswa, nama, status aktif, kelompok/kelas opsional, dan organisasi. |
| USER-02 | P0 | Admin dapat mencari, memfilter, menonaktifkan, dan melihat riwayat siswa. |
| USER-03 | P1 | Impor daftar siswa menggunakan CSV/XLSX dapat disediakan dengan validasi duplikasi dan ringkasan kesalahan. |
| USER-04 | P1 | Admin dapat menetapkan pembina ke kelompok/lokasi sesuai model izin. |
| USER-05 | P1 | Sistem menonaktifkan akses pengguna yang tidak lagi aktif tanpa menghapus rekam jejak absensinya. |

## 6.4 Lokasi dan geofence

| ID | Prioritas | Kebutuhan |
|---|---|---|
| GEO-01 | P0 | Admin dapat menentukan nama lokasi, koordinat pusat, radius absensi, dan status aktif. |
| GEO-02 | P0 | Browser mengambil lokasi melalui izin geolocation perangkat; bila izin ditolak atau lokasi tidak tersedia, absensi tidak dapat dinyatakan sah. |
| GEO-03 | P0 | Browser mengirim latitude, longitude, akurasi GPS dalam meter, dan metadata yang diperlukan ke backend melalui koneksi HTTPS. |
| GEO-04 | P0 | Backend menghitung jarak ke lokasi terpilih dan menentukan apakah koordinat berada di dalam radius yang berlaku. |
| GEO-05 | P0 | Batas awal radius dan akurasi harus dapat dikonfigurasi; usulan default pilot radius 100 meter dan akurasi maksimum 50 meter. Nilai akhir ditentukan setelah uji lapangan. |
| GEO-06 | P0 | Backend menyimpan hasil pemeriksaan, jarak perkiraan, akurasi GPS, lokasi yang dipakai, dan keputusan validasi. |
| GEO-07 | P1 | Organisasi dapat memiliki lebih dari satu lokasi dan menetapkan lokasi yang diperbolehkan bagi siswa/kelompok/jadwal. |
| GEO-08 | P1 | Sistem menampilkan pesan yang berbeda untuk lokasi di luar radius, akurasi terlalu rendah, izin ditolak, atau lokasi gagal diperoleh. |
| GEO-09 | P1 | Sistem dapat menandai sinyal anomali untuk ditinjau, tetapi tidak menyatakan spoofing terdeteksi dengan kepastian mutlak hanya dari browser. |

## 6.5 Absensi masuk dan pulang

| ID | Prioritas | Kebutuhan |
|---|---|---|
| ATT-01 | P0 | Siswa dapat mengirim satu absen masuk untuk sesi/hari kerja yang berlaku. |
| ATT-02 | P0 | Siswa dapat mengirim satu absen pulang setelah absen masuk sah tersedia. |
| ATT-03 | P0 | Backend menetapkan waktu kejadian resmi; waktu dari perangkat dicatat hanya jika memang diperlukan sebagai data pendukung dan tidak menggantikan waktu server. |
| ATT-04 | P0 | Server mencegah pengiriman ganda akibat klik berulang, retry jaringan, atau request bersamaan. |
| ATT-05 | P0 | Setiap catatan menyimpan siswa, tenant, jenis absensi, timestamp server, lokasi, akurasi, jarak, status validasi, dan referensi foto. |
| ATT-06 | P0 | Sistem menampilkan status harian: belum masuk, sudah masuk, sudah pulang, perlu ditinjau, atau dikoreksi. |
| ATT-07 | P0 | Siswa dapat melihat riwayat absensinya sendiri tanpa akses ke bukti siswa lain. |
| ATT-08 | P0 | Pembina dapat memfilter catatan berdasarkan tanggal, siswa, kelompok, lokasi, dan status. |
| ATT-09 | P0 | Pembina dapat melakukan koreksi dengan alasan, dan semua koreksi diaudit. |
| ATT-10 | P1 | Sistem mendukung aturan jadwal, periode masuk/pulang, keterlambatan, dan toleransi sesuai konfigurasi tenant. |
| ATT-11 | P1 | Pengajuan izin/sakit dan proses persetujuan tersedia sebagai modul terpisah, bukan mengganti bukti absen tanpa jejak. |
| ATT-12 | P1 | Laporan menandai absensi yang gagal atau perlu peninjauan secara jelas, tanpa mencampurkannya sebagai absensi sah. |
| ATT-13 | P2 | Perhitungan durasi kerja, lembur, dan uang saku dengan aturan yang dapat dikonfigurasi. |

## 6.6 Pengambilan, kompresi, dan penyimpanan foto

| ID | Prioritas | Kebutuhan |
|---|---|---|
| IMG-01 | P0 | Antarmuka memprioritaskan pengambilan foto langsung dari kamera depan pada browser perangkat yang mendukungnya. |
| IMG-02 | P0 | Foto dikompres dan diubah dimensinya pada browser sebelum upload jika browser mendukung pengolahan tersebut. |
| IMG-03 | P0 | Konfigurasi awal yang diusulkan: sisi terpanjang maksimal 1.280 piksel, format JPEG, kualitas sekitar 75-80, dengan target ukuran rata-rata 100-300 KB. Foto yang tidak mencapai target setelah kompresi tetap dibatasi oleh batas upload yang dapat dikonfigurasi. |
| IMG-04 | P0 | Backend memvalidasi ukuran, tipe file berdasarkan konten, dan kemampuan decode; tidak mempercayai ekstensi atau MIME type dari klien saja. |
| IMG-05 | P0 | Backend melakukan normalisasi ulang bila diperlukan, menghapus metadata EXIF yang tidak diperlukan, dan menolak file korup/tidak didukung. |
| IMG-06 | P0 | Sistem menyimpan versi terproses saja secara default; penyimpanan foto asli bukan perilaku default. |
| IMG-07 | P0 | Foto tidak ditempatkan di direktori publik yang dapat diakses tanpa otorisasi. |
| IMG-08 | P1 | Penyimpanan file menggunakan abstraksi storage agar dapat dipindah dari filesystem lokal ke object storage tanpa mengubah logika absensi. |
| IMG-09 | P1 | Dashboard menggunakan thumbnail, pagination, dan pemuatan bertahap agar tidak mengunduh semua foto sekaligus. |
| IMG-10 | P1 | Kebijakan retensi dan penghapusan foto dapat dikonfigurasi dan didokumentasikan. |
| IMG-11 | P2 | Pemrosesan thumbnail/asinkron dan lifecycle storage ditambahkan bila volume data memerlukannya. |

## 6.7 Dashboard, laporan, dan audit

| ID | Prioritas | Kebutuhan |
|---|---|---|
| REP-01 | P0 | Dashboard menampilkan ringkasan jumlah siswa aktif, sudah masuk, sudah pulang, belum hadir, dan catatan yang perlu ditinjau. |
| REP-02 | P0 | Rekap harian dapat difilter berdasarkan rentang tanggal, siswa, kelompok, lokasi, dan status. |
| REP-03 | P0 | Laporan dasar dapat diekspor minimal ke CSV; XLSX dapat ditambahkan pada tahap pilot bila kebutuhan operasional mengharuskan. |
| REP-04 | P1 | Ekspor XLSX/PDF, ringkasan bulanan, keterlambatan, dan analisis tren tersedia. |
| AUD-01 | P0 | Koreksi absensi, perubahan aturan, perubahan akun, dan tindakan admin yang sensitif dicatat dengan pelaku, waktu, objek, dan alasan bila relevan. |
| AUD-02 | P1 | Audit log hanya dapat dilihat oleh peran yang berwenang dan tidak dapat diubah melalui antarmuka pengguna biasa. |

## 6.8 Paket, langganan, invoice, dan pembayaran

| ID | Prioritas | Kebutuhan |
|---|---|---|
| BILL-01 | P1 | Superadmin dapat membuat paket dengan harga, periode, batas penggunaan, dan fitur yang dapat dikonfigurasi. |
| BILL-02 | P1 | Sistem mencatat status langganan: trial (jika digunakan), pending payment, active, past due, suspended, cancelled, dan expired, dengan aturan transisi yang jelas. |
| BILL-03 | P1 | Sistem membuat invoice untuk periode langganan dengan nomor unik, mata uang, jumlah, jatuh tempo, status, dan referensi tenant. |
| BILL-04 | P1 | Pengguna billing dapat melihat invoice dan riwayat pembayaran organisasi sendiri. |
| BILL-05 | P1 | Integrasi pembayaran dibuat melalui lapisan adapter agar payment gateway dapat diganti dengan perubahan terbatas. |
| BILL-06 | P1 | Metode awal mencakup QRIS dan metode lain yang disediakan penyedia terpilih, seperti virtual account/transfer atau dompet elektronik bila tersedia. |
| BILL-07 | P1 | Status pembayaran dikonfirmasi melalui callback/webhook tepercaya dari provider dan/atau verifikasi server-ke-server, bukan parameter sukses dari browser saja. |
| BILL-08 | P1 | Webhook diverifikasi, diproses secara idempotent, dicatat, dan aman menghadapi notifikasi duplikat atau terlambat. |
| BILL-09 | P1 | Aktivasi/perpanjangan langganan hanya terjadi setelah pembayaran valid dipastikan. |
| BILL-10 | P1 | Invoice dan transaksi memiliki jejak audit; nominal dan status transaksi yang sudah terkonfirmasi tidak dapat diedit sembarangan. |
| BILL-11 | P1 | Sistem memberi notifikasi sebelum dan sesudah jatuh tempo, serta menerapkan kebijakan masa tenggang yang ditentukan platform. |
| BILL-12 | P1 | Jika langganan kedaluwarsa, sistem membatasi fitur sesuai kebijakan tanpa langsung menghapus data pelanggan. |
| BILL-13 | P1 | Superadmin dapat melakukan rekonsiliasi untuk transaksi tertunda/gagal dan mencatat tindakan manual secara audit. |
| BILL-14 | P2 | Kupon, prorata, paket tahunan, upgrade/downgrade, recurring payment, dan pengembalian dana otomatis dipertimbangkan setelah model dasar stabil. |

## 6.9 Notifikasi

| ID | Prioritas | Kebutuhan |
|---|---|---|
| NOT-01 | P0 | Sistem menampilkan konfirmasi langsung setelah absensi berhasil atau gagal. |
| NOT-02 | P1 | Sistem menyediakan notifikasi in-app untuk kejadian penting seperti koreksi, invoice baru, pembayaran berhasil, dan langganan mendekati jatuh tempo. |
| NOT-03 | P1 | Kanal email/WhatsApp dapat diintegrasikan melalui penyedia resmi sesuai kebutuhan dan persetujuan; tidak menjadi ketergantungan untuk keberhasilan absensi inti. |

# 7. Aturan Bisnis Utama

1. Waktu resmi absensi ditentukan server dan disimpan konsisten. Timestamp disimpan dalam format yang mendukung zona waktu, lalu ditampilkan menggunakan zona waktu tenant.
2. Dalam konfigurasi awal, satu siswa hanya memiliki satu absen masuk dan satu absen pulang per hari kerja/sesi. Dukungan shift lintas tengah malam harus menjadi aturan terpisah sebelum diaktifkan.
3. Absen pulang tidak sah bila belum ada absen masuk yang sah, kecuali diselesaikan melalui koreksi resmi yang diaudit.
4. Request berulang dengan kunci idempotensi atau kombinasi data yang sama tidak boleh menghasilkan catatan sah ganda.
5. Absensi sah harus memenuhi validasi akun, tenant, sesi, lokasi, akurasi GPS, dan bukti foto sesuai konfigurasi. Pengecualian dilakukan melalui alur koreksi, bukan dengan melewati validasi diam-diam.
6. Radius dan ambang akurasi ditetapkan oleh organisasi/administrator yang berwenang. Usulan default pilot: radius 100 meter dan akurasi GPS maksimum 50 meter; perlu diuji pada area bengkel dan berbagai perangkat.
7. Jika GPS tidak tersedia, izin kamera/lokasi ditolak, atau foto gagal diproses, sistem menjelaskan kegagalan dan tidak memberi konfirmasi keberhasilan.
8. Koreksi tidak menghapus riwayat nilai sebelumnya dan wajib mempunyai alasan serta pelaku.
9. Foto disimpan pada versi terkompresi dan normalisasi. Akses foto memerlukan otorisasi yang sesuai dengan tenant dan peran.
10. Tenant yang memiliki tagihan tertunggak mengikuti masa tenggang dan pembatasan yang diumumkan. Data tidak langsung dihapus saat langganan kedaluwarsa.
11. Sistem tidak mempercayai status pembayaran dari browser; status final berasal dari verifikasi server yang dapat diaudit.
12. Sistem tidak mengklaim foto atau GPS sebagai bukti anti-kecurangan absolut.

# 8. Persyaratan UX dan Antarmuka

- Mobile-first: alur siswa dirancang terutama untuk layar ponsel dan koneksi yang tidak selalu stabil.
- Tombol **Absen Masuk** dan **Absen Pulang** harus menonjol dan statusnya jelas.
- Tampilkan urutan persiapan: izin kamera, ambil foto, ambil lokasi, validasi, kirim, dan hasil.
- Tampilkan indikator proses upload dan cegah klik berulang saat request berjalan.
- Pesan error harus menjelaskan tindakan berikutnya; hindari pesan teknis mentah.
- Aksesibilitas dasar: kontras yang memadai, label kontrol, fokus keyboard, dan pesan status yang tidak hanya mengandalkan warna.
- Dashboard pembina menggunakan tabel yang bisa dicari/difilter, pagination, dan thumbnail.
- Formulir pengaturan menampilkan zona waktu, radius meter, akurasi meter, jam efektif, dan lokasi secara eksplisit.
- Jangan tampilkan koordinat presisi ke pengguna yang tidak memerlukannya.
- Semua tanggal, angka, dan mata uang mengikuti format Indonesia; zona waktu ditampilkan konsisten.

# 9. Model Data Konseptual

Model berikut merupakan usulan awal, bukan skema database final. Seluruh entitas milik organisasi harus memiliki kaitan tenant yang eksplisit atau dapat diotorisasi dengan aman.

| Entitas | Data/relasi penting |
|---|---|
| Tenant/Organization | ID, nama, status, zona waktu, konfigurasi, paket/langganan aktif |
| User | ID, kredensial, status, role, tenant atau relasi membership |
| Membership/Role | User, tenant, role, cakupan akses, status |
| StudentProfile | User/akun, nomor siswa, nama, kelompok/kelas, status aktif |
| AttendanceLocation | Tenant, nama, latitude/longitude pusat, radius, akurasi maksimum, status |
| Schedule/AttendancePolicy | Tenant, hari aktif, jam masuk/pulang, toleransi, lokasi yang berlaku, aturan sesi |
| AttendanceSession/Workday | Siswa, tanggal kerja/sesi, status ringkasan, relasi check-in/check-out |
| AttendanceRecord | Siswa, tenant, jenis, waktu server, koordinat, akurasi, jarak, status validasi, lokasi, referensi foto |
| MediaAsset | Storage key, tipe, dimensi, ukuran byte, checksum opsional, waktu unggah, kebijakan retensi |
| AttendanceCorrection | Catatan, nilai lama/baru, alasan, pelaku, waktu, relasi audit |
| AuditLog | Tenant opsional, pelaku, tindakan, objek, waktu, metadata yang aman |
| Plan | Nama, harga, periode, batas penggunaan, fitur, status |
| Subscription | Tenant, plan, mulai/akhir periode, status, masa tenggang |
| Invoice | Nomor, tenant, jumlah, mata uang, tanggal terbit/jatuh tempo, status |
| PaymentTransaction | Invoice, provider, ID eksternal, metode, jumlah, status, waktu konfirmasi |
| PaymentWebhookEvent | ID event/provider, waktu terima, hasil pemrosesan, status idempotensi |
| Notification | Penerima, kanal, jenis, status, waktu pengiriman |

## 9.1 Integritas data

- Gunakan unique constraint atau mekanisme transaksi yang mencegah duplikasi absen berdasarkan kebijakan sesi.
- Gunakan foreign key dan indeks pada tenant, tanggal, siswa, status, dan nomor invoice yang umum dipakai untuk pencarian.
- Simpan nominal uang sebagai integer dalam satuan mata uang terkecil yang relevan (untuk IDR, rupiah bulat) atau tipe decimal yang tepat; jangan gunakan floating point untuk perhitungan tagihan.
- Jangan menyimpan foto biner besar di tabel relasional bila object storage lebih sesuai; simpan metadata dan storage key.
- Data audit penting tidak boleh ikut terhapus ketika sebuah akun dinonaktifkan.

# 10. Arsitektur dan Rekomendasi Teknologi

## 10.1 Pendekatan

Gunakan backend terpusat dengan API yang menjadi sumber aturan bisnis. Frontend web boleh memakai server-rendered templates untuk mempercepat MVP, dengan JavaScript untuk kamera, kompresi, geolocation, dan interaksi. API dipersiapkan agar dapat dipakai oleh web maupun aplikasi mobile nanti.

## 10.2 Stack rekomendasi awal

| Lapisan | Rekomendasi | Catatan |
|---|---|---|
| Backend | Python + Django | Cocok untuk domain data, admin internal, autentikasi, dan modul bertahap |
| API | Django REST Framework | Dipakai untuk endpoint yang perlu digunakan web/mobile dan integrasi |
| Frontend awal | Django Templates + JavaScript modular + CSS responsif | Mengurangi kompleksitas build pada tahap awal; framework SPA dapat dievaluasi kemudian |
| Database | PostgreSQL | Disarankan untuk data relasional dan pertumbuhan multi-tenant |
| Cache/queue | Belum wajib untuk pilot; Redis/worker jika diperlukan | Tambahkan untuk pekerjaan asinkron setelah beban membutuhkannya |
| Media | Abstraksi storage; object storage S3-compatible untuk produksi jika sesuai anggaran | Hindari ketergantungan langsung pada path lokal di seluruh aplikasi |
| Server | Linux VPS, reverse proxy, Gunicorn, HTTPS | Konfigurasi produksi harus terpisah dari development |
| Pembayaran | Adapter untuk provider berizin/tepat guna yang mendukung QRIS | Provider final dipilih setelah membandingkan biaya, settlement, webhook, dan persyaratan bisnis |
| Mobile berikutnya | Aplikasi Android/iOS menggunakan API | Pilihan framework native/cross-platform ditentukan setelah MVP tervalidasi |

## 10.3 Prinsip arsitektur wajib

- Pisahkan domain/aturan bisnis dari tampilan.
- Semua validasi penting berjalan di backend.
- Semua query dan mutasi data tenant melewati otorisasi tenant.
- Gunakan migrasi database yang tercatat.
- Konfigurasi sensitif disimpan di environment/secret manager, tidak di kode sumber.
- Pisahkan environment development, staging, dan production sejauh memungkinkan.
- Sediakan abstraksi penyimpanan file dan pembayaran agar provider bisa diganti.
- Endpoint penting memiliki validasi input, pembatasan request yang relevan, logging, dan penanganan error konsisten.
- Pertahankan API versioning saat API publik untuk aplikasi mobile mulai digunakan.

# 11. Keamanan, Privasi, dan Tata Kelola Data

Foto siswa, lokasi, identitas akun, dan catatan kehadiran harus diperlakukan sebagai data sensitif secara operasional. Sebelum peluncuran umum, pemilik platform perlu meninjau kewajiban perlindungan data pribadi yang berlaku, terutama karena pengguna dapat berupa pelajar di bawah umur.

Persyaratan minimum:

1. Sediakan kebijakan privasi dan syarat layanan yang menjelaskan tujuan pemrosesan, jenis data, pihak yang mengakses, retensi, kontak pengaduan, dan cara meminta koreksi/penghapusan sesuai kebijakan serta kewajiban hukum.
2. Kumpulkan data secukupnya. Jangan mengakses lokasi terus-menerus; ambil lokasi saat proses absensi sesuai kebutuhan.
3. Gunakan HTTPS untuk seluruh lalu lintas produksi.
4. Lindungi secret key, password database, token payment gateway, dan secret webhook.
5. Batasi ukuran upload, validasi konten file, dan cegah akses file tanpa otorisasi.
6. Terapkan proteksi terhadap serangan web umum sesuai framework, termasuk CSRF pada form berbasis cookie, XSS, SQL injection, dan akses objek tanpa izin.
7. Gunakan prinsip least privilege untuk akun admin, operator, service account, dan dukungan.
8. Catat tindakan administratif, koreksi, akses sensitif bila relevan, serta perubahan billing.
9. Jangan menyimpan data kartu pembayaran. Gunakan halaman/metode pembayaran yang disediakan provider dan simpan token/referensi yang memang diperlukan saja.
10. Buat jadwal backup, uji pemulihan, kebijakan retensi, dan prosedur respons insiden.
11. Hapus metadata EXIF yang tidak dibutuhkan dari foto yang disimpan.
12. Jangan memasukkan foto, koordinat presisi, kredensial, token, atau data pribadi ke log biasa tanpa alasan dan perlindungan yang sesuai.
13. Sediakan mekanisme ekspor dan penghapusan sesuai ketentuan yang telah ditetapkan, termasuk penanganan backup dan masa retensinya.

## 11.1 Batasan validasi lokasi dan foto

GPS browser menunjukkan posisi yang dilaporkan oleh perangkat, bukan jaminan bahwa pengguna secara fisik berada pada titik itu. Sistem dapat memakai pemeriksaan akurasi, radius, pola anomali, perangkat, dan peninjauan pembina untuk meningkatkan keandalan, tetapi tidak boleh menjanjikan anti-spoofing sempurna. Penggunaan selfie juga hanya membuktikan bahwa sebuah gambar dikirim; itu tidak otomatis merupakan verifikasi liveness atau identitas wajah.

# 12. Persyaratan Nonfungsional

Target berikut merupakan **target awal untuk diuji**, bukan jaminan sebelum pengukuran pada lingkungan produksi.

| Area | Target awal |
|---|---|
| Kinerja UI | Halaman utama/dashboard sederhana ditargetkan tampil dalam sekitar 2,5 detik pada kondisi jaringan dan perangkat uji yang ditetapkan |
| Respons API | Endpoint baca/tulis normal ditargetkan p95 di bawah 500 ms, tidak termasuk waktu pengiriman foto dan latensi pihak ketiga |
| Ukuran foto | Target tipikal 100-300 KB setelah kompresi; batas maksimal upload dikonfigurasi |
| Keandalan upload | Kegagalan jaringan menampilkan status yang benar dan tidak menghasilkan duplikasi saat retry |
| Responsif | Mendukung browser mobile modern dan desktop; daftar browser minimal ditentukan saat pilot |
| Ketersediaan | Target awal 99,5% per bulan setelah operasi komersial stabil, dengan pemantauan dan penanganan insiden |
| Kapasitas pilot | Rancang dan ukur untuk sedikitnya 100 request absensi hampir bersamaan sebagai target uji awal; sesuaikan berdasarkan hasil beban nyata |
| Skalabilitas | Bisa meningkatkan kapasitas aplikasi, database, dan storage tanpa desain ulang total domain bisnis |
| Aksesibilitas | Kontras, label formulir, navigasi keyboard dasar, dan pesan error yang mudah dipahami |
| Observabilitas | Log aplikasi, error, status background job, penggunaan storage, serta metrik respons tersedia dengan perlindungan data |
| Pemulihan | Backup database terjadwal dan prosedur pemulihan terdokumentasi; RPO/RTO final ditentukan sebelum layanan komersial |

# 13. Kriteria Penerimaan Rilis

## 13.1 Pilot absensi

Rilis pilot dapat diterima ketika:

- Siswa yang aktif dapat login dan hanya melihat riwayat miliknya.
- Siswa dapat melakukan absen masuk dan pulang di dalam radius yang ditetapkan menggunakan browser mobile yang didukung.
- Absen ditolak secara jelas bila di luar radius, akurasi GPS melewati batas, izin lokasi/kamera ditolak, atau foto tidak valid.
- Waktu resmi berasal dari server.
- Percobaan ganda tidak menghasilkan dua catatan sah untuk sesi yang sama, termasuk dalam uji request berulang.
- Foto dikompres sebelum upload dan dinormalisasi/divalidasi oleh backend.
- Pembina dapat melihat kehadiran, melakukan koreksi dengan alasan, dan mengekspor data dasar.
- Koreksi tercatat dalam audit log.
- Backup database tersedia dan prosedur pemulihan telah didokumentasikan.

## 13.2 Rilis SaaS komersial

Rilis komersial dapat diterima ketika seluruh kriteria pilot terpenuhi dan:

- Dua organisasi uji dapat beroperasi dalam satu deployment dengan data yang terisolasi.
- Pengujian otorisasi membuktikan user tenant A tidak dapat membaca atau mengubah data tenant B.
- Batas paket ditegakkan di backend, bukan hanya UI.
- Invoice dibuat dan mempunyai status yang konsisten.
- Pembayaran uji QRIS dikonfirmasi melalui webhook/verifikasi server; notifikasi duplikat atau terlambat tidak menggandakan aktivasi.
- Pembayaran yang belum terkonfirmasi tidak mengaktifkan langganan.
- Masa tenggang, suspend, perpanjangan, dan akses data setelah kedaluwarsa mengikuti kebijakan tertulis.
- Secret produksi tidak ada di repositori dan domain produksi menggunakan HTTPS.
- Kebijakan privasi, syarat layanan, dukungan pelanggan, backup, monitoring, dan prosedur insiden tersedia.

# 14. Analitik Produk dan Indikator Keberhasilan

| Indikator | Definisi |
|---|---|
| Tingkat keberhasilan absensi | Persentase upaya absensi yang berakhir pada catatan sah dibanding seluruh upaya yang valid untuk dihitung |
| Waktu penyelesaian absensi | Waktu dari memulai alur sampai hasil server muncul, dipisahkan dari error GPS/koneksi |
| Ukuran rata-rata foto | Rata-rata dan persentil ukuran file pascaproses |
| Tingkat kegagalan upload | Persentase upload yang gagal setelah retry yang diperbolehkan |
| Akurasi rekap | Jumlah koreksi/error rekap yang dilaporkan dalam periode tertentu |
| Aktivasi tenant | Organisasi yang menyelesaikan onboarding dan membuat pengguna/lokasi pertama |
| Konversi pembayaran | Invoice berbayar dibanding invoice yang jatuh tempo, dipantau per cohort/periode |
| Retensi tenant | Proporsi tenant yang memperpanjang langganan pada periode berikutnya |
| Insiden isolasi data | Jumlah insiden akses lintas tenant; targetnya nol |
| Efisiensi storage | Pertumbuhan penyimpanan per 1.000 catatan absensi dan biaya storage per tenant |

Analitik harus memakai data agregat seperlunya dan tidak memperlihatkan foto atau koordinat presisi kepada peran yang tidak berwenang.

# 15. Risiko dan Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| GPS tidak akurat di dalam bengkel | Siswa sah gagal absen | Uji beberapa perangkat dan titik; konfigurasi radius/akurasi; prosedur koreksi tercatat |
| GPS dipalsukan | Catatan kehadiran tidak dapat dipercaya | Pemeriksaan anomali dan pembina; jangan menjanjikan pencegahan absolut; evaluasi penguatan jika diperlukan |
| Foto tetap besar atau upload lambat | Beban server dan pengalaman pengguna buruk | Kompresi browser, batas upload, normalisasi server, thumbnail, object storage |
| Kebocoran data lintas tenant | Dampak privasi dan kepercayaan serius | Otorisasi tenant di backend, pengujian isolasi, least privilege, audit log |
| Webhook pembayaran palsu/duplikat | Langganan aktif tanpa pembayaran valid atau transaksi ganda | Verifikasi signature/status, idempotensi, rekonsiliasi server-ke-server |
| Biaya storage meningkat | Biaya operasional membesar | Batas paket, retensi, kompresi, metrik pertumbuhan, lifecycle storage |
| Pengembangan terlalu luas | Proyek lambat dan sulit dirawat | Prioritaskan MVP, kriteria selesai, backlog terpisah, perubahan scope terkontrol |
| Ketergantungan pada vendor | Migrasi mahal | Adapter untuk payment gateway dan storage, dokumentasi konfigurasi, ekspor data |
| Perubahan aturan privasi/kebijakan provider | Perlu perubahan proses | Tinjau ketentuan terkini saat memilih vendor dan sebelum peluncuran |
| Akun siswa dipakai orang lain | Validitas kehadiran berkurang | Password individual, sesi aman, pengawasan pembina, evaluasi kontrol tambahan secara proporsional |

# 16. Rencana Implementasi

Urutan berikut adalah urutan dependensi, bukan estimasi durasi.

1. **Discovery dan keputusan produk:** konfirmasi aturan absensi, peran, definisi sesi/hari kerja, alur koreksi, dan kebutuhan laporan.
2. **Fondasi proyek:** struktur Django, konfigurasi environment, database, model tenant awal, autentikasi, role/permission, migrasi, dan design system dasar.
3. **Absensi pilot:** profil siswa, lokasi, geofence, kamera, kompresi, upload, validasi server, check-in/check-out, dan idempotensi.
4. **Operasional:** dashboard, filter, laporan, ekspor, koreksi, dan audit log.
5. **Hardening pilot:** pengamanan foto, backup/pemulihan, logging, pengujian manual dengan perangkat nyata dan skenario GPS bermasalah.
6. **SaaS multi-tenant:** onboarding organisasi, isolasi data, paket dan pembatasan penggunaan.
7. **Billing:** invoice, integrasi provider, webhook, idempotensi, rekonsiliasi, pengingat, masa tenggang, dan status langganan.
8. **Kesiapan komersial:** kebijakan privasi/syarat layanan, monitoring, backup teruji, prosedur dukungan, dokumentasi admin, dan peluncuran bertahap.
9. **Evolusi produk:** PWA, modul uang saku, notifikasi, aplikasi Android/iOS, serta fitur lain berdasarkan data penggunaan.

# 17. Asumsi dan Keputusan yang Masih Harus Ditentukan

Keputusan berikut boleh menggunakan nilai default saat prototipe, tetapi perlu dikonfirmasi sebelum rilis terkait.

| Keputusan | Usulan awal | Pemilik keputusan/waktu |
|---|---|---|
| Nama dan domain produk | Nama kerja; belum final | Pemilik produk sebelum branding publik |
| Target pelanggan | Sekolah, unit TeFa, bengkel pendidikan; divalidasi melalui pilot | Pemilik produk pada discovery |
| Metode login siswa | ID siswa/username + password yang dibuat admin | Sebelum implementasi autentikasi |
| Radius geofence | 100 meter sebagai default pilot | Konfirmasi setelah uji lapangan |
| Akurasi maksimum GPS | 50 meter sebagai default pilot | Konfirmasi setelah uji perangkat nyata |
| Dimensi foto | Maksimum 1.280 piksel sisi terpanjang | Validasi kualitas foto saat pilot |
| Target ukuran foto | 100-300 KB, bukan jaminan tiap foto | Validasi hasil kompresi |
| Penyimpanan produksi | Object storage S3-compatible jika biaya dan akses memungkinkan | Sebelum peluncuran komersial |
| Provider pembayaran | Pilih setelah evaluasi biaya, metode, settlement, webhook, dan persyaratan merchant | Sebelum implementasi billing |
| Harga dan batas paket | Belum ditentukan | Sebelum halaman penjualan |
| Masa tenggang | Usulan awal 7 hari, perlu disetujui | Sebelum billing aktif |
| Nasib data setelah langganan berakhir | Tidak langsung dihapus; periode ekspor/retensi harus ditentukan | Sebelum syarat layanan final |
| Jadwal dan shift | Satu sesi harian untuk pilot | Konfirmasi oleh pengguna operasional |
| Format laporan | CSV dasar; XLSX/PDF sesuai kebutuhan | Konfirmasi pembina |
| Notifikasi | In-app dahulu; kanal eksternal menyusul | Setelah core stabil |
| Aplikasi mobile | Dibangun setelah web dan API tervalidasi | Setelah evaluasi MVP |

# 18. Ketentuan Kerja untuk AI Coding Agent

Bagian ini menjadi pedoman saat PRD dipecah menjadi tugas implementasi untuk Codex atau AI coding agent lain.

1. Baca PRD dan dokumentasi proyek yang ada sebelum mengubah kode.
2. Kerjakan satu modul atau tugas dengan batas ruang lingkup yang eksplisit.
3. Jangan membuat keputusan produk yang belum ada di PRD secara diam-diam. Catat pertanyaan atau gunakan asumsi yang paling aman dan mudah diubah.
4. Jangan mengganti stack, merombak arsitektur, atau mengubah model data lintas modul tanpa alasan yang jelas dan keputusan pemilik proyek.
5. Pertahankan isolasi tenant, otorisasi backend, validasi sisi server, dan audit trail sebagai aturan inti, bukan tambahan kosmetik.
6. Jangan menyatakan lokasi, foto, atau pembayaran valid hanya berdasarkan klaim dari frontend.
7. Jangan mengimplementasikan integrasi pembayaran seolah-olah transaksi nyata berhasil tanpa kredensial, konfigurasi, dan verifikasi provider yang sesungguhnya.
8. Untuk setiap tugas, laporkan ringkas file yang diubah, fungsi yang ditambahkan, konfigurasi/migrasi yang diperlukan, asumsi, dan langkah manual yang harus dilakukan pemilik proyek.
9. Jangan mengklaim QA, browser testing, deployment, atau verifikasi yang belum benar-benar dilakukan.
10. Jangan membuat commit secara otomatis kecuali diminta secara eksplisit.
11. Perubahan harus dapat dipisahkan dan mudah ditinjau; hindari perubahan yang tidak terkait tugas.
12. Secret, data siswa nyata, foto, koordinat, dan kredensial tidak boleh dimasukkan ke prompt/repository/log tanpa perlindungan yang sesuai.

# 19. Definisi Selesai (Definition of Done)

Satu fitur dinyatakan selesai jika:

- Perilakunya sesuai kebutuhan dan kriteria penerimaan yang ditetapkan.
- Validasi bisnis berjalan di backend untuk operasi yang memengaruhi data atau keamanan.
- Otorisasi role dan tenant diterapkan pada seluruh jalur terkait.
- Error, kondisi kosong, dan status pemrosesan ditangani dengan pesan yang jelas.
- Perubahan skema memiliki migrasi dan dapat diterapkan dengan prosedur terdokumentasi.
- Tidak ada secret atau data sensitif yang bocor ke kode/log biasa.
- Dokumentasi konfigurasi, batasan, serta pekerjaan manual yang tersisa diperbarui.
- Pemilik proyek melakukan pemeriksaan manual pada alur utama sebelum rilis.

# 20. Glosarium

| Istilah | Makna |
|---|---|
| TeFa / Teaching Factory | Model pembelajaran yang mengintegrasikan proses produksi/jasa industri dalam lingkungan pendidikan |
| SaaS | Software as a Service; perangkat lunak yang disediakan sebagai layanan, umumnya berlangganan |
| Tenant | Satu organisasi/pelanggan dengan data dan konfigurasi yang terisolasi |
| MVP | Minimum Viable Product; versi awal dengan fitur minimum untuk menguji kebutuhan nyata |
| Geofence | Batas wilayah virtual yang ditentukan berdasarkan titik pusat dan radius |
| GPS accuracy | Perkiraan ketidakpastian posisi yang dilaporkan perangkat; bukan jaminan posisi tepat |
| API | Antarmuka backend agar web atau aplikasi lain dapat berkomunikasi dengan sistem |
| Webhook | Notifikasi dari layanan eksternal ke backend ketika suatu peristiwa terjadi |
| Idempotensi | Prinsip agar pemrosesan request/event yang sama berulang tidak membuat efek ganda |
| Object storage | Penyimpanan file yang terpisah dari database relasional dan aplikasi web |
| Audit log | Catatan siapa melakukan tindakan apa, kapan, dan terhadap objek yang mana |
| PWA | Progressive Web App; website dengan kemampuan aplikasi tambahan sesuai dukungan browser/perangkat |

---

**Akhir dokumen — PRD Platform Absensi dan Manajemen TeFa v1.0**

Dokumen ini adalah baseline produk. Perubahan kebutuhan harus dicatat sebagai revisi PRD atau keputusan produk agar semua coding agent dan pengembang menggunakan spesifikasi yang konsisten.
