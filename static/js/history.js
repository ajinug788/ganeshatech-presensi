const pageRoot = document.querySelector('#student-history-page');
if (pageRoot) {
  const listView = document.querySelector('#history-list-view');
  const detailView = document.querySelector('#history-detail-view');
  const monthInput = document.querySelector('#history-month');
  const sortInput = document.querySelector('#history-sort');
  const listStatus = document.querySelector('#history-list-status');
  const detailStatusLine = document.querySelector('#history-detail-status-line');
  const dayList = document.querySelector('#history-day-list');
  const historyUrl = pageRoot.dataset.historyUrl;
  const query = new URLSearchParams(window.location.search);

  const statusInfo = {
    present: { label: 'Masuk Kerja', short: 'Hadir', className: 'present' },
    late: { label: 'Terlambat', short: 'Terlambat', className: 'late' },
    absent: { label: 'Tidak Hadir', short: 'Tidak hadir', className: 'absent' },
    excused: { label: 'Izin / Sakit', short: 'Izin / sakit', className: 'excused' },
  };
  const monthFormatter = new Intl.DateTimeFormat('id-ID', { month: 'long', timeZone: 'Asia/Jakarta' });
  const monthShortFormatter = new Intl.DateTimeFormat('id-ID', { month: 'short', timeZone: 'Asia/Jakarta' });
  const weekdayFormatter = new Intl.DateTimeFormat('id-ID', { weekday: 'long', timeZone: 'Asia/Jakarta' });
  const longDateFormatter = new Intl.DateTimeFormat('id-ID', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Asia/Jakarta',
  });
  const timeFormatter = new Intl.DateTimeFormat('id-ID', {
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: 'Asia/Jakarta',
  });

  function dateAtNoon(dateString) {
    return new Date(`${dateString}T12:00:00+07:00`);
  }

  function currentMonthInJakarta() {
    const parts = new Intl.DateTimeFormat('en-CA', {
      year: 'numeric', month: '2-digit', timeZone: 'Asia/Jakarta',
    }).formatToParts(new Date());
    const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    return `${values.year}-${values.month}`;
  }

  function monthFromDate(dateString) {
    return dateString ? dateString.slice(0, 7) : currentMonthInJakarta();
  }

  function formatTime(isoDate) {
    return isoDate ? timeFormatter.format(new Date(isoDate)) : '';
  }

  function formatDuration(checkIn, checkOut) {
    if (!checkIn || !checkOut) return null;
    const minutes = Math.max(0, Math.floor((new Date(checkOut) - new Date(checkIn)) / 60000));
    const hours = Math.floor(minutes / 60);
    const remainder = minutes % 60;
    if (hours && remainder) return `${hours} Jam ${remainder} Menit`;
    if (hours) return `${hours} Jam`;
    return `${remainder} Menit`;
  }

  async function fetchRecords(params) {
    const search = new URLSearchParams({ page: '1', page_size: '50', include_count: 'false', ...params });
    const response = await fetch(`/api/v1/attendance/me/history/?${search.toString()}`, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    });
    if (response.status === 401) {
      window.location.href = '/accounts/login/';
      return null;
    }
    if (!response.ok) throw new Error(`Server menolak permintaan (${response.status})`);
    return response.json();
  }

  function updateListUrl() {
    const url = new URL(historyUrl, window.location.origin);
    url.searchParams.set('month', monthInput.value);
    url.searchParams.set('sort', sortInput.value);
    window.history.replaceState({}, '', `${url.pathname}${url.search}`);
  }

  function createDayCard(dateString, record) {
    const date = dateAtNoon(dateString);
    const label = statusInfo[record?.status] || null;
    const card = document.createElement(record ? 'a' : 'div');
    const statusClass = label ? label.className : 'empty';
    card.className = `history-day-card history-day-card--${statusClass}`;

    if (record) {
      const detailUrl = new URL(historyUrl, window.location.origin);
      detailUrl.searchParams.set('date', dateString);
      detailUrl.searchParams.set('month', monthInput.value);
      detailUrl.searchParams.set('sort', sortInput.value);
      card.href = `${detailUrl.pathname}${detailUrl.search}`;
      card.setAttribute('aria-label', `Detail ${longDateFormatter.format(date)}${label ? `, ${label.short}` : ''}`);
    }

    const day = document.createElement('span');
    day.className = 'history-day-number';
    const monthName = document.createElement('small');
    monthName.textContent = monthShortFormatter.format(date).replace('.', '').toLocaleUpperCase('id-ID');
    const dayNumber = document.createElement('strong');
    dayNumber.textContent = String(date.getDate());
    day.append(monthName, dayNumber);

    const description = document.createElement('span');
    description.className = 'history-day-description';
    const title = document.createElement('span');
    title.className = 'history-day-title';
    const weekday = document.createElement('strong');
    weekday.textContent = weekdayFormatter.format(date);
    title.append(weekday);
    if (label) {
      const badge = document.createElement('span');
      badge.className = `history-day-status history-day-status--${statusClass}`;
      badge.textContent = label.short;
      title.append(badge);
    }
    description.append(title);

    if (record) {
      const detail = document.createElement('small');
      if (record.status === 'late' && record.late_minutes) {
        detail.textContent = `Terlambat ${record.late_minutes} menit`;
      } else if (record.status === 'excused') {
        detail.textContent = 'Pengajuan izin disetujui';
      } else if (record.status === 'absent') {
        detail.textContent = 'Tidak ada presensi masuk';
      } else {
        detail.textContent = 'Rincian presensi tersedia';
      }
      description.append(detail);
    }

    const times = document.createElement('span');
    times.className = 'history-day-times';
    if (record && (record.check_in_at || record.check_out_at)) {
      times.textContent = `${formatTime(record.check_in_at) || '—'} - ${formatTime(record.check_out_at) || '—'}`;
    }
    card.append(day, description, times);
    return card;
  }

  function renderMonth(records) {
    const [year, month] = monthInput.value.split('-').map(Number);
    const recordsByDate = new Map(records.map((record) => [record.work_date, record]));
    const sortedRecords = [...records].sort((left, right) => left.work_date.localeCompare(right.work_date));
    const dates = [];

    if (sortedRecords.length) {
      const first = dateAtNoon(sortedRecords[0].work_date);
      const last = dateAtNoon(sortedRecords[sortedRecords.length - 1].work_date);
      const monthEnd = new Date(year, month, 0).getDate();
      const firstDay = Math.max(1, first.getDate() - first.getDay());
      const todayMonth = currentMonthInJakarta();
      const todayParts = new Intl.DateTimeFormat('en-CA', {
        day: '2-digit', timeZone: 'Asia/Jakarta',
      }).formatToParts(new Date());
      const todayDay = Number(todayParts.find((part) => part.type === 'day')?.value || 1);
      const lastDay = monthInput.value === todayMonth
        ? Math.min(todayDay, monthEnd)
        : Math.min(monthEnd, last.getDate() + (6 - last.getDay()));
      for (let day = firstDay; day <= lastDay; day += 1) {
        dates.push(`${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`);
      }
      if (sortInput.value === 'newest') dates.reverse();
    }

    dayList.replaceChildren(...dates.map((dateString) => createDayCard(dateString, recordsByDate.get(dateString))));
    if (dates.length) {
      listStatus.textContent = `${monthFormatter.format(dateAtNoon(`${monthInput.value}-01`)).toLocaleUpperCase('id-ID')} ${year}`;
    } else {
      listStatus.textContent = 'Belum ada catatan presensi pada periode ini.';
    }
  }

  async function loadMonth() {
    listStatus.textContent = 'Memuat riwayat…';
    dayList.replaceChildren();
    try {
      const data = await fetchRecords({ month: monthInput.value, sort: sortInput.value });
      if (data) renderMonth(data.results || []);
    } catch (error) {
      listStatus.textContent = `Riwayat belum dapat dimuat. ${error.message || 'Periksa koneksi lalu coba lagi.'}`;
    }
  }

  function setPhotoLink(container, mediaId, label) {
    if (!mediaId) return;
    const link = document.createElement('a');
    link.href = `/photos/${encodeURIComponent(mediaId)}/`;
    link.target = '_blank';
    link.rel = 'noopener';
    link.className = 'history-photo-link';
    link.innerHTML = '<span class="msym" aria-hidden="true">photo_camera</span>';
    const text = document.createElement('span');
    text.textContent = label;
    link.append(text);
    container.append(link);
  }

  function renderDetail(record, dateString) {
    const date = dateAtNoon(dateString);
    const label = statusInfo[record.status] || { label: record.status, className: 'empty' };
    const statusValue = document.querySelector('#history-detail-status');
    statusValue.textContent = label.label;
    statusValue.className = `history-summary-value history-summary-value--${label.className}`;
    document.querySelector('#history-detail-date').textContent = longDateFormatter.format(date);
    document.querySelector('#history-detail-late').textContent = `${record.late_minutes || 0} menit`;

    const duration = formatDuration(record.check_in_at, record.check_out_at);
    document.querySelector('#history-detail-duration').textContent = duration || '—';
    document.querySelector('#history-duration-label').textContent = duration || 'Belum lengkap';
    document.querySelector('#history-check-in-time').textContent = formatTime(record.check_in_at) || '—';
    document.querySelector('#history-check-out-time').textContent = formatTime(record.check_out_at) || '—';
    document.querySelector('#history-check-in-row').classList.toggle('is-missing', !record.check_in_at);
    document.querySelector('#history-check-out-row').classList.toggle('is-missing', !record.check_out_at);

    const photos = document.querySelector('#history-detail-photos');
    photos.replaceChildren();
    setPhotoLink(photos, record.check_in_media_id, 'Foto saat masuk');
    setPhotoLink(photos, record.check_out_media_id, 'Foto saat pulang');
    detailStatusLine.textContent = '';
  }

  async function loadDetail(dateString) {
    listView.hidden = true;
    detailView.hidden = false;
    const backUrl = new URL(historyUrl, window.location.origin);
    if (query.get('month')) backUrl.searchParams.set('month', query.get('month'));
    if (query.get('sort')) backUrl.searchParams.set('sort', query.get('sort'));
    document.querySelector('#history-detail-back').href = `${backUrl.pathname}${backUrl.search}`;
    detailStatusLine.textContent = 'Memuat rincian presensi…';
    try {
      const data = await fetchRecords({ date: dateString, page_size: '1' });
      if (!data) return;
      if (!data.results?.length) throw new Error('Catatan presensi untuk tanggal ini tidak ditemukan.');
      renderDetail(data.results[0], dateString);
    } catch (error) {
      detailStatusLine.textContent = error.message || 'Rincian presensi belum dapat dimuat.';
    }
  }

  async function initializeList() {
    monthInput.value = query.get('month') || '';
    sortInput.value = query.get('sort') === 'newest' ? 'newest' : 'oldest';
    if (!monthInput.value) {
      try {
        const latest = await fetchRecords({ page_size: '1', sort: 'newest' });
        monthInput.value = monthFromDate(latest?.results?.[0]?.work_date);
      } catch {
        monthInput.value = currentMonthInJakarta();
      }
    }
    updateListUrl();
    await loadMonth();
  }

  const selectedDate = query.get('date');
  if (selectedDate) {
    loadDetail(selectedDate);
  } else {
    initializeList();
    monthInput.addEventListener('change', () => {
      if (!monthInput.value) return;
      updateListUrl();
      loadMonth();
    });
    sortInput.addEventListener('change', () => {
      updateListUrl();
      loadMonth();
    });
  }
}
