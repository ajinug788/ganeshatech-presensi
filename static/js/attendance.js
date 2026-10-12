// attendance.js — orkestrasi wizard absen: kamera → foto → lokasi → kirim
// Idempotency: client_request_id (crypto.randomUUID) disimpan di sessionStorage sampai respons final.
import { api, ApiError } from './api.js';
import { startCamera, stopCamera, captureFrame } from './camera.js';
import { getLocation } from './geo.js';
import { compressBlob } from './compress.js';

const $ = (s) => document.querySelector(s);

const state = {
  step: 1,
  photoBlob: null,
  geo: null,
  idempotencyKey: null,
  busy: false,
};

function setStep(n) {
  state.step = n;
  document.querySelectorAll('.stepper__step').forEach(el => {
    const idx = Number(el.dataset.step);
    el.classList.toggle('is-active', idx === n);
    el.classList.toggle('is-done', idx < n);
    el.classList.toggle('is-failed', el.dataset.failed === '1' && idx === n);
  });
  document.querySelectorAll('[data-pane]').forEach(p => {
    p.hidden = Number(p.dataset.pane) !== n;
  });
}

function setStatus(elId, text, kind = '') {
  const el = $(elId);
  if (!el) return;
  el.textContent = text;
  el.className = `status ${kind}`.trim();
  el.hidden = false;
}

function showError(elId, msg, action = '') {
  setStatus(elId, action ? `${msg} ${action}` : msg, 'status--error');
}

// --- Step 1: kamera ---
async function initCamera() {
  setStep(1);
  const video = $('#cam-video');
  const res = await startCamera(video);
  if (res.ok) {
    $('#cam-fallback').hidden = true;
    $('#btn-camera-retry').hidden = true;
    setStatus('#cam-status', 'Kamera siap. Ambil foto selfie.', 'status--ok');
  } else {
    $('#cam-fallback').hidden = false;
    $('#btn-camera-retry').hidden = false;
    showError('#cam-status', 'Kamera tidak bisa diakses.', 'Izinkan kamera untuk absen, lalu coba lagi atau gunakan kamera perangkat di bawah.');
  }
}

async function takePhoto() {
  const video = $('#cam-video');
  let blob;
  if (video.srcObject) {
    blob = await captureFrame(video);
  } else {
    const fileInput = $('#cam-file');
    if (!fileInput.files.length) { showError('#cam-status', 'Belum ada foto. Ambil selfie dulu.'); return; }
    blob = fileInput.files[0];
  }
  state.photoBlob = await compressBlob(blob);
  $('#photo-preview').src = URL.createObjectURL(state.photoBlob);
  stopCamera(video);
  setStep(2);
  setStatus('#photo-status', 'Foto siap. Lanjut ambil lokasi.', 'status--ok');
}

// --- Step 3: lokasi ---
async function acquireLocation() {
  setStep(3);
  setStatus('#geo-status', 'Mencari lokasi…');
  const res = await getLocation();
  if (!res.ok) {
    state.geo = null;
    document.querySelector('.stepper__step[data-step="3"]').dataset.failed = '1';
    showError('#geo-status', res.message, 'Perbaiki lalu coba lagi.');
    $('#btn-retry-geo').hidden = false;
    return;
  }
  state.geo = res;
  document.querySelector('.stepper__step[data-step="3"]').dataset.failed = '';
  setStatus('#geo-status', `Lokasi didapat (akurasi ±${res.accuracy_m} m).`, 'status--ok');
  $('#btn-submit').disabled = false;
  $('#btn-retry-geo').hidden = true;
  setStep(4);
}

// --- Step 4: kirim ---
function newIdempotencyKey() {
  state.idempotencyKey = crypto.randomUUID();
  sessionStorage.setItem('absen_client_request_id', state.idempotencyKey);
}

function setBusy(busy, isCheckout) {
  state.busy = busy;
  $('#btn-submit').disabled = busy;
  $('#btn-submit').textContent = busy ? 'Mengirim…' : (isCheckout ? 'Kirim Absen Pulang' : 'Kirim Absen Masuk');
  $('#btn-submit').setAttribute('aria-busy', String(busy));
}

