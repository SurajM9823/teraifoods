(() => {
  'use strict';
  const passwordToggle = document.querySelector('.password-toggle');
  passwordToggle?.addEventListener('click', () => {
    const input = document.getElementById(passwordToggle.getAttribute('aria-controls'));
    const show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    passwordToggle.textContent = show ? 'Hide' : 'Show';
    passwordToggle.setAttribute('aria-pressed', String(show));
  });

  const sidebar = document.getElementById('admin-sidebar');
  if (!sidebar) return;
  const body = document.body;
  const pin = document.querySelector('.pin-button');
  const menu = document.querySelector('.mobile-menu');
  const backdrop = document.querySelector('.sidebar-backdrop');
  const mobile = window.matchMedia('(max-width: 767px)');
  function setPinned(pinned) {
    body.classList.toggle('sidebar-pinned', pinned);
    pin.setAttribute('aria-pressed', String(pinned));
    pin.title = pinned ? 'Use automatic sidebar' : 'Keep sidebar open';
    pin.querySelector('.pin-label').textContent = pin.title;
  }
  try { setPinned(localStorage.getItem('terai_admin_sidebar_pinned') === 'true'); } catch (_) { setPinned(false); }
  pin.addEventListener('click', () => {
    const pinned = !body.classList.contains('sidebar-pinned');
    setPinned(pinned);
    try { localStorage.setItem('terai_admin_sidebar_pinned', String(pinned)); } catch (_) { /* Storage may be disabled. */ }
    // Release mouse focus so auto-collapse works immediately after leaving the rail.
    if (!pinned && !pin.matches(':focus-visible')) pin.blur();
  });
  function setMobileOpen(open, restoreFocus = true) {
    body.classList.toggle('sidebar-mobile-open', open);
    backdrop.hidden = !open;
    menu.setAttribute('aria-expanded', String(open));
    menu.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    sidebar.inert = mobile.matches && !open;
    document.querySelector('.workspace').inert = mobile.matches && open;
    if (open) sidebar.querySelector('a').focus();
    else if (restoreFocus && mobile.matches) menu.focus();
  }
  menu.addEventListener('click', () => setMobileOpen(!body.classList.contains('sidebar-mobile-open')));
  backdrop.addEventListener('click', () => setMobileOpen(false));
  document.addEventListener('keydown', (event) => {
    if (!body.classList.contains('sidebar-mobile-open')) return;
    if (event.key === 'Escape') setMobileOpen(false);
    if (event.key === 'Tab') {
      const items = [...sidebar.querySelectorAll('a[href], button:not([disabled])')].filter(el => el.getClientRects().length);
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  mobile.addEventListener('change', () => setMobileOpen(false, false));
  setMobileOpen(false, false);
})();
