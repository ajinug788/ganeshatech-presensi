import { api } from './api.js';

const tbody = document.querySelector('#tbl-history tbody');
const status = document.querySelector('#hist-status');
const count = document.querySelector('#hist-count');
const pageSize = 8;
let records = [];
let page = 0;

const STATUS = {
  HADIR: ['Hadir', 'badge--hadir'],
  BELUM_PULANG: ['Belum pulang', 'badge--belum'],
  BELUM_HADIR: ['Belum hadir', 'badge--tidak'],
  PERLU_DITINJAU: ['Perlu ditinjau', 'badge--tinjau'],
};

function render() {
  tbody.replaceChildren();
  const visible = records.slice(page * pageSize, (page + 1) * pageSize);
  for (const record of visible) {
    const row = document.createElement('tr');
    const date = document.createElement('td');
    date.textContent = new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Asia/Jakarta' }).format(new Date(`${record.date}T12:00:00+07:00`));
    row.append(date);
    for (const value of [record.check_in, record.check_out]) {
      const cell = document.createElement('td');
      cell.textContent = value || '—';
      row.append(cell);
    }
    const cell = document.createElement('td');
    const badge = document.createElement('span');
    const [label, style] = STATUS[record.status] || [record.status, 'badge--tidak'];
    badge.className = `badge ${style}`;
    badge.textContent = label;
    cell.append(badge);
    row.append(cell);
    tbody.append(row);
  }
  const start = records.length ? page * pageSize + 1 : 0;
  const end = Math.min((page + 1) * pageSize, records.length);
  count.textContent = records.length ? `Menampilkan ${start}–${end} dari ${records.length} catatan` : 'Belum ada catatan';
  document.querySelector('#hist-prev').disabled = page === 0;
  document.querySelector('#hist-next').disabled = end >= records.length;
  status.textContent = records.length ? '' : 'Belum ada riwayat absensi.';
}

document.querySelector('#hist-prev').addEventListener('click', () => { page = Math.max(0, page - 1); render(); });
document.querySelector('#hist-next').addEventListener('click', () => { page += 1; render(); });

try {
  const response = await api('GET', '/attendance/my-records/');
  records = response.results || [];
  render();
} catch (error) {
  status.className = 'status status--error';
  status.textContent = `Riwayat belum dapat dimuat. ${error.message || 'Periksa koneksi lalu coba lagi.'}`;
  count.textContent = '—';
}