async function submit() {
  if (state.busy) return;
  if (!state.photoBlob) { showError('#submit-status', 'Foto belum ada. Ambil ulang selfie.'); return; }
  if (!state.geo) { showError('#submit-status', 'Lokasi belum didapat. Coba ambil lokasi lagi.'); return; }
  setBusy(true, document.body.dataset.absenType === 'checkout');
  if (!state.idempotencyKey) newIdempotencyKey();

  const form = new FormData();
  form.append('photo', state.photoBlob, 'selfie.jpg');
  form.append('latitude', state.geo.latitude);
  form.append('longitude', state.geo.longitude);
  form.append('accuracy', state.geo.accuracy_m);
  form.append('client_request_id', state.idempotencyKey);

  const isCheckout = document.body.dataset.absenType === 'checkout';
  const path = isCheckout ? '/attendance/check-out/' : '/attendance/check-in/';
  try {
    const res = await api('POST', path, form, true);
    sessionStorage.removeItem('absen_client_request_id');
    const time = new Intl.DateTimeFormat('id-ID', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jakarta' }).format(res.server_time ? new Date(res.server_time) : new Date());
    setStatus('#submit-status',
      `Absen ${isCheckout ? 'pulang' : 'masuk'} tercatat pada ${time}.`,
      'status--ok');
    $('#wizard-result').dataset.state = 'success';
    $('#wizard-result').innerHTML = '<p class="status status--ok">Kehadiran berhasil dicatat. Terima kasih!</p><a class="btn btn--secondary" href="/dashboard/siswa/">Kembali ke beranda</a>';
  } catch (err) {
    const code = err instanceof ApiError ? err.code : 'NETWORK';
    if (code === 'NETWORK') {
      showError('#submit-status', 'Koneksi terputus. Cek internet, lalu coba lagi.');
    } else if (code === 'ALREADY_CHECKED_IN' || code === 'ALREADY_CHECKED_OUT') {
      setStatus('#submit-status', `${err.message} Status kehadiran sudah tercatat; kamu tidak perlu mengirim ulang.`, 'status--ok');
      $('#wizard-result').dataset.state = 'already-recorded';
      $('#wizard-result').innerHTML = '<a class="btn btn--secondary" href="/dashboard/siswa/">Kembali ke beranda</a>';
      $('#btn-submit').hidden = true;
    } else if (code === 'AUTH_REQUIRED') {
      location.href = '/accounts/login/';
      return;
    } else {
      showError('#submit-status', err.message);
    }
    // biarkan idempotency key tetap untuk retry yang sama
    $('#btn-submit').disabled = false;
  } finally {
    setBusy(false, isCheckout);
    if (['success', 'already-recorded'].includes($('#wizard-result').dataset.state)) $('#btn-submit').hidden = true;
  }
}

// --- init ---
document.addEventListener('DOMContentLoaded', () => {
  const isCheckout = new URLSearchParams(location.search).get('type') === 'checkout';
  document.body.dataset.absenType = isCheckout ? 'checkout' : 'checkin';
  $('#capture-title').textContent = isCheckout ? 'Absen pulang' : 'Absen masuk';
  state.idempotencyKey = sessionStorage.getItem('absen_client_request_id') || null;
  const btnSubmit = $('#btn-submit');
  if (btnSubmit) btnSubmit.textContent = isCheckout ? 'Kirim Absen Pulang' : 'Kirim Absen Masuk';
  $('#btn-capture')?.addEventListener('click', takePhoto);
  $('#btn-retake')?.addEventListener('click', () => {
    state.photoBlob = null;
    const preview = $('#photo-preview');
    if (preview.src.startsWith('blob:')) URL.revokeObjectURL(preview.src);
    $('#cam-file').value = '';
    // Percobaan baru (foto diambil ulang), bukan retry jaringan → key idempotency baru.
    sessionStorage.removeItem('absen_client_request_id');
    state.idempotencyKey = null;
    initCamera();
  });
  $('#btn-camera-retry')?.addEventListener('click', initCamera);
  $('#btn-continue')?.addEventListener('click', acquireLocation);
  $('#btn-retry-geo')?.addEventListener('click', acquireLocation);
  $('#btn-submit')?.addEventListener('click', submit);
  initCamera();
});
