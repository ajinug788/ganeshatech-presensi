/* students-filter.js — toggle panel filter Master siswa */
(function () {
  function init() {
    var btn = document.getElementById('filter-toggle');
    var panel = document.getElementById('filter-panel');
    if (!btn || !panel || btn.dataset.wired) return;
    btn.dataset.wired = '1';
    btn.addEventListener('click', function () {
      var open = panel.hidden;
      panel.hidden = !open;
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
