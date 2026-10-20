(() => {
  // If legacy theme bundle is present on the page (e.g. home page index.html), let it handle its own drawer animations.
  if (document.querySelector('script[src*="/bundle.js"]')) return;

  function initStorefrontDrawers() {
    if (window.__storefrontDrawersInitialized) return;
    window.__storefrontDrawersInitialized = true;

    let activeDrawerName = null;

    function getDrawer(drawerName) {
      if (!drawerName) return null;
      return document.querySelector(`.${drawerName}`) ||
             document.getElementById(drawerName) ||
             document.getElementById(drawerName.replace(/^site-/, '')) ||
             document.getElementById(`${drawerName}-drawer`);
    }

    function updateHeights(drawerEl) {
      if (!drawerEl) return;
      const header = document.querySelector('.site-header');
      const mobileNav = document.querySelector('.site-mobile-navbar, .klb-mobile-bottom');
      const headerHeight = header ? Math.round(header.getBoundingClientRect().height) : 0;
      const mobileNavHeight = mobileNav ? Math.round(mobileNav.getBoundingClientRect().height) : 0;
      drawerEl.style.setProperty('--header-height', `${headerHeight}px`);
      drawerEl.style.setProperty('--mobile-nav-height', `${mobileNavHeight}px`);
    }

    function closeAllDrawers() {
      // Remove active classes from body
      document.body.classList.remove(
        'site-menu-drawer-active',
        'site-categories-drawer-active',
        'site-search-drawer-active'
      );

      // Hide all drawers
      document.querySelectorAll('.site-drawer').forEach(drawerEl => {
        drawerEl.classList.remove('is-active', 'active');
        drawerEl.style.visibility = 'hidden';
        drawerEl.style.opacity = '0';
        drawerEl.setAttribute('aria-hidden', 'true');

        const inner = drawerEl.querySelector('.site-drawer-inner');
        if (inner) inner.style.transform = '';

        const overlay = drawerEl.querySelector('.site-drawer-overlay');
        if (overlay) {
          overlay.style.opacity = '0';
          overlay.style.visibility = 'hidden';
        }
      });

      // Deactivate all toggle buttons
      document.querySelectorAll('.menu-drawer-toggle, [data-drawer]').forEach(btn => {
        btn.classList.remove('active');
        btn.setAttribute('aria-expanded', 'false');
      });

      // Clean up any lingering loading states
      document.querySelectorAll('.is-loading, .is-navigating').forEach(el => {
        el.classList.remove('is-loading', 'is-navigating');
      });

      document.body.style.overflow = '';
      activeDrawerName = null;
    }

    function openDrawer(drawerName, triggerBtn) {
      const drawerEl = getDrawer(drawerName);
      if (!drawerEl) return;

      // Toggle off if same drawer is clicked again
      if (activeDrawerName === drawerName) {
        closeAllDrawers();
        return;
      }

      closeAllDrawers();
      activeDrawerName = drawerName;

      updateHeights(drawerEl);
      document.body.classList.add(`${drawerName}-active`);
      drawerEl.classList.add('is-active', 'active');
      drawerEl.style.visibility = 'visible';
      drawerEl.style.opacity = '1';
      drawerEl.setAttribute('aria-hidden', 'false');

      const inner = drawerEl.querySelector('.site-drawer-inner');
      if (inner) {
        inner.style.transform = 'translateX(0)';
      }

      const overlay = drawerEl.querySelector('.site-drawer-overlay');
      if (overlay) {
        overlay.style.visibility = 'visible';
        overlay.style.opacity = '1';
      }

      // Mark trigger buttons as active
      if (triggerBtn) {
        triggerBtn.classList.add('active');
        triggerBtn.setAttribute('aria-expanded', 'true');
      }
      document.querySelectorAll(`[data-drawer="${drawerName}"]`).forEach(btn => {
        btn.classList.add('active');
        btn.setAttribute('aria-expanded', 'true');
      });

      // Remove loading spinner from trigger
      document.querySelectorAll('.is-loading, .is-navigating').forEach(el => {
        el.classList.remove('is-loading', 'is-navigating');
      });

      document.body.style.overflow = 'hidden';
    }

    // Delegated click handler for triggers, close buttons, overlays, and links
    document.addEventListener('click', event => {
      // 1. Drawer Toggle Buttons (Header Hamburger, Bottom Navbar Categories, etc.)
      const toggleBtn = event.target.closest('.menu-drawer-toggle, [data-drawer]');
      if (toggleBtn) {
        const targetDrawer = toggleBtn.getAttribute('data-drawer');
        if (targetDrawer) {
          event.preventDefault();
          event.stopPropagation();
          openDrawer(targetDrawer, toggleBtn);
          return;
        }
      }

      // 2. Drawer Close Buttons
      const closeBtn = event.target.closest('.close-button, .close-button a, .site-drawer-close');
      if (closeBtn && closeBtn.closest('.site-drawer')) {
        event.preventDefault();
        event.stopPropagation();
        closeAllDrawers();
        return;
      }

      // 3. Drawer Overlay Click
      if (event.target.classList && event.target.classList.contains('site-drawer-overlay')) {
        event.preventDefault();
        event.stopPropagation();
        closeAllDrawers();
        return;
      }

      // 4. Sub-menu accordion toggle inside drawer
      const parentLink = event.target.closest('.site-drawer .menu-item-has-children > a');
      if (parentLink) {
        event.preventDefault();
        event.stopPropagation();
        parentLink.parentElement.classList.toggle('active');
        return;
      }

      // 5. Normal Navigation Link inside drawer -> close drawer so user can navigate cleanly
      const navLink = event.target.closest('.site-drawer .site-menu a, .site-drawer .menu-item a');
      if (navLink && navLink.getAttribute('href') && navLink.getAttribute('href') !== '#') {
        closeAllDrawers();
      }
    });

    // Close on Escape key
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && activeDrawerName) {
        closeAllDrawers();
      }
    });

    // Recalculate dimensions on window resize
    window.addEventListener('resize', () => {
      if (activeDrawerName) {
        const drawerEl = getDrawer(activeDrawerName);
        if (drawerEl) updateHeights(drawerEl);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initStorefrontDrawers);
  } else {
    initStorefrontDrawers();
  }
})();
