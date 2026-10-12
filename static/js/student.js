import { api } from './api.js';

const dateEl = document.querySelector('#today-date');
const date = new Intl.DateTimeFormat('id-ID', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Asia/Jakarta' });
dateEl.textContent = date.format(new Date());

try {
  const today = await api('GET', '/attendance/today/');
  const title = document.querySelector('#status-title');
  const detail = document.querySelector('#status-detail');
  if (today.state === 'BELUM_MASUK') {
    title.textContent = 'Selamat pagi, siap untuk hari ini?';
    detail.textContent = 'Kehadiranmu belum tercatat. Pastikan kamu sudah berada di area absensi.';
    document.querySelector('#btn-checkin').hidden = false;
  } else if (today.state === 'SUDAH_MASUK') {
    title.textContent = 'Satu langkah sudah selesai.';
    detail.textContent = `Absen masuk tercatat pukul ${today.check_in_time || '—'}. Jangan lupa absen pulang nanti.`;
    document.querySelector('#btn-checkout').hidden = false;
  } else {
    title.textContent = 'Hari ini sudah lengkap!';
    detail.textContent = `Masuk ${today.check_in_time || '—'} · Pulang ${today.check_out_time || '—'}. Sampai jumpa besok.`;
    document.querySelector('#complete-badge').hidden = false;
  }
} catch (error) {
  const notice = document.querySelector('#home-error');
  notice.textContent = `Status kehadiran belum dapat dimuat. ${error.message || 'Periksa koneksi lalu muat ulang halaman.'}`;
  notice.hidden = false;
  document.querySelector('#status-title').textContent = 'Status belum tersedia';
  document.querySelector('#status-detail').textContent = 'Kami belum bisa memastikan status kehadiranmu.';
}
