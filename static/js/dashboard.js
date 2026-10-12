import { api } from './api.js';

const $ = (selector) => document.querySelector(selector);
const pageSize = 8;
let rows = [];
let page = 0;
let returnFocus = null;

const STATUS = {
  HADIR: ['Hadir', 'badge--hadir'],
  BELUM_PULANG: ['Belum pulang', 'badge--belum'],
  BELUM_HADIR: ['Belum hadir', 'badge--tidak'],
  PERLU_DITINJAU: ['Perlu ditinjau', 'badge--tinjau'],
};

function button(label, attrs = {}) {
  const el = document.createElement('button');
  el.type = 'button';
  el.className = 'btn btn--secondary';
  el.textContent = label;
  for (const [key, value] of Object.entries(attrs)) el.dataset[key] = value;
  return el;
}

function filteredRows() {
  const query = $('#f-cari').value.trim().toLocaleLowerCase('id-ID');
  const status = $('#f-status').value;
  const group = $('#f-kelompok').value;
  const date = $('#f-tanggal').value;
  return rows.filter((row) => {
    const matchesName = !query || row.name.toLocaleLowerCase('id-ID').includes(query);
    const matchesStatus = !status || row.status === status;
    const matchesGroup = !group || (row.group || row.group_name || '') === group;
    const matchesDate = !date || (row.date || '') === date;
    return matchesName && matchesStatus && matchesGroup && matchesDate;
  });
}

function render() {
  const visibleRows = filteredRows();
  const start = page * pageSize;
  const pageRows = visibleRows.slice(start, start + pageSize);
  const tbody = $('#tbl-siswa tbody');
  tbody.replaceChildren();

  for (const record of pageRows) {
    const tr = document.createElement('tr');
    const photoCell = document.createElement('td');
    photoCell.append(button('Lihat', { foto: String(record.id) }));
    tr.append(photoCell);
    const nameCell = document.createElement('td');
    nameCell.textContent = record.name;
    tr.append(nameCell);
    for (const value of [record.check_in, record.check_out]) {
      const cell = document.createElement('td');
      cell.textContent = value || '—';
      tr.append(cell);
    }
    const statusCell = document.createElement('td');
    const badge = document.createElement('span');
    const [label, style] = STATUS[record.status] || [record.status, 'badge--tidak'];
    badge.className = `badge ${style}`;
    badge.textContent = label;
    statusCell.append(badge);
    tr.append(statusCell);
    const distanceCell = document.createElement('td');
    distanceCell.textContent = record.distance_m == null ? '—' : `${record.distance_m} m`;
    tr.append(distanceCell);
    const actionCell = document.createElement('td');
    actionCell.append(button('Koreksi', { koreksi: String(record.id), nama: record.name }));
    tr.append(actionCell);
    tbody.append(tr);
  }

  const end = Math.min(start + pageRows.length, visibleRows.length);
  $('#row-count').textContent = `${visibleRows.length} siswa`;
  $('#page-label').textContent = visibleRows.length ? `Menampilkan ${start + 1}–${end} dari ${visibleRows.length}` : 'Tidak ada data cocok';
  $('#page-prev').disabled = page === 0;
  $('#page-next').disabled = end >= visibleRows.length;
  $('#pembina-status').textContent = visibleRows.length ? '' : 'Tidak ada data yang sesuai dengan pencarian atau filter.';
}

function openModal(id) {
  returnFocus = document.activeElement;
  $(id).hidden = false;
  $(id).querySelector('button, input, textarea')?.focus();
}

function closeModal(id) {
  $(id).hidden = true;
  returnFocus?.focus();
}

// Foto bukti via endpoint terotorisasi /photos/{id}/ — bukan file publik.
async function openPhotoModal(photoId) {
  const content = $('#foto-content');
  content.className = 'empty-state';
  content.innerHTML = '<strong>Memuat foto…</strong>';
  openModal('#modal-foto');
  try {
    const res = await fetch(`/api/v1/photos/${encodeURIComponent(photoId)}/`, { credentials: 'same-origin' });
    if (!res.ok) throw new Error(res.status === 404 ? 'Foto tidak ditemukan.' : 'Foto belum tersedia di server.');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const img = document.createElement('img');
    img.src = url;
    img.alt = 'Foto selfie absensi';
    img.style.cssText = 'width:100%;max-height:60vh;object-fit:contain;border-radius:12px;';
    img.onload = () => URL.revokeObjectURL(url);
    content.className = '';
    content.replaceChildren(img);
  } catch (error) {
    content.className = 'empty-state';
    content.innerHTML = `<strong>Foto tidak tersedia.</strong>${error.message || 'Coba lagi nanti.'}`;
  }
}

