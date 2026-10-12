// api.js — satu pintu semua fetch. Mode dummy (?dummy=1 atau DUMMY=true) untuk demo tanpa backend.
// Implementasi nyata ke /api/v1/ tetap ada; saat backend siap cukup matikan dummy.

const DUMMY = new URLSearchParams(location.search).has('dummy') || true; // default DUMMY aktif sampai backend siap; ubah ke `false` saat /api/v1/ nyata
const BASE = '/api/v1';
const SIM_DELAY = 600; // ms delay simulasi

// Skenario gagal yang bisa dipilih untuk demo: ?dummy=1&fail=OUT_OF_GEOFENCE|GPS_ACCURACY_TOO_LOW|ALREADY_CHECKED_IN|...
function failScenario() {
  return new URLSearchParams(location.search).get('fail') || '';
}

function mapError(code, detail) {
  const M = {
    LOCATION_PERMISSION_REQUIRED: 'Aktifkan izin lokasi, lalu coba lagi.',
    LOCATION_UNAVAILABLE: 'Lokasi tidak terdeteksi. Pastikan GPS aktif / cari area terbuka.',
    GPS_ACCURACY_TOO_LOW: 'Sinyal GPS lemah. Tunggu sebentar, lalu coba lagi.',
    OUT_OF_GEOFENCE: 'Kamu berada di luar area absensi.',
    OUTSIDE_GEOFENCE: 'Kamu berada di luar area absensi.',
    PHOTO_REQUIRED: 'Foto tidak valid. Ambil ulang selfie.',
    INVALID_PHOTO: 'Foto tidak valid. Ambil ulang selfie.',
    ALREADY_CHECKED_IN: 'Kamu sudah absen masuk hari ini.',
    ALREADY_CHECKED_OUT: 'Kamu sudah absen pulang hari ini.',
    CHECK_IN_REQUIRED: 'Kamu belum absen masuk hari ini. Hubungi pembina jika ada kendala.',
    ATTENDANCE_WINDOW_CLOSED: 'Di luar jam absensi. Lihat jadwal / hubungi pembina.',
    RATE_LIMITED: 'Terlalu sering. Tunggu sebentar, lalu coba lagi.',
    AUTH_REQUIRED: 'Sesi berakhir. Silakan login kembali.',
  };
  return { code, message: M[code] || (detail || 'Terjadi kesalahan. Coba lagi.'), detail: detail || '' };
}

class ApiError extends Error {
  constructor(code, message, detail) { super(message); this.code = code; this.detail = detail; }
}

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

function todayStr() { return new Date().toISOString().slice(0, 10); }

// ---- Data dummy (tanpa data siswa nyata) ----
const dummyState = {
  today: null,
  records: [
    { id: 'r1', date: todayStr(), check_in: '07:58', check_out: null, status: 'HADIR', distance_m: 18.4 },
    { id: 'r2', date: '2026-10-09', check_in: '08:04', check_out: '16:31', status: 'HADIR', distance_m: 22.1 },
    { id: 'r3', date: '2026-10-08', check_in: '07:52', check_out: '16:02', status: 'HADIR', distance_m: 12.7 },
  ],
};

function dummyToday() {
  if (!dummyState.today) dummyState.today = { date: todayStr(), check_in_time: null, check_out_time: null, state: 'BELUM_MASUK' };
  return dummyState.today;
}

function isoNow(offsetMin = 0) {
  return new Date(Date.now() + offsetMin * 60000).toISOString();
}

// ---- Dummy handlers ----
const dummyHandlers = {
  async 'POST /auth/login/'() {
    await delay(SIM_DELAY);
    return { token: 'dummy-token', user: { name: 'Siswa Demo', email: 'demo@tefa.sch.id' } };
  },
  async 'GET /attendance/today/'() { await delay(SIM_DELAY); return dummyToday(); },
  async 'POST /attendance/check-in/'() {
    await delay(900);
    const fail = failScenario();
    if (fail) throw mapError(fail, 'Simulasi kegagalan dummy mode.');
    const t = dummyToday();
    t.check_in_time = isoNow().slice(11, 16);
    t.state = 'SUDAH_MASUK';
    return {
      status: 'accepted', attendance_event_id: 'dummy-' + crypto.randomUUID(), event_type: 'CHECK_IN',
      server_time: isoNow(), location_validation: { valid: true, distance_m: 18.4, accuracy_m: 12.0 },
    };
  },
  async 'POST /attendance/check-out/'() {
    await delay(900);
    const fail = failScenario();
    if (fail) throw mapError(fail, 'Simulasi kegagalan dummy mode.');
    const t = dummyToday();
    t.check_out_time = isoNow().slice(11, 16);
    t.state = 'SUDAH_PULANG';
    return {
      status: 'accepted', attendance_event_id: 'dummy-' + crypto.randomUUID(), event_type: 'CHECK_OUT',
      server_time: isoNow(), location_validation: { valid: true, distance_m: 15.2, accuracy_m: 10.0 },
    };
  },
  async 'GET /attendance/my-records/'() { await delay(SIM_DELAY); return { results: dummyState.records, next: null }; },
  async 'GET /attendance/records/'() {
    await delay(SIM_DELAY);
    const siswa = [
      { id: 'p1', name: 'Andi Pratama', check_in: '07:55', check_out: '16:30', status: 'HADIR', distance_m: 14.2 },
      { id: 'p2', name: 'Bunga Sari', check_in: '08:11', check_out: null, status: 'BELUM_PULANG', distance_m: 25.0 },
      { id: 'p3', name: 'Citra Dewi', check_in: null, check_out: null, status: 'BELUM_HADIR', distance_m: null },
      { id: 'p4', name: 'Dimas Arya', check_in: '07:49', check_out: '15:58', status: 'PERLU_DITINJAU', distance_m: 210.0 },
    ];
    return { summary: { hadir: 2, belum_hadir: 1, pulang: 2, perlu_ditinjau: 1 }, results: siswa, next: null };
  },
  async 'POST /attendance/records/{id}/corrections/'(url, opts) {
    await delay(500);
    if (!opts.body) throw mapError('CORRECTION_REASON_REQUIRED', 'Alasan koreksi wajib diisi.');
    return { status: 'created' };
  },
};

// ---- Real handler (backend belum ada — akan digunakan saat siap) ----
async function realRequest(method, path, body, isForm = false) {
  const opts = { method, headers: {} };
  if (body) {
    if (isForm) { opts.body = body; }
    else { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  }
  const res = await fetch(BASE + path, opts);
  if (res.status === 401) throw mapError('AUTH_REQUIRED', 'Sesi berakhir.');
  let data = null;
  try { data = await res.json(); } catch { /* non-JSON */ }
  if (!res.ok) throw mapError(data?.code || 'SERVER_ERROR', data?.message || data?.detail);
  return data;
}

async function dummyRequest(method, path, body) {
  const key = `${method} ${path}`;
  const h = dummyHandlers[key];
  if (!h) throw mapError('NOT_IMPLEMENTED_DUMMY', `Endpoint ${key} belum tersedia di dummy mode.`);
  return h(path, { body });
}

export async function api(method, path, body, isForm = false) {
  if (DUMMY || failScenario()) return dummyRequest(method, path, body);
  return realRequest(method, path, body, isForm);
}

export { ApiError };
