// api.js — satu pintu semua fetch. Mode dummy HANYA via ?dummy=1 (backend /api/v1/ sudah aktif).
const DUMMY = new URLSearchParams(location.search).has('dummy') && true; // matikan sepenuhnya: hapus baris failScenario di bawah juga
const BASE = '/api/v1';
const SIM_DELAY = 600;

// Skenario gagal untuk demo dummy: ?dummy=1&fail=OUT_OF_GEOFENCE|GPS_ACCURACY_TOO_LOW|...
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
    NOT_CHECKED_IN: 'Kamu belum absen masuk hari ini. Hubungi pembina jika ada kendala.',
    ATTENDANCE_WINDOW_CLOSED: 'Di luar jam absensi. Lihat jadwal / hubungi pembina.',
    OUTSIDE_CHECKIN_WINDOW: 'Di luar jam absen masuk. Lihat jadwal / hubungi pembina.',
    OUTSIDE_CHECKOUT_WINDOW: 'Di luar jam absen pulang. Lihat jadwal / hubungi pembina.',
    POLICY_NOT_CONFIGURED: 'Jadwal absensi belum diatur. Hubungi admin/pembina.',
    RATE_LIMITED: 'Terlalu sering. Tunggu sebentar, lalu coba lagi.',
    VALIDATION_ERROR: 'Data yang dikirim tidak valid. Coba lagi.',
    IDEMPOTENCY_CONFLICT: 'Ada percobaan absen lain sedang diproses. Tunggu sebentar.',
    TENANT_ACCESS_DENIED: 'Akses ditolak.',
    AUTH_REQUIRED: 'Sesi berakhir. Silakan login kembali.',
  };
  return new ApiError(code, M[code] || (detail || 'Terjadi kesalahan. Coba lagi.'), detail || '');
}

class ApiError extends Error {
  constructor(code, message, detail) { super(message); this.code = code; this.detail = detail; }
}

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

function todayStr() {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Jakarta', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
  return `${parts.find(p => p.type === 'year').value}-${parts.find(p => p.type === 'month').value}-${parts.find(p => p.type === 'day').value}`;
}

// ---- Data dummy (hanya dipakai kalau ?dummy=1) ----
const dummyState = {
  today: null,
  records: [
    { id: 'r1', date: todayStr(), check_in: '07:58', check_out: null, status: 'HADIR', distance_m: 18.4 },
  ],
};

function dummyToday() {
  if (!dummyState.today) dummyState.today = { date: todayStr(), check_in_time: null, check_out_time: null, state: 'BELUM_MASUK' };
  return dummyState.today;
}

function isoNow(offsetMin = 0) {
  return new Date(Date.now() + offsetMin * 60000).toISOString();
}

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
    return { status: 'accepted', attendance_event_id: 'dummy-' + crypto.randomUUID(), event_type: 'CHECK_IN', server_time: isoNow(), location_validation: { valid: true, distance_m: 18.4, accuracy_m: 12.0 } };
  },
  async 'POST /attendance/check-out/'() {
    await delay(900);
    const fail = failScenario();
    if (fail) throw mapError(fail, 'Simulasi kegagalan dummy mode.');
    const t = dummyToday();
    t.check_out_time = isoNow().slice(11, 16);
    t.state = 'SUDAH_PULANG';
    return { status: 'accepted', attendance_event_id: 'dummy-' + crypto.randomUUID(), event_type: 'CHECK_OUT', server_time: isoNow(), location_validation: { valid: true, distance_m: 15.2, accuracy_m: 10.0 } };
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
    if (!opts.body) throw mapError('VALIDATION_ERROR', 'Alasan koreksi wajib diisi.');
    return { status: 'created' };
  },
};

async function dummyRequest(method, path, body) {
  const key = `${method} ${path}`;
  const h = dummyHandlers[key];
  if (!h) throw mapError('NOT_IMPLEMENTED_DUMMY', `Endpoint ${key} belum tersedia di dummy mode.`);
  return h(path, { body });
}

async function realRequest(method, path, body, isForm = false) {
  const opts = { method, headers: {}, credentials: 'same-origin' };
  if (body) {
    if (isForm) { opts.body = body; }
    else { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  }
  // CSRF cookie → header (Django)
  const csrf = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  if (csrf && method !== 'GET') opts.headers['X-CSRFToken'] = decodeURIComponent(csrf[1]);
  const res = await fetch(BASE + path, opts);
  if (res.status === 401 || res.status === 403) {
    let data = null;
    try { data = await res.json(); } catch { /* non-JSON */ }
    if (data?.code === 'TENANT_ACCESS_DENIED' && res.status === 403) throw mapError('TENANT_ACCESS_DENIED', data.message);
    if (res.status === 401) { location.href = '/accounts/login/'; throw mapError('AUTH_REQUIRED', 'Sesi berakhir.'); }
  }
  let data = null;
  try { data = await res.json(); } catch { /* non-JSON */ }
  if (!res.ok) throw mapError(data?.code || 'SERVER_ERROR', data?.message || data?.detail);
  return data;
}

export async function api(method, path, body, isForm = false) {
  if (DUMMY) return dummyRequest(method, path, body);
  return realRequest(method, path, body, isForm);
}

export { ApiError };
