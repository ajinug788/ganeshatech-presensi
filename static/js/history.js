// history.js — riwayat siswa dari API nyata /api/v1/attendance/me/history/ (server-side pagination)
const tbody = document.querySelector('#tbl-history tbody');
const status = document.querySelector('#hist-status');
const count = document.querySelector('#hist-count');
const btnPrev = document.querySelector('#hist-prev');
const btnNext = document.querySelector('#hist-next');

let page = 1;
let totalPages = 1;
let total = 0;

const STATUS = {
  present: ['Hadir', 'badge--hadir'],
  late: ['Terlambat', 'badge--belum'],
  absent: ['Tidak hadir', 'badge--tinjau'],
  excused: ['Izin / sakit', 'badge--tidak'],
};

function fmtJam(iso) {
  if (!iso) return '—';
  return new Intl.DateTimeFormat('id-ID', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jakarta' }).format(new Date(iso));
}

function fmtTanggal(dateStr) {
  return new Intl.DateTimeFormat('id-ID', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Asia/Jakarta' }).format(new Date(`${dateStr}T12:00:00+07:00`));
}

function getCookie(name) {
  const m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return m ? decodeURIComponent(m[1]) : null;
}

async function load() {
  status.textContent = 'Memuat riwayat…';
  status.className = 'status-line';
  try {
    const res = await fetch(`/api/v1/attendance/me/history/?page=${page}&page_size=8`, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    });
    if (res.status === 401) { window.location.href = '/accounts/login/'; return; }
    if (!res.ok) throw new Error('Server menolak permintaan (' + res.status + ')');
    const data = await res.json();
    total = data.count ?? 0;
    totalPages = Math.max(1, Math.ceil(total / (data.page_size ?? 8)));
    tbody.replaceChildren();
    for (const r of data.results || []) {
      const row = document.createElement('tr');
      const date = document.createElement('td');
      date.textContent = fmtTanggal(r.work_date);
      row.append(date);
      const masuk = document.createElement('td');
      masuk.textContent = fmtJam(r.check_in_at);
      row.append(masuk);
      const pulang = document.createElement('td');
      pulang.textContent = fmtJam(r.check_out_at);
      row.append(pulang);
      const st = document.createElement('td');
      const badge = document.createElement('span');
      const [label, style] = STATUS[r.status] || [r.status, 'badge--tidak'];
      badge.className = `badge ${style}`;
      badge.textContent = r.status === 'late' && r.late_minutes ? `Terlambat ${r.late_minutes} mnt` : label;
      st.append(badge);
      row.append(st);
      const foto = document.createElement('td');
      if (r.check_in_media_id) {
        const link = document.createElement('a');
        link.href = `/photos/${r.check_in_media_id}/`;
        link.target = '_blank';
        link.rel = 'noopener';
        link.textContent = 'Lihat foto';
        foto.append(link);
      } else {
        foto.textContent = '—';
      }
      row.append(foto);
      tbody.append(row);
    }
    const start = total ? (page - 1) * (data.page_size ?? 8) + 1 : 0;
    const end = Math.min(page * (data.page_size ?? 8), total);
    count.textContent = total ? `Menampilkan ${start}–${end} dari ${total} catatan` : 'Belum ada catatan';
    btnPrev.disabled = page <= 1;
    btnNext.disabled = page >= totalPages;
    status.textContent = '';
  } catch (error) {
    status.className = 'status status--error';
    status.textContent = `Riwayat belum dapat dimuat. ${error.message || 'Periksa koneksi lalu coba lagi.'}`;
    count.textContent = '—';
  }
}

btnPrev.addEventListener('click', () => { if (page > 1) { page -= 1; load(); } });
btnNext.addEventListener('click', () => { if (page < totalPages) { page += 1; load(); } });
load();
