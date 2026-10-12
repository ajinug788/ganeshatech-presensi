// dashboard.js — dashboard pembina: ringkasan, tabel, filter, modal koreksi & foto
import { api } from './api.js';

const $ = (s) => document.querySelector(s);
let rows = [];

const BADGE = {
  HADIR: 'badge--hadir', BELUM_PULANG: 'badge--belum', BELUM_HADIR: 'badge--tidak', PERLU_DITINJAU: 'badge--tinjau',
};

async function load() {
  const status = $('#pembina-status');
  status.textContent = 'Memuat data…';
  try {
    const res = await api('GET', '/attendance/records/');
    rows = res.results || [];
    if (res.summary) {
      $('#sum-hadir').textContent = res.summary.hadir ?? '–';
      $('#sum-belum').textContent = res.summary.belum_hadir ?? '–';
      $('#sum-pulang').textContent = res.summary.pulang ?? '–';
      $('#sum-tinjau').textContent = res.summary.perlu_ditinjau ?? '–';
    }
    render();
    status.textContent = '';
  } catch (e) {
    status.textContent = 'Gagal memuat: ' + e.message;
  }
}

function render() {
  const q = $('#f-cari').value.toLowerCase();
  const st = $('#f-status').value;
  const tbody = $('#tbl-siswa tbody');
  tbody.innerHTML = '';
  for (const r of rows) {
    if (q && !r.name.toLowerCase().includes(q)) continue;
    if (st && r.status !== st) continue;
    const tr = document.createElement('tr');
    tr.innerHTML =
      `<td><button class="btn btn--secondary" data-foto="${r.id}" style="padding:6px 10px;">Lihat</button></td>` +
      `<td>${r.name}</td><td>${r.check_in ?? '—'}</td><td>${r.check_out ?? '—'}</td>` +
      `<td><span class="badge ${BADGE[r.status] || ''}">${r.status.replace('_', ' ')}</span></td>` +
      `<td>${r.distance_m != null ? r.distance_m + ' m' : '—'}</td>` +
      `<td><button class="btn btn--secondary" data-koreksi="${r.id}" data-nama="${r.name}" style="padding:6px 10px;">Koreksi</button></td>`;
    tbody.appendChild(tr);
  }
  if (!tbody.children.length) $('#pembina-status').textContent = 'Tidak ada data cocok.';
}

function openModal(id) { $(id).hidden = false; }
function closeModal(id) { $(id).hidden = true; }

document.addEventListener('DOMContentLoaded', () => {
  load();
  $('#f-cari').addEventListener('input', render);
  $('#f-status').addEventListener('change', render);
  $('#f-tanggal').addEventListener('change', () => { /* backend filter; dummy abaikan */ });

  $('#tbl-siswa').addEventListener('click', async (ev) => {
    const fotoBtn = ev.target.closest('[data-foto]');
    if (fotoBtn) {
      $('#modal-foto-img').src = `/api/v1/photos/${fotoBtn.dataset.foto}/?dummy=1`;
      openModal('#modal-foto');
      return;
    }
    const korBtn = ev.target.closest('[data-koreksi]');
    if (korBtn) {
      $('#modal-nama').textContent = korBtn.dataset.nama;
      $('#kor-alasan').value = '';
      $('#kor-status').textContent = '';
      $('#kor-simpan').dataset.recordId = korBtn.dataset.koreksi;
      openModal('#modal-koreksi');
    }
  });

  $('#kor-batal').addEventListener('click', () => closeModal('#modal-koreksi'));
  $('#foto-tutup').addEventListener('click', () => closeModal('#modal-foto'));
  document.querySelectorAll('.modal').forEach(m =>
    m.addEventListener('click', (e) => { if (e.target === m) m.hidden = true; }));

  $('#kor-simpan').addEventListener('click', async () => {
    const alasan = $('#kor-alasan').value.trim();
    if (!alasan) { $('#kor-status').textContent = 'Alasan koreksi wajib diisi.'; $('#kor-status').className = 'status status--error'; return; }
    const recordId = $('#kor-simpan').dataset.recordId;
    try {
      await api('POST', `/attendance/records/${recordId}/corrections/`, {
        check_in: $('#kor-waktu-masuk').value || null,
        check_out: $('#kor-waktu-pulang').value || null,
        reason: alasan,
      });
      $('#kor-status').textContent = 'Koreksi tersimpan.';
      $('#kor-status').className = 'status status--ok';
      setTimeout(() => { closeModal('#modal-koreksi'); load(); }, 600);
    } catch (e) {
      $('#kor-status').textContent = e.message;
      $('#kor-status').className = 'status status--error';
    }
  });
});
