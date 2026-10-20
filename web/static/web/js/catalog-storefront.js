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
    let detail = read('catalog-detail');
    let currentRevision = Number(read('catalog-revision') || 1);
    const notify = message => window.TeraiCatalog?.showToast('Product availability', message, 'warning');

    if (window.TeraiCatalog) window.TeraiCatalog.validateCart = async (cart = window.TeraiCatalog.getCart()) => {
      if (!cart || !cart.length) return true;
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
        window.dispatchEvent(new CustomEvent('delivery:quote', {detail:{items:cart, quote:data}}));
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
          if (!grid.children.length && (filters.get('q') || filters.get('s'))) {
            const qVal = filters.get('q') || filters.get('s');
            const emptyNotice = document.createElement('div');
            emptyNotice.className = 'shop-empty-search-state';
            emptyNotice.innerHTML = `
              <div class="empty-icon"><i class="klb-icon-search"></i></div>
              <h4 class="empty-title">No matching products found</h4>
              <p class="empty-desc">We couldn't find any products matching "<strong>${escape(qVal)}</strong>".<br>Try checking your spelling, using broader keywords, or searching for categories like <em>rice</em>, <em>spices</em>, or <em>tea</em>.</p>
              <button type="button" class="btn btn-outline-primary btn-sm rounded" id="btn-empty-reset-search">Clear Search Filter</button>
            `;
            emptyNotice.querySelector('#btn-empty-reset-search')?.addEventListener('click', () => {
              const clearBtn = document.getElementById('shop-search-clear-btn');
              if (clearBtn) clearBtn.click();
            });
            grid.append(emptyNotice);
          }
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
      const clearBtn = document.getElementById('shop-search-clear-btn');
      const spinner = document.getElementById('shop-search-spinner');
      const statusBar = document.getElementById('shop-search-status-bar');
      const feedbackText = document.getElementById('shop-search-feedback-text');
      const resetLink = document.getElementById('shop-search-reset-link');
      const mobileSearchToggle = document.getElementById('mobile-search-toggle-btn');

      const updateSearchUI = () => {
        const val = search ? search.value.trim() : '';
        if (clearBtn) clearBtn.style.display = val ? 'inline-flex' : 'none';
        if (statusBar) {
          if (val) {
            statusBar.style.display = 'flex';
            if (info && typeof info.total === 'number') {
              feedbackText.innerHTML = `Found <strong>${info.total}</strong> product${info.total === 1 ? '' : 's'} for "<strong>${escape(val)}</strong>"`;
            } else {
              feedbackText.innerHTML = `Searching for "<strong>${escape(val)}</strong>"…`;
            }
          } else {
            statusBar.style.display = 'none';
            if (feedbackText) feedbackText.innerHTML = '';
          }
        }
      };

      if (search) {
        search.value = filters.get('q') || filters.get('s') || '';
        updateSearchUI();

        search.addEventListener('input', () => {
          clearTimeout(timer);
          updateSearchUI();
          if (spinner) spinner.style.display = 'inline-block';
          timer = setTimeout(() => {
            const query = search.value.trim();
            if (query) {
              filters.set('q', query);
              filters.delete('s');
              if (!filters.has('sort') || filters.get('sort') === 'relevance' || filters.get('sort') === 'featured') {
                if (sort) sort.value = 'relevance';
              }
            } else {
              filters.delete('q');
              filters.delete('s');
              if (sort && sort.value === 'relevance') {
                sort.value = 'featured';
                filters.delete('sort');
              }
            }
            history.replaceState(null, '', location.pathname + (filters.toString() ? '?' + filters : ''));
            load(true).finally(() => {
              if (spinner) spinner.style.display = 'none';
              updateSearchUI();
            });
          }, 200);
        });

        const doReset = () => {
          search.value = '';
          filters.delete('q');
          filters.delete('s');
          if (sort && sort.value === 'relevance') {
            sort.value = 'featured';
            filters.delete('sort');
          }
          history.replaceState(null, '', location.pathname + (filters.toString() ? '?' + filters : ''));
          updateSearchUI();
          load(true).finally(() => {
            search.focus();
          });
        };

        if (clearBtn) clearBtn.addEventListener('click', doReset);
        if (resetLink) resetLink.addEventListener('click', doReset);

        const urlParams = new URLSearchParams(location.search);
        if (urlParams.get('focus_search') === 'true' || urlParams.get('focus_search') === '1') {
          setTimeout(() => {
            search.focus();
            search.select();
            search.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }, 60);
          urlParams.delete('focus_search');
          const cleanSearch = urlParams.toString() ? '?' + urlParams : '';
          history.replaceState(null, '', location.pathname + cleanSearch);
        }
      }

      if (mobileSearchToggle) {
        mobileSearchToggle.addEventListener('click', (e) => {
          if (window.location.pathname.includes('/shop')) {
            e.preventDefault();
            if (search) {
              search.focus();
              search.select();
              search.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
          }
        });
      }

      const desktopSearch = document.getElementById('header-search-input');
      if (desktopSearch && search) {
        if (!desktopSearch.value && search.value) {
          desktopSearch.value = search.value;
        }
        desktopSearch.addEventListener('input', () => {
          search.value = desktopSearch.value;
          search.dispatchEvent(new Event('input'));
        });
        const desktopForm = desktopSearch.closest('form');
        if (desktopForm) {
          desktopForm.addEventListener('submit', (e) => {
            e.preventDefault();
            search.value = desktopSearch.value;
            search.dispatchEvent(new Event('input'));
            search.scrollIntoView({ behavior: 'smooth', block: 'center' });
          });
        }
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

    /* --- Real-Time Reflection without Page Refresh --- */
    function updateCard(card, product) {
      if (!card || !product) return false;
      const pId = String(product.id);
      if (String(card.dataset.catalogProduct) !== pId) return false;

      const oldPrice = card.dataset.price;
      const oldRegPrice = card.dataset.regularPrice || '';
      const newRegPrice = product.sale_price ? String(product.regular_price) : '';
      const oldName = card.dataset.name;
      const oldAvail = card.dataset.available;

      let changed = false;

      // Title
      if (oldName !== product.name) {
        card.dataset.name = product.name;
        const titleLink = card.querySelector('.product-title a, .woocommerce-loop-product__title a, h2.product-title a, h2 a');
        if (titleLink && titleLink.textContent !== product.name) {
          titleLink.textContent = product.name;
          if (product.url && titleLink.tagName === 'A') titleLink.href = product.url;
          changed = true;
        }
      }

      // Price
      if (oldPrice !== String(product.price) || oldRegPrice !== newRegPrice) {
        card.dataset.price = product.price;
        card.dataset.regularPrice = newRegPrice;
        changed = true;

        // Shop card prices
        const saleEl = card.querySelector('.sale-price');
        const regEl = card.querySelector('.regular-price, del.regular-price');
        if (saleEl) saleEl.innerHTML = '&pound;' + product.price;
        if (regEl) regEl.innerHTML = newRegPrice ? ('&pound;' + newRegPrice) : '';

        // WooCommerce / Homepage style prices
        const insBdi = card.querySelector('.price ins .woocommerce-Price-amount bdi, .price ins .amount bdi');
        const delBdi = card.querySelector('.price del .woocommerce-Price-amount bdi, .price del .amount bdi');
        if (insBdi) {
          insBdi.innerHTML = '<span class="woocommerce-Price-currencySymbol" translate="no">&pound;</span>' + product.price;
          if (delBdi) {
            delBdi.innerHTML = newRegPrice ? ('<span class="woocommerce-Price-currencySymbol" translate="no">&pound;</span>' + newRegPrice) : '';
          }
        } else {
          const singleBdi = card.querySelector('.price .woocommerce-Price-amount bdi, .price .amount bdi');
          if (singleBdi) {
            singleBdi.innerHTML = '<span class="woocommerce-Price-currencySymbol" translate="no">&pound;</span>' + product.price;
          }
        }
      }

      // Discount badges
      const expectedDiscount = product.discount ? (product.discount + '%') : '';
      const discountPill = card.querySelector('.badge-discount');
      if (discountPill && discountPill.textContent !== expectedDiscount) {
        discountPill.textContent = expectedDiscount;
        discountPill.style.display = expectedDiscount ? '' : 'none';
        changed = true;
      }
      const saleBadge = card.querySelector('.thumbnail-badges .badge.sale, .badge.sale');
      if (saleBadge && saleBadge.textContent !== expectedDiscount) {
        saleBadge.textContent = expectedDiscount;
        saleBadge.style.display = expectedDiscount ? '' : 'none';
        changed = true;
      }

      // Images: ONLY update if src actually differs!
      if (product.image) {
        const img = card.querySelector('.product-thumbnail img, .thumbnail-wrapper img, img.wp-post-image, img');
        if (img && img.getAttribute('src') !== product.image) {
          img.src = product.image;
          changed = true;
        }
        if (product.images && product.images[0]) {
          const avif = card.querySelector('picture source[type="image/avif"]');
          if (avif && avif.getAttribute('srcset') !== product.images[0].avif) {
            avif.srcset = product.images[0].avif;
            changed = true;
          }
          const webp = card.querySelector('picture source[type="image/webp"]');
          if (webp && webp.getAttribute('srcset') !== product.images[0].webp) {
            webp.srcset = product.images[0].webp;
            changed = true;
          }
        }
      }

      // Availability state
      const availStr = product.available ? 'true' : 'false';
      if (oldAvail !== availStr) {
        card.dataset.available = availStr;
        changed = true;
        if (!product.available) {
          card.classList.add('out-of-stock');
          const addBtn = card.querySelector('.add_to_cart_button, .btn-cart-pill');
          if (addBtn) addBtn.setAttribute('aria-disabled', 'true');
        } else {
          card.classList.remove('out-of-stock');
          const addBtn = card.querySelector('.add_to_cart_button, .btn-cart-pill');
          if (addBtn) addBtn.removeAttribute('aria-disabled');
        }
      }

      return changed;
    }

    async function syncProductDetail(slug) {
      try {
        const res = await fetch(`/api/products/${encodeURIComponent(slug)}/?_v=${currentRevision}`, {
          headers: { Accept: 'application/json' },
          cache: 'no-store'
        });
        if (res.status === 404) {
          if (detail) detail.available = false;
          notify('Notice: This product is no longer active or available.');
          document.querySelectorAll('#btn-pdp-add-cart, #btn-pdp-buy-now, .btn-add-cart-detail').forEach(btn => {
            btn.disabled = true;
            btn.classList.add('disabled');
          });
          return;
        }
        if (!res.ok) return;
        const prod = await res.json();
        if (detail) {
          detail.name = prod.name;
          detail.price = prod.price;
          detail.stock = prod.stock;
          detail.available = prod.available;
          detail.image = prod.image;
        }

        // Title and Breadcrumb
        document.querySelectorAll('.pdp-product-title, .single-product-title').forEach(el => {
          if (el.textContent !== prod.name) el.textContent = prod.name;
        });
        document.querySelectorAll('.current').forEach(el => {
          if (el.closest('.breadcrumbs, .woocommerce-breadcrumb, .breadcrumb') && el.textContent !== prod.name) {
            el.textContent = prod.name;
          }
        });

        // Prices
        document.querySelectorAll('.pdp-main-price, .single-product-price .price ins .amount, .single-product-price .price .amount').forEach(el => {
          el.innerHTML = '&pound;' + prod.price;
        });
        const strikeEl = document.querySelector('.pdp-strike-price');
        if (strikeEl) {
          if (prod.sale_price) {
            strikeEl.innerHTML = `<del>&pound;${prod.regular_price}</del> <span class="pdp-discount-pill">-${prod.discount}%</span>`;
          } else {
            strikeEl.innerHTML = '';
          }
        }

        // Image
        const activeImg = document.getElementById('pdp-active-image');
        if (activeImg && prod.image && activeImg.getAttribute('src') !== prod.image) {
          activeImg.src = prod.image;
        }

        // Action buttons
        const actionBtns = document.querySelectorAll('#btn-pdp-add-cart, #btn-pdp-buy-now, .btn-add-cart-detail');
        if (!prod.available) {
          actionBtns.forEach(btn => { btn.disabled = true; btn.classList.add('disabled'); });
        } else {
          actionBtns.forEach(btn => { btn.disabled = false; btn.classList.remove('disabled'); });
        }
      } catch {}
    }

    async function syncCardsOnPage(changedIds = null) {
      const cards = document.querySelectorAll('[data-catalog-product]');
      if (!cards.length) return;
      const allIds = [...new Set([...cards].map(c => c.dataset.catalogProduct).filter(Boolean))];
      if (!allIds.length) return;

      // If specific product IDs were updated, ONLY target those IDs that exist on this page!
      let targetIds = allIds;
      if (Array.isArray(changedIds) && changedIds.length > 0) {
        const changedSet = new Set(changedIds.map(String));
        targetIds = allIds.filter(id => changedSet.has(String(id)));
        if (!targetIds.length) return;
      }

      try {
        let anyCardChanged = false;
        for (let i = 0; i < targetIds.length; i += 50) {
          const chunk = targetIds.slice(i, i + 50);
          const res = await fetch(`/api/products/?ids=${chunk.join(',')}&limit=50&_v=${currentRevision}`, {
            headers: { Accept: 'application/json' },
            cache: 'no-store'
          });
          if (!res.ok) continue;
          const data = await res.json();
          if (Array.isArray(data.products)) {
            const returnedIds = new Set(data.products.map(p => String(p.id)));
            data.products.forEach(prod => {
              document.querySelectorAll(`[data-catalog-product="${prod.id}"]`).forEach(card => {
                if (updateCard(card, prod)) anyCardChanged = true;
              });
            });
            chunk.forEach(id => {
              if (!returnedIds.has(String(id))) {
                document.querySelectorAll(`[data-catalog-product="${id}"]`).forEach(card => {
                  card.classList.add('out-of-stock');
                  card.dataset.available = 'false';
                  const addBtn = card.querySelector('.add_to_cart_button, .btn-cart-pill');
                  if (addBtn) addBtn.setAttribute('aria-disabled', 'true');
                  anyCardChanged = true;
                });
              }
            });
          }
        }
        if (anyCardChanged) {
          document.dispatchEvent(new Event('catalog:updated'));
        }
      } catch {}
    }

    async function syncStorefront(changedIds = null) {
      await syncCardsOnPage(changedIds);
      const pdpSlug = detail?.slug || new URLSearchParams(location.search).get('product');
      if (pdpSlug) {
        if (!changedIds || !detail?.id || changedIds.map(String).includes(String(detail.id))) {
          syncProductDetail(pdpSlug);
        }
      }
      if (window.TeraiCatalog?.getCart()?.length > 0) {
        window.TeraiCatalog.validateCart();
      }
    }

    let isCheckingRevision = false;
    async function checkCatalogRevision() {
      if (isCheckingRevision || document.hidden) return;
      isCheckingRevision = true;
      try {
        const res = await fetch('/api/catalog/revision/', {
          headers: { Accept: 'application/json' },
          cache: 'no-store'
        });
        if (res.ok) {
          const data = await res.json();
          if (typeof data.version === 'number' && data.version > currentRevision) {
            currentRevision = data.version;
            syncStorefront(data.changed_ids);
          }
        }
      } catch {} finally {
        isCheckingRevision = false;
      }
    }

    setInterval(checkCatalogRevision, 12000);
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) checkCatalogRevision();
    });
    window.addEventListener('focus', checkCatalogRevision);

    if (window.TeraiCatalog) {
      window.TeraiCatalog.sync = syncStorefront;
      window.TeraiCatalog.checkRevision = checkCatalogRevision;
    }
  });
})();
