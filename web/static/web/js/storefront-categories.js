(() => {
  // Check if already initialized to avoid duplicate binding
  if (window.__teraiUnifiedDrawersInitialized) return;
  window.__teraiUnifiedDrawersInitialized = true;

  function initUnifiedDrawers() {
    const drawers = new Map();
    let activeDrawer = null;

    const clearButtons = () => {
      document.body.classList.remove(
        'site-menu-drawer-active',
        'site-categories-drawer-active',
        'site-search-drawer-active'
      );
      document.querySelectorAll('.menu-drawer-toggle, [data-drawer]').forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-expanded', 'false');
      });
      document.querySelectorAll('.is-loading, .is-navigating').forEach(el => {
        el.classList.remove('is-loading', 'is-navigating');
      });
      document.body.style.overflow = '';
    };

    const closeDrawer = () => {
      clearButtons();
      drawers.forEach(controller => controller.reverse());
      activeDrawer = null;
    };

    function registerDrawer(item) {
      if (!item || drawers.has(item)) return;
      const inner = item.querySelector('.site-drawer-inner');
      const overlay = item.querySelector('.site-drawer-overlay');

      // CSS owns transitions. No second animation may restore an invisible backdrop.
      drawers.set(item, {
        play: () => {
          item.classList.add('is-active');
          item.setAttribute('aria-hidden', 'false');
          item.inert = false;
        },
        reverse: () => {
          item.classList.remove('is-active', 'active');
          item.setAttribute('aria-hidden', 'true');
          item.inert = true;
        }
      });
      drawers.get(item).reverse();

      // Close on inner close button and backdrop click
      item.querySelectorAll('.close-button, .close-button a, .site-drawer-close, .site-drawer-overlay').forEach(closeEl => {
        closeEl.addEventListener('click', event => {
          event.preventDefault();
          event.stopPropagation();
          closeDrawer();
        });
      });

      // Auto-close on normal link click inside drawer
      item.querySelectorAll('.site-menu a, .menu-item a').forEach(navLink => {
        navLink.addEventListener('click', () => {
          if (navLink.parentElement && navLink.parentElement.classList.contains('menu-item-has-children')) return;
          closeDrawer();
        });
      });

      // Accordion dropdown for sub-categories
      item.querySelectorAll('.menu-item-has-children > a').forEach(toggleLink => {
        toggleLink.addEventListener('click', event => {
          event.preventDefault();
          event.stopPropagation();
          toggleLink.parentElement.classList.toggle('active');
        });
      });
    }

    // Register all initial drawers in the DOM
    document.querySelectorAll('.site-menu-drawer, .site-categories-drawer, .site-search-drawer').forEach(registerDrawer);
    window.teraiCloseNavigationDrawers = closeDrawer;

    // Global delegated click listener for any trigger button
    document.addEventListener('click', event => {
      // 1. Check if clicking a drawer toggle button
      const button = event.target.closest('.menu-drawer-toggle, [data-drawer]');
      if (button) {
        const name = button.dataset.drawer || button.getAttribute('data-drawer');
        if (name) {
          const item = document.querySelector(`.${name}`) || 
                       document.getElementById(name) || 
                       document.getElementById(name.replace(/^site-/, '')) ||
                       document.getElementById(`${name}-drawer`);
          if (item) {
            event.preventDefault();
            event.stopPropagation();

            registerDrawer(item);

            const wasOpen = activeDrawer === item;
            closeDrawer();

            if (!wasOpen) {
              activeDrawer = item;
              const anim = drawers.get(item);
              if (anim && typeof anim.play === 'function') {
                anim.play();
              }
              button.classList.add('active');
              button.setAttribute('aria-expanded', 'true');
              document.body.classList.add(`${name}-active`);
              document.body.style.overflow = 'hidden';

              // Also mark any other button targeting this drawer
              document.querySelectorAll(`[data-drawer="${name}"]`).forEach(b => {
                b.classList.add('active');
                b.setAttribute('aria-expanded', 'true');
              });
            }
            return;
          }
        }
      }

      // 2. Check if clicking close button inside any drawer
      const closeBtn = event.target.closest('.close-button, .close-button a, .site-drawer-close');
      if (closeBtn && closeBtn.closest('.site-drawer')) {
        event.preventDefault();
        event.stopPropagation();
        closeDrawer();
        return;
      }

      // 3. Check if clicking backdrop overlay
      if (event.target.classList && event.target.classList.contains('site-drawer-overlay')) {
        event.preventDefault();
        event.stopPropagation();
        closeDrawer();
        return;
      }
    });

    // Close on Escape key
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') closeDrawer();
    });

    window.addEventListener('pagehide', closeDrawer);
    window.matchMedia('(min-width: 1200px)').addEventListener('change', closeDrawer);

    // Reset when page is restored from bfcache
    window.addEventListener('pageshow', event => {
      if (event.persisted) closeDrawer();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initUnifiedDrawers);
  } else {
    initUnifiedDrawers();
  }
})();