async function load() {
  $('#pembina-status').textContent = 'Memuat data kehadiran…';
  try {
    const result = await api('GET', '/attendance/records/');
    rows = result.results || [];
    const groupSelect = $('#f-kelompok');
    const groups = [...new Set(rows.map(row => row.group || row.group_name).filter(Boolean))].sort();
    groupSelect.replaceChildren(new Option('Semua kelompok', ''));
    for (const group of groups) groupSelect.add(new Option(group, group));
    if (result.summary) {
      $('#sum-hadir').textContent = result.summary.hadir ?? '—';
      $('#sum-belum').textContent = result.summary.belum_hadir ?? '—';
      $('#sum-pulang').textContent = result.summary.pulang ?? '—';
      $('#sum-tinjau').textContent = result.summary.perlu_ditinjau ?? '—';
    }
    $('#pembina-status').className = 'status-line';
    page = 0;
    render();
  } catch (error) {
    $('#pembina-status').className = 'status status--error';
    $('#pembina-status').textContent = `Data belum dapat dimuat. ${error.message || 'Periksa koneksi lalu coba lagi.'}`;
    $('#row-count').textContent = '—';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  $('#today-label').textContent = new Intl.DateTimeFormat('id-ID', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'Asia/Jakarta' }).format(new Date());
  load();
  $('#f-cari').addEventListener('input', () => { page = 0; render(); });
  $('#f-status').addEventListener('change', () => { page = 0; render(); });
  $('#f-kelompok').addEventListener('change', () => { page = 0; render(); });
  $('#f-tanggal').addEventListener('change', () => { page = 0; render(); });
  $('#page-prev').addEventListener('click', () => { page = Math.max(0, page - 1); render(); });
  $('#page-next').addEventListener('click', () => { page += 1; render(); });

  $('#tbl-siswa').addEventListener('click', (event) => {
    const photoButton = event.target.closest('[data-foto]');
    if (photoButton) { openPhotoModal(photoButton.dataset.foto); return; }
    const correctionButton = event.target.closest('[data-koreksi]');
    if (!correctionButton) return;
    $('#modal-nama').textContent = correctionButton.dataset.nama;
    $('#kor-alasan').value = '';
    $('#kor-waktu-masuk').value = '';
    $('#kor-waktu-pulang').value = '';
    $('#kor-status').textContent = '';
    $('#kor-simpan').dataset.recordId = correctionButton.dataset.koreksi;
    openModal('#modal-koreksi');
  });

  $('#kor-batal').addEventListener('click', () => closeModal('#modal-koreksi'));
  $('#foto-tutup').addEventListener('click', () => closeModal('#modal-foto'));
  document.querySelectorAll('.modal').forEach((modal) => {
    modal.addEventListener('click', (event) => { if (event.target === modal) closeModal(`#${modal.id}`); });
    modal.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeModal(`#${modal.id}`); });
  });

  $('#kor-simpan').addEventListener('click', async (event) => {
    const saveButton = event.currentTarget;
    const reason = $('#kor-alasan').value.trim();
    const status = $('#kor-status');
    if (!reason) {
      status.className = 'status status--error';
      status.textContent = 'Alasan koreksi wajib diisi.';
      $('#kor-alasan').focus();
      return;
    }
    saveButton.disabled = true;
    try {
      await api('POST', `/attendance/records/${saveButton.dataset.recordId}/corrections/`, {
        check_in: $('#kor-waktu-masuk').value || null,
        check_out: $('#kor-waktu-pulang').value || null,
        reason,
      });
      status.className = 'status status--ok';
      status.textContent = 'Koreksi tersimpan dan tercatat.';
      window.setTimeout(() => { closeModal('#modal-koreksi'); load(); }, 700);
    } catch (error) {
      status.className = 'status status--error';
      status.textContent = error.message || 'Koreksi belum dapat disimpan.';
    } finally {
      saveButton.disabled = false;
    }
  });
});
