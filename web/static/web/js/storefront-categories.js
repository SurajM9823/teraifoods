(() => {
  // Pages with the original theme bundle retain its existing drawer animations.
  if (document.querySelector('script[src*="/bundle.js"]')) return;
  const drawer = document.querySelector('.site-categories-drawer');
  if (!drawer) return;
  const inner = drawer.querySelector('.site-drawer-inner');
  const overlay = drawer.querySelector('.site-drawer-overlay');
  const buttons = document.querySelectorAll('[data-drawer="site-categories-drawer"]');
  let opened = false;
  function toggle(show) {
    opened = show;
    drawer.style.setProperty('--header-height', `${document.querySelector('.site-header')?.getBoundingClientRect().height || 0}px`);
    drawer.style.setProperty('--mobile-nav-height', `${document.querySelector('.site-mobile-navbar')?.getBoundingClientRect().height || 0}px`);
    document.body.classList.toggle('site-categories-drawer-active', show);
    drawer.style.visibility = show ? 'visible' : 'hidden';
    drawer.style.opacity = show ? '1' : '0';
    if (inner) inner.style.transform = show ? 'translateX(0)' : '';
    if (overlay) { overlay.style.opacity = show ? '1' : '0'; overlay.style.visibility = show ? 'visible' : 'hidden'; }
    buttons.forEach(button => { button.classList.toggle('active', show); button.setAttribute('aria-expanded', String(show)); });
  }
  buttons.forEach(button => button.addEventListener('click', event => {
    event.preventDefault(); toggle(!opened);
  }));
  overlay?.addEventListener('click', () => toggle(false));
  document.addEventListener('keydown', event => { if (event.key === 'Escape') toggle(false); });
  drawer.querySelectorAll('.menu-item-has-children > a').forEach(link => link.addEventListener('click', event => {
    event.preventDefault();
    link.parentElement.classList.toggle('active');
  }));
})();
