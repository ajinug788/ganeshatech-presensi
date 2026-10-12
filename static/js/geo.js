// geo.js — getCurrentPosition high accuracy, timeout ~10s, pesan error BERBEDA per kegagalan
export function getLocation() {
  return new Promise((resolve) => {
    if (!('geolocation' in navigator)) {
      resolve({ ok: false, code: 'LOCATION_UNAVAILABLE', message: 'Perangkat tidak mendukung GPS/lokasi.' });
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({
        ok: true,
        latitude: pos.coords.latitude,
        longitude: pos.coords.longitude,
        accuracy_m: Math.round(pos.coords.accuracy),
      }),
      (err) => {
        const map = {
          1: { code: 'LOCATION_PERMISSION_REQUIRED', message: 'Aktifkan izin lokasi, lalu coba lagi.' },
          2: { code: 'LOCATION_UNAVAILABLE', message: 'Lokasi tidak terdeteksi. Pastikan GPS aktif / cari area terbuka.' },
          3: { code: 'LOCATION_UNAVAILABLE', message: 'Waktu pencarian lokasi habis. Coba lagi di area terbuka.' },
        };
        resolve({ ok: false, ...(map[err.code] || { code: 'LOCATION_UNAVAILABLE', message: 'Gagal mengambil lokasi. Coba lagi.' }) });
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
  });
}
