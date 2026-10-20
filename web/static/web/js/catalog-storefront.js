/* Backend data and pagination. Existing card HTML and CSS remain authoritative. */
(() => {
  'use strict';
  const ready = fn => document.readyState !== 'complete' ? document.addEventListener('DOMContentLoaded', fn) : fn();
  const read = id => { try { return JSON.parse(document.getElementById(id)?.textContent || 'null'); } catch { return null; } };
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  ready(() => {
    const grid = document.getElementById('shop-products-container');
    const initial = read('catalog-page');
    let info = initial, busy = false, generation = 0, controller, retry = false;
    let filters = new URLSearchParams(location.search);
    if (filters.has('s') && !filters.has('q')) filters.set('q', filters.get('s'));
    const detail = read('catalog-detail');
    const notify = message => window.TeraiCatalog?.showToast('Product availability', message, 'warning');
    if (window.TeraiCatalog) window.TeraiCatalog.validateCart = async (cart = window.TeraiCatalog.getCart()) => {
      if (cart.some(item => item.catalogVersion !== 2)) {
        notify('Your basket contains items from the old catalog. Please remove and re-add them.');
        return false;
      }
      try {
        const csrf = document.cookie.split('; ').find(value => value.startsWith('csrftoken='))?.split('=').slice(1).join('=') ||
          document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
        const response = await fetch('/api/cart/quote/', {method:'POST',
          headers:{'Content-Type':'application/json','X-CSRFToken':decodeURIComponent(csrf)},
          body:JSON.stringify({items:cart.map(item => ({product_id:Number(item.id), quantity:item.quantity}))})});
        const data = await response.json();
        if (!response.ok) { notify(data.errors?.join(' ') || 'Unable to validate basket.'); return false; }
        const refreshed = new Map(data.items.map(item => [String(item.id), {id:String(item.id),title:item.name,
          image:item.image,price:Number(item.price),quantity:item.quantity,catalogVersion:2}]));
        window.TeraiCatalog.saveCart(window.TeraiCatalog.getCart().map(item => refreshed.get(String(item.id)) || item));
        return true;
      } catch { notify('Unable to check current prices and stock. Please retry.'); return false; }
    };
    if (window.TeraiCatalog) {
      window.TeraiCatalog.addDetail = buy => {
        if (!detail?.available) return notify('This item is currently unavailable.');
        const quantity = Number(document.getElementById('pdp-qty-input')?.value || 1);
        if (!Number.isInteger(quantity) || quantity < 1 || quantity > detail.stock) return notify('Choose a quantity within available stock.');
        window.TeraiCatalog.addToCart({id:detail.id, title:detail.name, price:Number(detail.price), image:detail.image}, quantity);
        if (buy) location.href = '/checkout/';
      };
    }
    document.addEventListener('click', event => {
      if (event.target.closest('#btn-final-pay, #btn-submit-new-card')) {
        event.preventDefault(); event.stopImmediatePropagation();
        notify('Online payment is not configured. No payment has been taken.');
        return;
      }
      const card = event.target.closest('[data-catalog-product]');
      if (!card) return;
      const add = event.target.closest('.add_to_cart_button, .btn-cart-pill');
      const quick = event.target.closest('.quickview-button, .eye-link');
      if (!add && !quick) return;
      event.preventDefault(); event.stopImmediatePropagation();
      const product = window.TeraiCatalog?.getProductById(card.dataset.catalogProduct);
      if (!product) return;
      if (quick) window.TeraiCatalog.openQuickview(product);
      else window.TeraiCatalog.addToCart(product, 1);
    }, true);

    if (grid && initial) {
      // One small accessible control outside the unchanged product grid.
      const more = document.createElement('button');
      more.type = 'button'; more.className = 'btn btn-white';
      more.textContent = 'Load more'; more.setAttribute('aria-label', 'Load more products');
      const status = document.createElement('span'); status.setAttribute('role','status');
      grid.after(more, status);
      const update = () => {
        more.hidden = !info?.has_more && !retry;
        more.disabled = busy;
        more.textContent = retry ? 'Retry loading products' : busy ? 'Loading…' : 'Load more';
        status.textContent = !grid.children.length && !busy ? (retry ? 'Products could not be loaded.' : 'No products found.') : '';
      };
      async function load(reset = false) {
        if (!reset && (busy || (!info?.has_more && !retry))) return;
        if (reset) {
          controller?.abort(); generation++;
          grid.replaceChildren(); info = null;
        }
        const run = generation;
        controller = new AbortController(); busy = true; retry = false; update();
        const params = new URLSearchParams(filters);
        params.delete('cursor');
        if (!reset && info?.next_cursor) params.set('cursor', info.next_cursor);
        try {
          const response = await fetch('/api/products/?' + params, {signal:controller.signal, headers:{Accept:'application/json'}});
          if (response.status === 409) {
            const changed = await response.json();
            if (changed.restart && run === generation) { load(true); return; }
          }
          if (!response.ok) throw new Error('Products could not be loaded.');
          const payload = await response.json();
          if (run !== generation) return;
          const fragment = document.createElement('template'); fragment.innerHTML = payload.html;
          const seen = new Set([...grid.querySelectorAll('[data-catalog-product]')].map(n => n.dataset.catalogProduct));
          for (const child of [...fragment.content.children]) {
            const id = child.dataset.catalogProduct;
            if (id && !seen.has(id)) { grid.append(child); seen.add(id); }
          }
          info = payload;
          document.dispatchEvent(new Event('catalog:updated'));
        } catch (error) {
          if (error.name !== 'AbortError' && run === generation) retry = true;
        } finally {
          if (run === generation) { busy = false; update(); }
        }
      }
      more.addEventListener('click', () => load());
      if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver(entries => {
          if (entries.some(e => e.isIntersecting) && !retry) load();
        }, {rootMargin:'0px 0px 150px 0px'});
        observer.observe(more);
      }
      const sort = document.getElementById('shop-sort-select');
      if (sort) {
        sort.value = filters.get('sort') || sort.value;
        sort.addEventListener('change', () => {
          filters.set('sort', sort.value);
          history.replaceState(null, '', '?' + filters); load(true);
        });
      }
      let timer;
      const search = document.getElementById('shop-header-search-input');
      if (search) {
        search.value = filters.get('q') || '';
        search.addEventListener('input', () => {
          clearTimeout(timer);
          timer = setTimeout(() => {
            filters.set('q', search.value); history.replaceState(null, '', '?' + filters); load(true);
          }, 250);
        });
      }
      // History navigation restores the loaded fragment only briefly; checkout
      // always validates current price/status/stock in the database.
      const stateKey = 'terai:listing:' + location.pathname + location.search;
      try {
        const saved = JSON.parse(sessionStorage.getItem(stateKey) || 'null');
        if (performance.getEntriesByType('navigation')[0]?.type === 'back_forward' && saved && Date.now()-saved.time < 60000) {
          grid.innerHTML = saved.html; info = saved.info;
          document.dispatchEvent(new Event('catalog:updated'));
          requestAnimationFrame(() => scrollTo(0, saved.scroll));
        }
      } catch {}
      addEventListener('pagehide', () => {
        try {sessionStorage.setItem('terai:listing:'+location.pathname+location.search, JSON.stringify({html:grid.innerHTML,info,scroll:scrollY,time:Date.now()}));} catch {}
      });
      update();
    }
    // All existing search boxes query the complete database, not loaded cards.
    document.querySelectorAll('form.search-form').forEach(form => {
      form.action = '/shop/'; form.method = 'get';
      const input = form.querySelector('input[type="search"], input[name="s"]');
      if (input) input.name = 'q';
    });
    // Payment UI is retained, but a demo cannot claim money was authorized.
    document.addEventListener('submit', event => {
      if (event.target.id === 'form-drawer-payment') {
        event.preventDefault(); event.stopImmediatePropagation();
        notify('Online payment is not configured. No payment has been taken.');
      }
    }, true);
  });
})();
