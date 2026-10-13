// Mobile nav v2: tombol .nav-toggle (logo + teks) di topbar = hamburger.
(function () {
  function setOpen(open) {
    if (window.innerWidth > 760) open = false;
    document.body.classList.toggle('sidebar-open', open);
    const btn = document.querySelector('.nav-toggle');
    if (btn) btn.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.nav-toggle');
    if (btn) { e.preventDefault(); setOpen(!document.body.classList.contains('sidebar-open')); return; }
    if (e.target.closest('.sidebar-overlay')) { setOpen(false); return; }
    if (e.target.closest('.drawer-close')) { setOpen(false); return; }
    const navLink = e.target.closest('.side-nav .nav-link');
    if (navLink && document.body.classList.contains('sidebar-open')) setOpen(false);
  });

  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setOpen(false); });
  document.addEventListener('turbo:load', () => setOpen(false));
  window.addEventListener('resize', () => { if (window.innerWidth > 760) setOpen(false); });
})();
