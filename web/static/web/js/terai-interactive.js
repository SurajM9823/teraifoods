/**
 * ============================================================================
 * Terai Food - Comprehensive Interactive Client-side Engine
 * Ensures 100% clickability, real-time cart, checkout sync, quickview,
 * live search, location selector, and responsive animations.
 * ============================================================================
 */
(function () {
  'use strict';

  // --- Constants & Storage Keys ---
  const STORAGE_CART = 'teraifood_cart';
  const STORAGE_WISHLIST = 'teraifood_wishlist';
  const STORAGE_ADDRESS = 'teraifood_uk_address';

  // --- State Helpers ---
  function getCart() {
    try {
      const data = localStorage.getItem(STORAGE_CART);
      return data ? JSON.parse(data) : [];
    } catch (e) {
      return [];
    }
  }

  function saveCart(cart) {
    try {
      localStorage.setItem(STORAGE_CART, JSON.stringify(cart));
    } catch (e) {}
    updateCartUI();
  }

  // --- Default Wishlist Dataset (Matches Initial 4-Count Badge) ---
  const DEFAULT_WISHLIST = [
    {
      id: '756',
      title: "Thomas' Everything Bagels - 20oz_6ct",
      price: 2.50,
      oldPrice: 4.50,
      image: "/static/web/images/1-27-500x500.jpg",
      unit: "20oz / 6ct",
      stock: "In Stock"
    },
    {
      id: '754',
      title: "Take And Bake Baguettes - 14oz_2ct",
      price: 1.75,
      oldPrice: 2.75,
      image: "/static/web/images/1-25-500x500.jpg",
      unit: "14oz / 2ct",
      stock: "In Stock"
    },
    {
      id: '752',
      title: "Wild Forest Raw Organic Honey - 500g",
      price: 7.99,
      oldPrice: 9.50,
      image: "/static/web/images/1-16-500x500.jpg",
      unit: "500g",
      stock: "In Stock"
    },
    {
      id: '750',
      title: "Himalayan Pink Rock Salt (Fine) - 1kg",
      price: 3.25,
      oldPrice: 4.20,
      image: "/static/web/images/1-28-500x500.jpg",
      unit: "1kg",
      stock: "In Stock"
    }
  ];

  function getWishlist() {
    try {
      const data = localStorage.getItem(STORAGE_WISHLIST);
      if (data === null) {
        localStorage.setItem(STORAGE_WISHLIST, JSON.stringify(DEFAULT_WISHLIST));
        return DEFAULT_WISHLIST;
      }
      const parsed = JSON.parse(data);
      if (!Array.isArray(parsed)) return [];
      
      return parsed.map((item, idx) => {
        if (typeof item === 'object' && item !== null) return item;
        const defaultMatch = DEFAULT_WISHLIST.find(d => String(d.id) === String(item));
        return defaultMatch || {
          id: String(item),
          title: `Organic Grocery Special #${idx + 1}`,
          price: 4.99,
          oldPrice: 6.50,
          image: "/static/web/images/1-16-500x500.jpg",
          stock: "In Stock"
        };
      });
    } catch (e) {
      return [];
    }
  }

  function saveWishlist(list) {
    try {
      localStorage.setItem(STORAGE_WISHLIST, JSON.stringify(list));
    } catch (e) {}
    updateWishlistUI();
  }

  // --- Toast Notification System ---
  let toastContainer = null;
  function showToast(title, message, type = 'success') {
    if (!toastContainer) {
      toastContainer = document.createElement('div');
      toastContainer.className = 'terai-toast-container';
      document.body.appendChild(toastContainer);
    }

    const toast = document.createElement('div');
    toast.className = `terai-toast ${type}`;

    let iconHtml = '<i class="klb-icon-check"></i>';
    if (type === 'info') iconHtml = '<i class="klb-icon-heart"></i>';
    if (type === 'warning') iconHtml = '<i class="klb-icon-alert-circle"></i>';

    toast.innerHTML = `
      <div class="terai-toast-icon">${iconHtml}</div>
      <div class="terai-toast-content">
        <div class="terai-toast-title">${title}</div>
        ${message ? `<div class="terai-toast-msg">${message}</div>` : ''}
      </div>
      <button class="terai-toast-close" type="button" aria-label="Close notification">
        <i class="klb-icon-x"></i>
      </button>
    `;

    toast.querySelector('.terai-toast-close').addEventListener('click', () => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 350);
    });

    toastContainer.appendChild(toast);
    requestAnimationFrame(() => {
      toast.classList.add('show');
    });

    setTimeout(() => {
      if (toast.parentNode) {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 350);
      }
    }, 4000);
  }

  // --- Product Catalog Indexing ---
  let catalog = [];
  function indexProducts() {
    catalog = [];
    const productNodes = document.querySelectorAll('.product, .shop-product-card');

    productNodes.forEach((node, index) => {
      const id = node.querySelector('[data-product_id]')?.getAttribute('data-product_id') ||
                 node.className.match(/post-(\d+)/)?.[1] ||
                 `p-${index + 1}`;

      const titleEl = node.querySelector('.product-title a') || node.querySelector('.product-title');
      const title = titleEl ? titleEl.textContent.trim() : `Fresh Organic Grocery #${index + 1}`;

      const imgEl = node.querySelector('.wp-post-image') || node.querySelector('img');
      const image = imgEl ? (imgEl.getAttribute('src') || '') : '/static/web/images/1-16-500x500.jpg';

      // Price extraction
      let price = 5.99;
      let oldPrice = null;
      const priceIns = node.querySelector('.price ins .woocommerce-Price-amount, .sale-price');
      const priceDel = node.querySelector('.price del .woocommerce-Price-amount, .regular-price');
      const priceRegular = node.querySelector('.price .woocommerce-Price-amount');

      if (priceIns) {
        const text = priceIns.textContent.replace(/[^0-9.]/g, '');
        if (text) price = parseFloat(text);
      } else if (priceRegular) {
        const text = priceRegular.textContent.replace(/[^0-9.]/g, '');
        if (text) price = parseFloat(text);
      }

      if (priceDel) {
        const text = priceDel.textContent.replace(/[^0-9.]/g, '');
        if (text) oldPrice = parseFloat(text);
      }

      const ratingEl = node.querySelector('.star-rating strong');
      const rating = ratingEl ? ratingEl.textContent.trim() : '4.8';

      const stockEl = node.querySelector('.product-progress-detail span');
      const stock = stockEl ? stockEl.textContent.trim() : 'In Stock';

      catalog.push({
        id: String(id),
        title,
        price,
        oldPrice,
        image,
        rating,
        stock,
        element: node
      });
    });
  }

  function getProductById(id) {
    return catalog.find(p => String(p.id) === String(id));
  }

  // --- Cart Calculations & UI Sync ---
  function updateCartUI() {
    const cart = getCart();
    const totalCount = cart.reduce((sum, item) => sum + item.quantity, 0);
    const subtotal = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);

    // 1. Update Cart Count Badges
    document.querySelectorAll('.cart-count, .mini-cart-count, .count, .cart-button .badge').forEach(el => {
      el.textContent = totalCount;
    });

    // 2. Update Header Subtotal Text
    document.querySelectorAll('.cart-total, .cart-subtotal, .mini-cart-total, .cart-price').forEach(el => {
      el.textContent = '£' + subtotal.toFixed(2);
    });

    // 3. Render Drawer Items
    renderDrawerCart();
  }

  function renderSideCart(cart, subtotal) {
    renderDrawerCart();
  }

  let cartPillTimer = null;
  function highlightHeaderCart(item, qty) {
    const cartButtons = document.querySelectorAll('.mini-cart-button, .header-cart, .cart-button');
    const badges = document.querySelectorAll('.cart-count, .mini-cart-count, .count, .cart-button .badge');

    // 1. Elastic bounce on cart count badges
    badges.forEach(b => {
      b.classList.remove('cart-badge-bounce');
      void b.offsetWidth;
      b.classList.add('cart-badge-bounce');
    });

    // 2. Radiating ring pulse on cart icon
    document.querySelectorAll('.mini-cart-button .action-icon, .header-cart .action-icon, .header-cart i, .mini-cart-button i').forEach(icon => {
      icon.classList.remove('cart-icon-pulse');
      void icon.offsetWidth;
      icon.classList.add('cart-icon-pulse');
    });

    // 3. Expandable sleek mini floating pill docked directly under the header cart
    cartButtons.forEach(btn => {
      let pill = btn.querySelector('.header-cart-expandable-pill');
      if (!pill) {
        pill = document.createElement('div');
        pill.className = 'header-cart-expandable-pill';
        btn.appendChild(pill);
        pill.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          openSideCart(1);
        });
      }

      const itemTitle = (item && item.title) ? item.title : 'Item';
      pill.innerHTML = `
        <span class="pill-badge">✓ +${qty}</span>
        <span class="pill-text" title="${itemTitle}">${itemTitle}</span>
        <span class="pill-action">Cart &rarr;</span>
      `;

      pill.classList.remove('show');
      void pill.offsetWidth;
      pill.classList.add('show');
    });

    if (cartPillTimer) clearTimeout(cartPillTimer);
    cartPillTimer = setTimeout(() => {
      document.querySelectorAll('.header-cart-expandable-pill').forEach(pill => {
        pill.classList.remove('show');
      });
    }, 2500);
  }

  function addToCart(item, qty = 1) {
    const cart = getCart();
    const existing = cart.find(i => String(i.id) === String(item.id));

    if (existing) {
      existing.quantity += qty;
    } else {
      cart.push({
        id: String(item.id),
        title: item.title,
        price: item.price,
        image: item.image,
        quantity: qty
      });
    }

    saveCart(cart);
    showToast('Added to Basket!', `✓ ${item.title} (${qty}x) added to your order.`, 'success');
    highlightHeaderCart(item, qty);
  }

  function changeCartItemQty(id, delta) {
    let cart = getCart();
    const existing = cart.find(i => String(i.id) === String(id));
    if (existing) {
      existing.quantity += delta;
      if (existing.quantity <= 0) {
        cart = cart.filter(i => String(i.id) !== String(id));
        showToast('Item Removed', `${existing.title} removed from basket.`, 'info');
      }
      saveCart(cart);
    }
  }

  function removeCartItem(id) {
    let cart = getCart();
    const item = cart.find(i => String(i.id) === String(id));
    cart = cart.filter(i => String(i.id) !== String(id));
    saveCart(cart);
    if (item) {
      showToast('Item Removed', `${item.title} removed from basket.`, 'info');
    }
  }

  // --- Side Cart Drawer Open / Close (70% Screen Width Right Drawer) ---
  function openSideCart(step = 1) {
    if (!sideCartDrawer) initSideCartDrawer();
    closeWishlistDrawer();
    goToDrawerStep(step);
    document.querySelectorAll('.cart-widget-side, #cart-widget-side').forEach(el => {
      el.classList.add('open');
    });
    document.querySelectorAll('.cart-side-overlay, #cart-side-overlay').forEach(el => {
      el.classList.add('open');
    });
    document.body.classList.add('cart-widget-side-active');
  }

  function closeSideCart() {
    document.querySelectorAll('.cart-widget-side, #cart-widget-side').forEach(el => {
      el.classList.remove('open');
      el.style.transform = '';
    });
    document.querySelectorAll('.cart-side-overlay, #cart-side-overlay').forEach(el => {
      el.classList.remove('open');
      el.style.opacity = '';
      el.style.visibility = '';
    });
    document.body.classList.remove('cart-widget-side-active');
  }
  window.teraiCloseCart = closeSideCart;

  // --- Wishlist Sidebar Drawer System (Expanded Width: 440px) ---
  let wishlistDrawer = null;
  let wishlistOverlay = null;

  function initWishlistDrawer() {
    if (document.getElementById('wishlist-widget-side')) {
      wishlistDrawer = document.getElementById('wishlist-widget-side');
      wishlistOverlay = document.getElementById('wishlist-side-overlay');
      return;
    }

    wishlistOverlay = document.createElement('div');
    wishlistOverlay.id = 'wishlist-side-overlay';
    wishlistOverlay.className = 'wishlist-side-overlay';

    wishlistDrawer = document.createElement('div');
    wishlistDrawer.id = 'wishlist-widget-side';
    wishlistDrawer.className = 'wishlist-widget-side';
    wishlistDrawer.setAttribute('role', 'dialog');
    wishlistDrawer.setAttribute('aria-modal', 'true');
    wishlistDrawer.setAttribute('aria-label', 'Wishlist Drawer');

    wishlistDrawer.innerHTML = `
      <div class="wishlist-side-header">
        <div class="wishlist-side-title-wrap">
          <h4 class="wishlist-side-title"><i class="klb-icon-heart-4"></i> My Saved Wishlist</h4>
          <span class="wishlist-badge-count" id="wishlist-drawer-badge">0 items</span>
        </div>
        <button type="button" class="wishlist-side-close" id="wishlist-drawer-close" aria-label="Close Wishlist">
          <i class="klb-icon-x"></i>
        </button>
      </div>
      <div class="wishlist-side-body" id="wishlist-drawer-body">
        <!-- Wishlist items or empty state rendered dynamically -->
      </div>
      <div class="wishlist-side-footer" id="wishlist-drawer-footer" style="display: none;">
        <button type="button" class="wishlist-btn-add-all" id="btn-wishlist-add-all">
          <i class="klb-icon-shopping-cart-3"></i> Add All to Basket
        </button>
        <a href="/shop/" class="wishlist-btn-view-shop" id="btn-wishlist-view-shop">
          Continue Shopping &bull; View All Groceries
        </a>
      </div>
    `;

    document.body.appendChild(wishlistOverlay);
    document.body.appendChild(wishlistDrawer);

    // Event listeners
    wishlistOverlay.addEventListener('click', closeWishlistDrawer);
    wishlistDrawer.querySelector('#wishlist-drawer-close')?.addEventListener('click', closeWishlistDrawer);

    wishlistDrawer.querySelector('#btn-wishlist-add-all')?.addEventListener('click', () => {
      addAllWishlistToCart();
    });

    wishlistDrawer.querySelector('#btn-wishlist-view-shop')?.addEventListener('click', () => {
      closeWishlistDrawer();
    });

    renderWishlistDrawer();
  }

  function openWishlistDrawer() {
    if (!wishlistDrawer || !document.getElementById('wishlist-widget-side')) {
      initWishlistDrawer();
    }

    renderWishlistDrawer();
    closeSideCart(); // Close cart drawer if open

    if (wishlistDrawer) wishlistDrawer.classList.add('open');
    if (wishlistOverlay) wishlistOverlay.classList.add('open');
    document.body.classList.add('wishlist-side-active');
  }

  function closeWishlistDrawer() {
    if (wishlistDrawer) wishlistDrawer.classList.remove('open');
    if (wishlistOverlay) wishlistOverlay.classList.remove('open');
    document.body.classList.remove('wishlist-side-active');
  }

  function renderWishlistDrawer() {
    const body = document.getElementById('wishlist-drawer-body');
    const footer = document.getElementById('wishlist-drawer-footer');
    const badge = document.getElementById('wishlist-drawer-badge');
    if (!body) return;

    const list = getWishlist();
    if (badge) {
      badge.textContent = `${list.length} item${list.length === 1 ? '' : 's'}`;
    }

    if (list.length === 0) {
      if (footer) footer.style.display = 'none';
      body.innerHTML = `
        <div class="wishlist-empty-state">
          <div class="wishlist-empty-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="46" height="46" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
              <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
            </svg>
          </div>
          <h4 class="wishlist-empty-title">Your Wishlist is Empty</h4>
          <p class="wishlist-empty-desc">You haven't saved any items to your wishlist yet. Discover authentic Himalayan and organic groceries in our shop!</p>
          <a href="/shop/" class="wishlist-empty-shop-btn" id="btn-wishlist-empty-shop">
            <i class="klb-icon-shopping-cart-3"></i> Start Shopping &bull; Explore Shop
          </a>
        </div>
      `;

      body.querySelector('#btn-wishlist-empty-shop')?.addEventListener('click', () => {
        closeWishlistDrawer();
      });
      return;
    }

    if (footer) footer.style.display = 'flex';

    let cardsHtml = `
      <div class="wishlist-side-toolbar">
        <span>Saved Products (${list.length})</span>
        <button type="button" class="wishlist-side-clear-btn" id="btn-wishlist-clear-all">Clear All</button>
      </div>
    `;

    cardsHtml += list.map(item => `
      <div class="wishlist-card-item" data-id="${item.id}">
        <div class="wishlist-card-img-wrap">
          <img src="${item.image || '/static/web/images/1-16-500x500.jpg'}" alt="${item.title}" class="wishlist-card-img">
        </div>
        <div class="wishlist-card-info">
          <div class="wishlist-card-top-row">
            <h5 class="wishlist-card-title">
              <a href="/product-detail/" title="${item.title}">${item.title}</a>
            </h5>
            <button type="button" class="wishlist-btn-remove" data-id="${item.id}" title="Remove from wishlist">
              <i class="klb-icon-x"></i>
            </button>
          </div>
          <div class="wishlist-card-bottom-row">
            <div class="wishlist-card-price-wrap">
              <span class="wishlist-card-price">£${Number(item.price || 0).toFixed(2)}</span>
              ${item.oldPrice ? `<del class="wishlist-card-old-price">£${Number(item.oldPrice).toFixed(2)}</del>` : ''}
              ${item.unit ? `<span class="wishlist-card-unit">&bull; ${item.unit}</span>` : ''}
            </div>
            <button type="button" class="wishlist-btn-add-cart" data-id="${item.id}">
              <i class="klb-icon-shopping-cart-3"></i> Add
            </button>
          </div>
        </div>
      </div>
    `).join('');

    body.innerHTML = cardsHtml;

    // Attach listeners
    body.querySelectorAll('.wishlist-btn-add-cart').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = btn.getAttribute('data-id');
        addWishlistItemToCart(id);
      });
    });

    body.querySelectorAll('.wishlist-btn-remove').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = btn.getAttribute('data-id');
        removeFromWishlist(id);
      });
    });

    body.querySelector('#btn-wishlist-clear-all')?.addEventListener('click', (e) => {
      e.stopPropagation();
      clearWishlist();
    });
  }

  function removeFromWishlist(id) {
    let list = getWishlist();
    const item = list.find(i => String(i.id) === String(id));
    list = list.filter(i => String(i.id) !== String(id));
    saveWishlist(list);
    showToast('Removed from Wishlist', `${item ? item.title : 'Item'} removed from wishlist.`, 'info');
  }

  function clearWishlist() {
    saveWishlist([]);
    showToast('Wishlist Cleared', 'All items have been removed from your wishlist.', 'info');
  }

  function addWishlistItemToCart(id) {
    const list = getWishlist();
    const item = list.find(i => String(i.id) === String(id));
    if (item) {
      addToCart({
        id: item.id,
        title: item.title,
        price: Number(item.price),
        image: item.image
      }, 1);
    }
  }

  function addAllWishlistToCart() {
    const list = getWishlist();
    if (list.length === 0) return;

    list.forEach(item => {
      addToCart({
        id: item.id,
        title: item.title,
        price: item.price,
        image: item.image
      }, 1);
    });

    showToast('All Items Added!', '✓ Added wishlist items to your basket.', 'success');
  }

  // --- Terai Food - 70% Width Right-Side Shopping & Checkout Drawer ---
  // Flow: Step 1: Clean Basket -> Step 2: Daraz-Style Checkout -> Step 3: Payment -> Step 4: Success
  let sideCartDrawer = null;
  let sideCartOverlay = null;
  let currentDrawerStep = 1;
  let selectedShippingMethod = 'standard';
  let selectedPaymentMethod = 'card';
  let appliedVoucherCode = '';
  let voucherDiscountPercent = 0;
  let unselectedItemIds = new Set();
  let lastOrderDetails = null;

  const DEFAULT_DARAZ_ADDRESS = {
    name: 'Suraj Mahato',
    phone: '9805996874',
    tag: 'OFFICE',
    address: 'Dhunge Sadhu Chowck, Lalitpur - Imadole Area, Lalitpur Outside Ring Road, Bagmati Province',
    note: 'Aakrati Advertisment'
  };

  function getSavedAddress() {
    try {
      const data = JSON.parse(localStorage.getItem(STORAGE_ADDRESS));
      if (data && data.name) return Object.assign({}, DEFAULT_DARAZ_ADDRESS, data);
    } catch (e) {}
    return DEFAULT_DARAZ_ADDRESS;
  }

  function initSideCartDrawer() {
    // Remove any legacy centered modal if found in DOM
    document.getElementById('terai-commerce-modal')?.remove();
    document.getElementById('terai-commerce-overlay')?.remove();

    if (document.getElementById('cart-widget-side') && document.getElementById('cart-widget-side').querySelector('#drawer-pane-1')) {
      sideCartDrawer = document.getElementById('cart-widget-side');
      sideCartOverlay = document.querySelector('.cart-side-overlay') || document.getElementById('cart-side-overlay');
      return;
    }

    // Overlay
    let existingOverlay = document.querySelector('.cart-side-overlay');
    if (existingOverlay) {
      sideCartOverlay = existingOverlay;
    } else {
      sideCartOverlay = document.createElement('div');
      sideCartOverlay.className = 'cart-side-overlay';
      document.body.appendChild(sideCartOverlay);
    }

    // Drawer container
    let existingDrawer = document.querySelector('.cart-widget-side');
    if (existingDrawer) {
      sideCartDrawer = existingDrawer;
    } else {
      sideCartDrawer = document.createElement('div');
      sideCartDrawer.className = 'cart-widget-side';
      document.body.appendChild(sideCartDrawer);
    }

    sideCartDrawer.id = 'cart-widget-side';
    sideCartDrawer.setAttribute('role', 'dialog');
    sideCartDrawer.setAttribute('aria-modal', 'true');
    sideCartDrawer.setAttribute('aria-label', 'Shopping Cart and Checkout Drawer');

    const addr = getSavedAddress();

    sideCartDrawer.innerHTML = `
      <!-- Drawer Header - Clean Minimalist (No Stepper 1-4) -->
      <div class="cart-side-header-enhanced">
        <h3 class="cart-side-main-title" id="drawer-step-title">Shopping Cart</h3>
        <button type="button" class="cart-side-close cart-side-close-btn" id="drawer-close-btn" onclick="window.teraiCloseCart && window.teraiCloseCart()" aria-label="Close cart">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
      </div>

      <!-- Drawer Content Body Scroll Area -->
      <div class="cart-drawer-content-body">
        <!-- STEP 1 PANE: BASKET (cart.html 2-column layout, Clean & Minimal) -->
        <div class="cart-drawer-step-pane active" id="drawer-pane-1">
          <div class="cart-drawer-2col">
            <!-- Left Column: Select All & Items List -->
            <div class="cart-drawer-left-col">
              <div class="cart-drawer-top-bar" id="drawer-top-bar">
                <label class="cart-drawer-select-all">
                  <span class="cart-custom-checkbox">
                    <input type="checkbox" id="drawer-select-all" checked>
                    <span class="cart-checkbox-box"></span>
                  </span>
                  <span id="drawer-select-all-text">SELECT ALL (0 ITEMS)</span>
                </label>
                <button type="button" class="cart-drawer-btn-clear" id="btn-drawer-clear-selected">
                  <i class="klb-icon-trash"></i> Delete Selected
                </button>
              </div>

              <div class="cart-drawer-vendor-card" id="drawer-vendor-card">
                <div class="cart-drawer-vendor-header">
                  <i class="klb-icon-shop"></i>
                  <span>Terai Food Store &ndash; Direct Farm Fresh</span>
                </div>
                <div id="drawer-cart-items-container"></div>
              </div>
            </div>

            <!-- Right Column: Clean Order Summary Card (No Bullets, No Location Pill) -->
            <div class="cart-drawer-right-col" id="drawer-step1-summary-col">
              <div class="cart-drawer-summary-card">
                <div class="cart-drawer-summary-title">Order Summary</div>
                <div class="cart-drawer-voucher-group">
                  <input type="text" class="cart-drawer-voucher-input" id="drawer-voucher-input" placeholder="Enter Store/Daraz Code">
                  <button type="button" class="cart-drawer-voucher-btn" id="btn-drawer-apply-voucher">APPLY</button>
                </div>
                <div id="drawer-voucher-feedback" style="font-size: 11px; margin-top: -6px; margin-bottom: 8px; display: none;"></div>

                <div class="cart-drawer-summary-row">
                  <span>Items Total (<span id="drawer-items-count-label">0 Items</span>)</span>
                  <span class="cart-drawer-summary-row-val" id="drawer-subtotal-val">£0.00</span>
                </div>
                <div class="cart-drawer-summary-row" id="drawer-discount-row" style="display: none; color: #16a34a;">
                  <span>Store Discount</span>
                  <span class="cart-drawer-summary-row-val" id="drawer-discount-val">-£0.00</span>
                </div>
                <div class="cart-drawer-summary-row">
                  <span>Delivery Fee</span>
                  <span class="cart-drawer-summary-row-val" id="drawer-shipping-val">£3.99</span>
                </div>
                <div class="cart-drawer-summary-total-row">
                  <span class="cart-drawer-summary-total-label">Total:</span>
                  <div style="text-align: right;">
                    <div class="cart-drawer-summary-total-amount" id="drawer-total-val">£0.00</div>
                    <div class="checkout-summary-taxes-sub">All taxes included</div>
                  </div>
                </div>
                <button type="button" class="cart-drawer-btn-checkout" id="btn-drawer-proceed-checkout">
                  Proceed to Checkout
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- STEP 2 PANE: DARAZ-STYLE CHECKOUT SCREEN (Matching User Screenshot) -->
        <div class="cart-drawer-step-pane" id="drawer-pane-2">
          <div class="cart-drawer-2col">
            <!-- Left Column: Shipping Address & Package 1 of 1 -->
            <div class="cart-drawer-left-col">
              <!-- Shipping Address Card -->
              <div class="checkout-card" id="checkout-shipping-address-card">
                <div class="checkout-card-header">
                  <span class="checkout-card-title">Shipping Address</span>
                  <a href="javascript:void(0)" class="checkout-card-link" id="btn-edit-shipping-address">EDIT</a>
                </div>
                
                <!-- Display View -->
                <div id="checkout-address-display-view">
                  <div class="checkout-addr-name-row">
                    <span id="disp-cust-name">${addr.name}</span>
                    <span id="disp-cust-phone" style="font-weight: 500; color: #475569;">${addr.phone}</span>
                  </div>
                  <div class="checkout-addr-detail-row">
                    <span class="checkout-addr-badge" id="disp-cust-tag">${addr.tag || 'OFFICE'}</span>
                    <span id="disp-cust-address">${addr.address}</span>
                  </div>
                  <div class="checkout-addr-note" id="disp-cust-note">${addr.note}</div>
                </div>

                <!-- Inline Edit Form (Hidden by default) -->
                <div id="checkout-address-edit-view" style="display: none; margin-top: 12px; border-top: 1px solid #f1f5f9; padding-top: 12px;">
                  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 8px;">
                    <div>
                      <label style="font-size: 10.5px; font-weight: 700; color: #475569; display: block; margin-bottom: 2px;">Full Name *</label>
                      <input type="text" id="edit-cust-name" class="cart-drawer-form-input" value="${addr.name}">
                    </div>
                    <div>
                      <label style="font-size: 10.5px; font-weight: 700; color: #475569; display: block; margin-bottom: 2px;">Phone Number *</label>
                      <input type="text" id="edit-cust-phone" class="cart-drawer-form-input" value="${addr.phone}">
                    </div>
                  </div>
                  <div style="margin-bottom: 8px;">
                    <label style="font-size: 10.5px; font-weight: 700; color: #475569; display: block; margin-bottom: 3px;">Address Tag</label>
                    <div style="display: flex; gap: 8px;">
                      <button type="button" class="btn-tag-select ${addr.tag === 'OFFICE' ? 'active' : ''}" data-tag="OFFICE">OFFICE</button>
                      <button type="button" class="btn-tag-select ${addr.tag === 'HOME' ? 'active' : ''}" data-tag="HOME">HOME</button>
                    </div>
                  </div>
                  <div style="margin-bottom: 8px;">
                    <label style="font-size: 10.5px; font-weight: 700; color: #475569; display: block; margin-bottom: 2px;">Delivery Address *</label>
                    <input type="text" id="edit-cust-address" class="cart-drawer-form-input" value="${addr.address}">
                  </div>
                  <div style="margin-bottom: 8px;">
                    <label style="font-size: 10.5px; font-weight: 700; color: #475569; display: block; margin-bottom: 2px;">Landmark / Note</label>
                    <input type="text" id="edit-cust-note" class="cart-drawer-form-input" value="${addr.note}">
                  </div>
                  <div style="display: flex; gap: 8px; margin-top: 10px;">
                    <button type="button" class="checkout-save-addr-btn" id="btn-save-address">Save Address</button>
                    <button type="button" class="checkout-cancel-addr-btn" id="btn-cancel-address">Cancel</button>
                  </div>
                </div>
              </div>

              <!-- Package 1 of 1 Card -->
              <div class="checkout-card" id="checkout-package-card">
                <div class="checkout-pkg-header">
                  <span class="checkout-card-title">Package 1 of 1</span>
                  <span class="checkout-pkg-vendor">Shipped by <strong>SIM-EDWIN</strong></span>
                </div>
                <div class="checkout-delivery-label">Delivery or Pickup</div>

                <!-- Delivery Option Box -->
                <div class="checkout-delivery-tile selected" id="checkout-delivery-tile-box">
                  <div class="checkout-delivery-tile-top">
                    <span class="checkout-delivery-check">
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
                    </span>
                    <span id="checkout-delivery-price-text">£3.99</span>
                  </div>
                  <div class="checkout-delivery-method">Standard Delivery</div>
                  <div class="checkout-delivery-eta" id="checkout-delivery-eta-text">Guaranteed by 25 Oct</div>
                </div>

                <!-- Package Items List -->
                <div class="checkout-pkg-items-list" id="checkout-pkg-items-container">
                  <!-- Populated dynamically -->
                </div>
              </div>
            </div>

            <!-- Right Column: Promotion, Invoice Info & Order Detail -->
            <div class="cart-drawer-right-col">
              <!-- Promotion Card -->
              <div class="checkout-promo-card">
                <div class="checkout-promo-title">Promotion</div>
                <div class="checkout-promo-input-group">
                  <input type="text" class="checkout-promo-input" id="checkout-promo-input" placeholder="Enter Store/Daraz Code">
                  <button type="button" class="checkout-promo-btn" id="btn-checkout-apply-promo">APPLY</button>
                </div>
                <div id="checkout-promo-feedback" style="font-size: 11px; margin-top: 6px; display: none;"></div>
              </div>

              <!-- Invoice and Contact Info Card -->
              <div class="checkout-invoice-card">
                <span style="font-size: 13px; font-weight: 700; color: #0f172a;">Invoice and Contact Info</span>
                <a href="javascript:void(0)" class="checkout-card-link" id="btn-edit-invoice-info">Edit</a>
              </div>

              <!-- Order Detail Card -->
              <div class="checkout-order-detail-card">
                <div class="checkout-order-detail-title">Order Detail</div>
                <div class="checkout-summary-line">
                  <span>Items Total (<span id="checkout-summary-items-count">1 Items</span>)</span>
                  <span class="checkout-summary-line-val" id="checkout-summary-items-total">£0.00</span>
                </div>
                <div class="checkout-summary-line" id="checkout-summary-discount-row" style="display: none; color: #16a34a;">
                  <span>Store Discount</span>
                  <span class="checkout-summary-line-val" id="checkout-summary-discount-val" style="color: #16a34a;">-£0.00</span>
                </div>
                <div class="checkout-summary-line">
                  <span>Delivery Fee</span>
                  <span class="checkout-summary-line-val" id="checkout-summary-delivery-fee">£3.99</span>
                </div>
                <div class="checkout-summary-total-wrap">
                  <span class="checkout-summary-total-label">Total:</span>
                  <div class="checkout-summary-total-right">
                    <div class="checkout-summary-total-amt" id="checkout-summary-grand-total">£0.00</div>
                    <div class="checkout-summary-taxes-sub">All taxes included</div>
                  </div>
                </div>
                <button type="button" class="checkout-btn-proceed-pay" id="btn-proceed-to-pay">
                  Proceed to Pay
                </button>
                <button type="button" class="cart-drawer-btn-secondary" id="btn-checkout-back-to-cart" style="margin-top: 10px; width: 100%;">
                  &larr; Back to Basket
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- STEP 3 PANE: PAYMENT METHOD -->
        <div class="cart-drawer-step-pane" id="drawer-pane-3">
          <form id="form-drawer-payment">
            <div class="cart-drawer-2col">
              <!-- Left: Selectable Payment Methods -->
              <div class="cart-drawer-left-col">
                <div class="cart-drawer-payment-tiles">
                  <!-- Method 1: Credit / Debit Card -->
                  <div class="cart-drawer-payment-tile selected" data-payment="card">
                    <div class="cart-drawer-payment-tile-header">
                      <div class="cart-drawer-payment-tile-left">
                        <input type="radio" name="drawer_payment" value="card" checked id="drawer-pay-card" class="payment-tile-radio">
                        <label for="drawer-pay-card" style="margin: 0; cursor: pointer;">Credit or Debit Card</label>
                      </div>
                      <span style="font-size: 11px; font-weight: 700; color: #1547A8;">Visa / Mastercard / Amex</span>
                    </div>
                    <div class="cart-drawer-payment-tile-body" id="drawer-card-box">
                      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 10px; margin-top: 6px; border: 1px solid #e2e8f0; background: #fafafa;">
                        <div style="grid-column: 1 / -1;">
                          <label style="font-size: 10.5px; font-weight: 700; color: #475569; display: block; margin-bottom: 2px;">Card Number</label>
                          <input type="text" class="cart-drawer-form-input" id="drawer-card-num" value="4532 8920 1284 9912" placeholder="4xxx xxxx xxxx xxxx">
                        </div>
                        <div>
                          <label style="font-size: 10.5px; font-weight: 700; color: #475569; display: block; margin-bottom: 2px;">Expiry (MM/YY)</label>
                          <input type="text" class="cart-drawer-form-input" id="drawer-card-exp" value="08/28" placeholder="MM/YY">
                        </div>
                        <div>
                          <label style="font-size: 10.5px; font-weight: 700; color: #475569; display: block; margin-bottom: 2px;">Security CVC</label>
                          <input type="text" class="cart-drawer-form-input" id="drawer-card-cvc" value="382" placeholder="CVC">
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- Method 2: PayPal -->
                  <div class="cart-drawer-payment-tile" data-payment="paypal">
                    <div class="cart-drawer-payment-tile-header">
                      <div class="cart-drawer-payment-tile-left">
                        <input type="radio" name="drawer_payment" value="paypal" id="drawer-pay-paypal" class="payment-tile-radio">
                        <label for="drawer-pay-paypal" style="margin: 0; cursor: pointer;">PayPal Express</label>
                      </div>
                      <span style="font-size: 11px; font-weight: 700; color: #0070ba;">PayPal</span>
                    </div>
                    <div class="cart-drawer-payment-tile-body">
                      Instant 1-click checkout with PayPal Buyer Protection.
                    </div>
                  </div>

                  <!-- Method 3: UK Bank Transfer -->
                  <div class="cart-drawer-payment-tile" data-payment="bacs">
                    <div class="cart-drawer-payment-tile-header">
                      <div class="cart-drawer-payment-tile-left">
                        <input type="radio" name="drawer_payment" value="bacs" id="drawer-pay-bacs" class="payment-tile-radio">
                        <label for="drawer-pay-bacs" style="margin: 0; cursor: pointer;">UK Bank Transfer (Faster Payments)</label>
                      </div>
                      <span style="font-size: 10px; font-weight: 700; color: #059669; background: #ecfdf5; padding: 1px 4px;">Zero Fees</span>
                    </div>
                    <div class="cart-drawer-payment-tile-body">
                      Sort Code: 20-00-00 | Account: 83920194 | Payee: Terai Food UK.
                    </div>
                  </div>

                  <!-- Method 4: Cash on Delivery -->
                  <div class="cart-drawer-payment-tile" data-payment="cod">
                    <div class="cart-drawer-payment-tile-header">
                      <div class="cart-drawer-payment-tile-left">
                        <input type="radio" name="drawer_payment" value="cod" id="drawer-pay-cod" class="payment-tile-radio">
                        <label for="drawer-pay-cod" style="margin: 0; cursor: pointer;">Cash / Card on Delivery</label>
                      </div>
                      <span style="font-size: 11px; font-weight: 700; color: #64748b;">Chilled Van</span>
                    </div>
                    <div class="cart-drawer-payment-tile-body">
                      Pay safely by cash or contactless terminal upon arrival.
                    </div>
                  </div>
                </div>
              </div>

              <!-- Right: Payment Review Summary Card -->
              <div class="cart-drawer-right-col">
                <div class="checkout-order-detail-card">
                  <div class="checkout-order-detail-title">Payment Summary</div>
                  <div class="checkout-summary-line">
                    <span>Delivery Fee:</span>
                    <span class="checkout-summary-line-val" id="drawer-step3-shipping">£3.99</span>
                  </div>
                  <div class="checkout-summary-total-wrap">
                    <span class="checkout-summary-total-label">Total to Pay:</span>
                    <div class="checkout-summary-total-right">
                      <div class="checkout-summary-total-amt" id="drawer-step3-total">£0.00</div>
                      <div class="checkout-summary-taxes-sub">All taxes included</div>
                    </div>
                  </div>
                  <button type="submit" class="checkout-btn-proceed-pay" id="btn-drawer-confirm-pay">
                    Confirm &amp; Place Order
                  </button>
                  <button type="button" class="cart-drawer-btn-secondary" id="btn-drawer-back-to-2" style="margin-top: 10px; width: 100%;">
                    &larr; Back to Checkout
                  </button>
                </div>
              </div>
            </div>
          </form>
        </div>

        <!-- STEP 4 PANE: CONFIRMATION / RECEIPT -->
        <div class="cart-drawer-step-pane" id="drawer-pane-4">
          <div class="cart-drawer-confirm-box" id="drawer-confirm-content">
            <!-- Dynamic Receipt populated on submit -->
          </div>
        </div>
      </div>
    `;

    // Global and element close bindings
    sideCartOverlay.addEventListener('click', closeSideCart);
    sideCartDrawer.querySelector('#drawer-close-btn')?.addEventListener('click', closeSideCart);

    // Step 1: Select All Checkbox
    sideCartDrawer.querySelector('#drawer-select-all')?.addEventListener('change', (e) => {
      const isChecked = e.target.checked;
      const cart = getCart();
      if (isChecked) {
        unselectedItemIds.clear();
      } else {
        cart.forEach(item => unselectedItemIds.add(String(item.id)));
      }
      renderDrawerCart();
    });

    // Step 1: Clear Selected Button
    sideCartDrawer.querySelector('#btn-drawer-clear-selected')?.addEventListener('click', () => {
      let cart = getCart();
      const initialLen = cart.length;
      cart = cart.filter(item => unselectedItemIds.has(String(item.id)));
      saveCart(cart);
      unselectedItemIds.clear();
      showToast('Items Removed', `Removed ${initialLen - cart.length} items from basket.`, 'info');
      renderDrawerCart();
    });

    // Step 1 & Step 2: Voucher Apply
    const applyVoucherLogic = (inputId, feedbackId) => {
      const input = sideCartDrawer.querySelector(inputId);
      const feedback = sideCartDrawer.querySelector(feedbackId);
      const code = input ? input.value.trim().toUpperCase() : '';

      if (!code) {
        if (feedback) {
          feedback.style.display = 'block';
          feedback.style.color = '#ef4444';
          feedback.textContent = 'Please enter a voucher code.';
        }
        return;
      }

      if (code === 'TERAI10' || code === 'DARAZ10' || code === 'DISCOUNT10' || code === 'SAVE10') {
        appliedVoucherCode = code;
        voucherDiscountPercent = 10;
        if (feedback) {
          feedback.style.display = 'block';
          feedback.style.color = '#16a34a';
          feedback.textContent = '✓ 10% Store Discount Applied!';
        }
        showToast('Voucher Applied!', '10% discount applied to your order.', 'success');
      } else {
        appliedVoucherCode = '';
        voucherDiscountPercent = 0;
        if (feedback) {
          feedback.style.display = 'block';
          feedback.style.color = '#ef4444';
          feedback.textContent = 'Invalid code. Try "DARAZ10" or "TERAI10".';
        }
      }
      renderDrawerSummaries();
    };

    sideCartDrawer.querySelector('#btn-drawer-apply-voucher')?.addEventListener('click', () => {
      applyVoucherLogic('#drawer-voucher-input', '#drawer-voucher-feedback');
    });

    sideCartDrawer.querySelector('#btn-checkout-apply-promo')?.addEventListener('click', () => {
      applyVoucherLogic('#checkout-promo-input', '#checkout-promo-feedback');
    });

    // Step 1: Proceed to Checkout -> Go to Step 2
    sideCartDrawer.querySelector('#btn-drawer-proceed-checkout')?.addEventListener('click', () => {
      const cart = getCart();
      const activeItems = cart.filter(i => !unselectedItemIds.has(String(i.id)));
      if (activeItems.length === 0) {
        showToast('Basket Empty', 'Please select at least 1 item to proceed to checkout.', 'warning');
        return;
      }
      goToDrawerStep(2);
    });

    // Step 2: Edit Address Toggle
    sideCartDrawer.querySelector('#btn-edit-shipping-address')?.addEventListener('click', () => {
      const editView = sideCartDrawer.querySelector('#checkout-address-edit-view');
      const dispView = sideCartDrawer.querySelector('#checkout-address-display-view');
      if (editView && dispView) {
        const isEditing = editView.style.display !== 'none';
        editView.style.display = isEditing ? 'none' : 'block';
        dispView.style.display = isEditing ? 'block' : 'none';
      }
    });

    // Tag Selection
    sideCartDrawer.querySelectorAll('.btn-tag-select').forEach(btn => {
      btn.addEventListener('click', () => {
        sideCartDrawer.querySelectorAll('.btn-tag-select').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      });
    });

    // Save Address
    sideCartDrawer.querySelector('#btn-save-address')?.addEventListener('click', () => {
      const name = sideCartDrawer.querySelector('#edit-cust-name')?.value.trim() || 'Suraj Mahato';
      const phone = sideCartDrawer.querySelector('#edit-cust-phone')?.value.trim() || '9805996874';
      const activeTagBtn = sideCartDrawer.querySelector('.btn-tag-select.active');
      const tag = activeTagBtn ? activeTagBtn.getAttribute('data-tag') : 'OFFICE';
      const address = sideCartDrawer.querySelector('#edit-cust-address')?.value.trim() || DEFAULT_DARAZ_ADDRESS.address;
      const note = sideCartDrawer.querySelector('#edit-cust-note')?.value.trim() || '';

      const updatedAddr = { name, phone, tag, address, note };
      try {
        localStorage.setItem(STORAGE_ADDRESS, JSON.stringify(updatedAddr));
      } catch (e) {}

      // Update display elements
      const dispName = sideCartDrawer.querySelector('#disp-cust-name');
      const dispPhone = sideCartDrawer.querySelector('#disp-cust-phone');
      const dispTag = sideCartDrawer.querySelector('#disp-cust-tag');
      const dispAddress = sideCartDrawer.querySelector('#disp-cust-address');
      const dispNote = sideCartDrawer.querySelector('#disp-cust-note');

      if (dispName) dispName.textContent = name;
      if (dispPhone) dispPhone.textContent = phone;
      if (dispTag) dispTag.textContent = tag;
      if (dispAddress) dispAddress.textContent = address;
      if (dispNote) dispNote.textContent = note;

      sideCartDrawer.querySelector('#checkout-address-edit-view').style.display = 'none';
      sideCartDrawer.querySelector('#checkout-address-display-view').style.display = 'block';
      showToast('Address Updated', 'Shipping address saved successfully.', 'success');
      renderDrawerSummaries();
    });

    // Cancel Address Edit
    sideCartDrawer.querySelector('#btn-cancel-address')?.addEventListener('click', () => {
      sideCartDrawer.querySelector('#checkout-address-edit-view').style.display = 'none';
      sideCartDrawer.querySelector('#checkout-address-display-view').style.display = 'block';
    });

    // Step 2: Back to Basket
    sideCartDrawer.querySelector('#btn-checkout-back-to-cart')?.addEventListener('click', () => {
      goToDrawerStep(1);
    });

    // Step 2: Proceed to Pay -> Go to Step 3
    sideCartDrawer.querySelector('#btn-proceed-to-pay')?.addEventListener('click', () => {
      goToDrawerStep(3);
    });

    // Step 3: Back to Checkout
    sideCartDrawer.querySelector('#btn-drawer-back-to-2')?.addEventListener('click', () => {
      goToDrawerStep(2);
    });

    // Step 3: Payment method tiles
    sideCartDrawer.querySelectorAll('.cart-drawer-payment-tile').forEach(tile => {
      tile.addEventListener('click', () => {
        sideCartDrawer.querySelectorAll('.cart-drawer-payment-tile').forEach(t => t.classList.remove('selected'));
        tile.classList.add('selected');
        const radio = tile.querySelector('input[type="radio"]');
        if (radio) {
          radio.checked = true;
          selectedPaymentMethod = radio.value;
        }
      });
    });

    // Step 3: Form submit -> Order Confirmed in Step 4
    sideCartDrawer.querySelector('#form-drawer-payment')?.addEventListener('submit', (e) => {
      e.preventDefault();
      const cart = getCart();
      const activeItems = cart.filter(i => !unselectedItemIds.has(String(i.id)));
      const subtotal = calculateDrawerSubtotal();
      const shipping = calculateDrawerShipping();
      const discount = (subtotal * voucherDiscountPercent) / 100;
      const total = Math.max(0, subtotal - discount) + shipping;

      const addrData = getSavedAddress();
      const orderRef = 'TF-' + Math.floor(10000 + Math.random() * 90000);
      const now = new Date();
      const orderDateStr = now.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });

      lastOrderDetails = {
        orderRef,
        date: orderDateStr,
        name: addrData.name,
        phone: addrData.phone,
        address: addrData.address,
        tag: addrData.tag,
        items: activeItems,
        subtotal,
        discount,
        shipping,
        total,
        paymentMethod: selectedPaymentMethod === 'card' ? 'Credit/Debit Card' : (selectedPaymentMethod === 'paypal' ? 'PayPal' : (selectedPaymentMethod === 'bacs' ? 'Bank Transfer' : 'Cash on Delivery'))
      };

      // Populate Step 4 confirmation pane inside the drawer
      const confirmContent = sideCartDrawer.querySelector('#drawer-confirm-content');
      if (confirmContent) {
        const itemsRows = lastOrderDetails.items.map(item => `
          <tr>
            <td>
              <div style="display: flex; align-items: center; gap: 8px;">
                <img src="${item.image || '/static/web/images/1-16-500x500.jpg'}" alt="${item.title}" style="width: 32px; height: 32px; object-fit: cover; border: 1px solid #e2e8f0;">
                <div>
                  <strong style="color: #0f172a; font-size: 11.5px;">${item.title}</strong>
                  <div style="font-size: 10px; color: #64748b;">Qty: ${item.quantity} &times; £${Number(item.price).toFixed(2)}</div>
                </div>
              </div>
            </td>
            <td style="text-align: right; font-weight: 700; color: #0f172a;">
              £${(item.price * item.quantity).toFixed(2)}
            </td>
          </tr>
        `).join('');

        confirmContent.innerHTML = `
          <div class="cart-drawer-confirm-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
          </div>
          <h3 class="cart-drawer-confirm-title">Order Confirmed!</h3>
          <p class="cart-drawer-confirm-desc">
            Thank you, <strong>${lastOrderDetails.name}</strong>! Your order has been placed successfully.
          </p>

          <div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 12px 14px; text-align: left; margin-bottom: 14px; font-size: 11.5px; display: flex; flex-direction: column; gap: 4px;">
            <div style="display: flex; justify-content: space-between;">
              <span style="color: #64748b;">Order Reference:</span>
              <strong style="color: #0f172a; font-weight: 800;">#${lastOrderDetails.orderRef}</strong>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span style="color: #64748b;">Order Date:</span>
              <span style="color: #0f172a; font-weight: 600;">${lastOrderDetails.date}</span>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span style="color: #64748b;">Payment Method:</span>
              <span style="color: #0f172a; font-weight: 600;">${lastOrderDetails.paymentMethod}</span>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span style="color: #64748b;">Delivery To:</span>
              <span style="color: #0f172a; font-weight: 600; text-align: right; max-width: 60%;">${lastOrderDetails.name} (${lastOrderDetails.tag}) - ${lastOrderDetails.address}</span>
            </div>
          </div>

          <table class="cart-drawer-receipt-table">
            <thead>
              <tr>
                <th>Item Details</th>
                <th style="text-align: right;">Total</th>
              </tr>
            </thead>
            <tbody>
              ${itemsRows}
            </tbody>
            <tfoot>
              <tr>
                <td style="font-weight: 600; color: #64748b; padding-top: 8px;">Subtotal:</td>
                <td style="text-align: right; font-weight: 600; color: #0f172a; padding-top: 8px;">£${lastOrderDetails.subtotal.toFixed(2)}</td>
              </tr>
              ${lastOrderDetails.discount > 0 ? `
              <tr>
                <td style="font-weight: 600; color: #16a34a;">Store Discount:</td>
                <td style="text-align: right; font-weight: 600; color: #16a34a;">-£${lastOrderDetails.discount.toFixed(2)}</td>
              </tr>` : ''}
              <tr>
                <td style="font-weight: 600; color: #64748b;">Delivery Fee:</td>
                <td style="text-align: right; font-weight: 600; color: #0f172a;">${lastOrderDetails.shipping === 0 ? 'FREE' : '£' + lastOrderDetails.shipping.toFixed(2)}</td>
              </tr>
              <tr style="border-top: 1px solid #cbd5e1;">
                <td style="font-weight: 800; font-size: 13px; color: #0f172a;">Total Paid:</td>
                <td style="text-align: right; font-weight: 900; font-size: 15px; color: #f85606;">£${lastOrderDetails.total.toFixed(2)}</td>
              </tr>
            </tfoot>
          </table>

          <div style="display: flex; align-items: center; justify-content: center; gap: 10px; margin-top: 16px;">
            <button type="button" class="cart-drawer-btn-secondary" id="btn-drawer-continue-shopping" style="height: 38px; padding: 0 18px;">
              Continue Shopping
            </button>
            <a href="/track-order/?order=${lastOrderDetails.orderRef}" class="checkout-btn-proceed-pay" style="width: auto; height: 38px; padding: 0 20px; line-height: 38px; text-decoration: none;">
              Track Order &rarr;
            </a>
          </div>
        `;

        confirmContent.querySelector('#btn-drawer-continue-shopping')?.addEventListener('click', () => {
          closeSideCart();
          goToDrawerStep(1);
        });
      }

      // Empty basket and update headers
      saveCart([]);
      unselectedItemIds.clear();

      goToDrawerStep(4);
      showToast('Order Placed!', `Order #${orderRef} placed successfully.`, 'success');
    });
  }

  function calculateDrawerSubtotal() {
    const cart = getCart();
    return cart.reduce((sum, item) => {
      if (unselectedItemIds.has(String(item.id))) return sum;
      return sum + (Number(item.price) || 0) * (Number(item.quantity) || 1);
    }, 0);
  }

  function calculateDrawerShipping() {
    const subtotal = calculateDrawerSubtotal();
    if (selectedShippingMethod === 'express') return 6.99;
    return subtotal >= 50.0 ? 0.0 : 3.99;
  }

  function renderDrawerSummaries() {
    const subtotal = calculateDrawerSubtotal();
    const shipping = calculateDrawerShipping();
    const discount = (subtotal * voucherDiscountPercent) / 100;
    const total = Math.max(0, subtotal - discount) + shipping;
    const cart = getCart();
    const activeCount = cart.filter(i => !unselectedItemIds.has(String(i.id))).length;

    // Step 1 summary values
    const s1ItemsCount = document.getElementById('drawer-items-count-label');
    const subtotalEl = document.getElementById('drawer-subtotal-val');
    const shippingEl = document.getElementById('drawer-shipping-val');
    const totalEl = document.getElementById('drawer-total-val');
    const discountRow = document.getElementById('drawer-discount-row');
    const discountVal = document.getElementById('drawer-discount-val');

    if (s1ItemsCount) s1ItemsCount.textContent = `${activeCount} Items`;
    if (subtotalEl) subtotalEl.textContent = '£' + subtotal.toFixed(2);
    if (shippingEl) shippingEl.textContent = (shipping === 0 ? 'FREE' : '£' + shipping.toFixed(2));
    if (totalEl) totalEl.textContent = '£' + total.toFixed(2);

    if (discountRow && discountVal) {
      if (discount > 0) {
        discountRow.style.display = 'flex';
        discountVal.textContent = '-£' + discount.toFixed(2);
      } else {
        discountRow.style.display = 'none';
      }
    }

    // Step 2 (Checkout screen) summary values
    const s2ItemsCount = document.getElementById('checkout-summary-items-count');
    const s2ItemsTotal = document.getElementById('checkout-summary-items-total');
    const s2ShippingFee = document.getElementById('checkout-summary-delivery-fee');
    const s2GrandTotal = document.getElementById('checkout-summary-grand-total');
    const s2DiscountRow = document.getElementById('checkout-summary-discount-row');
    const s2DiscountVal = document.getElementById('checkout-summary-discount-val');
    const s2DeliveryPriceText = document.getElementById('checkout-delivery-price-text');

    if (s2ItemsCount) s2ItemsCount.textContent = `${activeCount} Items`;
    if (s2ItemsTotal) s2ItemsTotal.textContent = '£' + subtotal.toFixed(2);
    if (s2ShippingFee) s2ShippingFee.textContent = (shipping === 0 ? 'FREE' : '£' + shipping.toFixed(2));
    if (s2DeliveryPriceText) s2DeliveryPriceText.textContent = (shipping === 0 ? 'FREE' : '£' + shipping.toFixed(2));
    if (s2GrandTotal) s2GrandTotal.textContent = '£' + total.toFixed(2);

    if (s2DiscountRow && s2DiscountVal) {
      if (discount > 0) {
        s2DiscountRow.style.display = 'flex';
        s2DiscountVal.textContent = '-£' + discount.toFixed(2);
      } else {
        s2DiscountRow.style.display = 'none';
      }
    }

    // Step 3 summary values
    const s3Shipping = document.getElementById('drawer-step3-shipping');
    const s3Total = document.getElementById('drawer-step3-total');
    const s3CustPreview = document.getElementById('drawer-step3-cust-preview');

    if (s3Shipping) s3Shipping.textContent = (shipping === 0 ? 'FREE' : '£' + shipping.toFixed(2));
    if (s3Total) s3Total.textContent = '£' + total.toFixed(2);
    if (s3CustPreview) {
      const addr = getSavedAddress();
      s3CustPreview.textContent = `${addr.name} (${addr.tag || 'OFFICE'})`;
    }
  }

  function renderDrawerCart() {
    if (!sideCartDrawer) initSideCartDrawer();

    const container = document.getElementById('drawer-cart-items-container');
    const topBar = document.getElementById('drawer-top-bar');
    const vendorCard = document.getElementById('drawer-vendor-card');
    const summaryCol = document.getElementById('drawer-step1-summary-col');
    const selectAllCheck = document.getElementById('drawer-select-all');
    const selectAllText = document.getElementById('drawer-select-all-text');

    if (!container) return;

    const cart = getCart();

    // Select all status
    if (selectAllText) {
      selectAllText.textContent = `SELECT ALL (${cart.length} ITEMS)`;
    }
    if (selectAllCheck) {
      const allSelected = cart.length > 0 && cart.every(i => !unselectedItemIds.has(String(i.id)));
      selectAllCheck.checked = allSelected;
    }

    if (cart.length === 0) {
      if (topBar) topBar.style.display = 'none';
      if (vendorCard) vendorCard.style.display = 'none';
      if (summaryCol) summaryCol.style.display = 'none';

      container.innerHTML = `
        <div class="cart-drawer-empty">
          <div class="cart-drawer-empty-icon">
            <i class="klb-icon-shopping-cart-3"></i>
          </div>
          <h4 style="font-size: 15px; font-weight: 800; color: #0f172a; margin-bottom: 4px;">Your Basket is Empty</h4>
          <p style="font-size: 12px; color: #64748b; margin-bottom: 16px;">Explore our organic groceries and fresh pantry specials.</p>
          <a href="/shop/" class="cart-drawer-btn-checkout" style="display: inline-flex; width: auto; padding: 0 24px; height: 38px; text-decoration: none;">
            Start Shopping
          </a>
        </div>
      `;
      renderDrawerSummaries();
      return;
    }

    if (topBar) topBar.style.display = 'flex';
    if (vendorCard) vendorCard.style.display = 'block';
    if (summaryCol) summaryCol.style.display = 'block';

    // Render Items in Step 1
    container.innerHTML = cart.map(item => {
      const isSelected = !unselectedItemIds.has(String(item.id));
      const lineTotal = (item.price * item.quantity).toFixed(2);
      return `
        <div class="cart-drawer-item-row ${isSelected ? '' : 'is-unselected'}" data-id="${item.id}">
          <label class="cart-custom-checkbox" style="flex-shrink: 0;">
            <input type="checkbox" class="drawer-item-checkbox" data-id="${item.id}" ${isSelected ? 'checked' : ''}>
            <span class="cart-checkbox-box"></span>
          </label>
          <div class="cart-drawer-thumb-box">
            <img src="${item.image || '/static/web/images/1-16-500x500.jpg'}" alt="${item.title}">
          </div>
          <div class="cart-drawer-item-info">
            <h5 class="cart-drawer-item-title" title="${item.title}">${item.title}</h5>
            <span class="cart-drawer-item-badge">FRESH &bull; IN STOCK</span>
            <div style="font-size: 11px; color: #64748b; margin-top: 2px;">
              £${Number(item.price).toFixed(2)} each
            </div>
          </div>
          <div class="cart-drawer-pricing-col">
            <div class="cart-drawer-price">£${lineTotal}</div>
            <div class="cart-drawer-stepper-wrap">
              <div class="cart-stepper-control">
                <button type="button" class="cart-stepper-btn btn-drawer-qty-minus" data-id="${item.id}">-</button>
                <input type="text" class="cart-stepper-input" value="${item.quantity}" readonly>
                <button type="button" class="cart-stepper-btn btn-drawer-qty-plus" data-id="${item.id}">+</button>
              </div>
              <button type="button" class="cart-drawer-delete-btn" data-id="${item.id}" title="Remove item">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
              </button>
            </div>
          </div>
        </div>
      `;
    }).join('');

    // Attach listeners
    container.querySelectorAll('.drawer-item-checkbox').forEach(chk => {
      chk.addEventListener('change', () => {
        const id = chk.getAttribute('data-id');
        if (chk.checked) {
          unselectedItemIds.delete(String(id));
        } else {
          unselectedItemIds.add(String(id));
        }
        renderDrawerCart();
      });
    });

    container.querySelectorAll('.btn-drawer-qty-plus').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        changeCartItemQty(btn.getAttribute('data-id'), 1);
        renderDrawerCart();
      });
    });

    container.querySelectorAll('.btn-drawer-qty-minus').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        changeCartItemQty(btn.getAttribute('data-id'), -1);
        renderDrawerCart();
      });
    });

    container.querySelectorAll('.cart-drawer-delete-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        removeCartItem(btn.getAttribute('data-id'));
        renderDrawerCart();
      });
    });

    renderDrawerSummaries();
  }

  function renderCheckoutPackage() {
    const pkgContainer = document.getElementById('checkout-pkg-items-container');
    const etaText = document.getElementById('checkout-delivery-eta-text');
    if (!pkgContainer) return;

    // Delivery guarantee date: 3 business days from now
    const targetDate = new Date();
    targetDate.setDate(targetDate.getDate() + 3);
    const dateFormatted = targetDate.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
    if (etaText) etaText.textContent = 'Guaranteed by ' + dateFormatted;

    const cart = getCart();
    const activeItems = cart.filter(i => !unselectedItemIds.has(String(i.id)));

    if (activeItems.length === 0) {
      pkgContainer.innerHTML = '<div style="padding: 16px; text-align: center; color: #64748b; font-size: 12px;">No items selected for this package.</div>';
      return;
    }

    pkgContainer.innerHTML = activeItems.map(item => `
      <div class="checkout-pkg-item-row" data-id="${item.id}">
        <div class="checkout-pkg-item-left">
          <img src="${item.image || '/static/web/images/1-16-500x500.jpg'}" alt="${item.title}" class="checkout-pkg-thumb">
          <div>
            <h5 class="checkout-pkg-title" title="${item.title}">${item.title}</h5>
            <p class="checkout-pkg-desc">Fresh Farm Harvest, Standard Pack</p>
          </div>
        </div>
        <div class="checkout-pkg-item-right">
          <div class="checkout-pkg-price">£${(item.price * item.quantity).toFixed(2)}</div>
          <div class="checkout-pkg-qty">Qty: ${item.quantity}</div>
          <button type="button" class="checkout-pkg-del-btn" data-id="${item.id}" title="Remove item">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
          </button>
        </div>
      </div>
    `).join('');

    pkgContainer.querySelectorAll('.checkout-pkg-del-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        removeCartItem(btn.getAttribute('data-id'));
        renderCheckoutPackage();
        renderDrawerSummaries();
      });
    });
  }

  function goToDrawerStep(step) {
    currentDrawerStep = step;
    if (!sideCartDrawer) initSideCartDrawer();

    const titleEl = sideCartDrawer.querySelector('#drawer-step-title');
    if (titleEl) {
      if (step === 1) titleEl.textContent = 'Shopping Cart';
      if (step === 2) titleEl.textContent = 'Checkout';
      if (step === 3) titleEl.textContent = 'Choose Payment Method';
      if (step === 4) titleEl.textContent = 'Order Confirmed';
    }

    sideCartDrawer.querySelectorAll('.cart-drawer-step-pane').forEach((pane, idx) => {
      if (idx + 1 === step) {
        pane.classList.add('active');
      } else {
        pane.classList.remove('active');
      }
    });

    if (step === 1) renderDrawerCart();
    if (step === 2) renderCheckoutPackage();
    renderDrawerSummaries();
  }

  // Backward compatibility aliases
  function openCommerceModal(step = 1) {
    openSideCart(step);
  }

  function initCommerceModal() {
    initSideCartDrawer();
  }
  // --- Quick View Modal System ---
  let quickviewBackdrop = null;
  function initQuickviewModal() {
    quickviewBackdrop = document.createElement('div');
    quickviewBackdrop.className = 'terai-quickview-backdrop';
    quickviewBackdrop.id = 'terai-quickview-modal';

    quickviewBackdrop.innerHTML = `
      <div class="terai-quickview-dialog">
        <button type="button" class="terai-quickview-close" aria-label="Close modal">
          <i class="klb-icon-x"></i>
        </button>
        <div class="terai-quickview-grid">
          <div class="terai-quickview-gallery">
            <img src="" alt="" class="terai-quickview-img" id="qv-img">
          </div>
          <div class="terai-quickview-info">
            <span class="terai-quickview-badge" id="qv-stock">✓ In Stock &bull; Fresh Batch</span>
            <h2 class="terai-quickview-title" id="qv-title">Product Title</h2>
            <div class="d-flex align-items-center gap-2 mb-2">
              <div class="star-rating text-13" style="color: #f59e0b;">
                <i class="klb-icon-star"></i><i class="klb-icon-star"></i><i class="klb-icon-star"></i><i class="klb-icon-star"></i><i class="klb-icon-star"></i>
              </div>
              <span class="text-12 text-gray-500" id="qv-reviews">(18 verified customer ratings)</span>
            </div>
            <div class="terai-quickview-price-wrap">
              <span class="terai-quickview-price" id="qv-price">£5.99</span>
              <span class="terai-quickview-old-price" id="qv-old-price">£7.99</span>
            </div>
            <p class="terai-quickview-desc" id="qv-desc">
              Carefully sourced organic groceries from certified farms. Delivered fresh to your door across the UK with complete temperature guarantee.
            </p>
            <div class="terai-quickview-qty-group">
              <span class="text-13 fw-semibold text-gray-600">Quantity:</span>
              <div class="terai-quickview-stepper">
                <button type="button" id="qv-qty-minus">-</button>
                <input type="text" id="qv-qty-input" value="1" readonly>
                <button type="button" id="qv-qty-plus">+</button>
              </div>
            </div>
            <div class="terai-quickview-actions">
              <button type="button" class="terai-btn-add-cart" id="qv-btn-add">
                <i class="klb-icon-cart"></i> Add to Basket
              </button>
              <a href="/checkout/" class="terai-btn-buy-now" id="qv-btn-buy">
                Buy Now &bull; Instant Checkout
              </a>
            </div>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(quickviewBackdrop);

    // Event listeners
    quickviewBackdrop.querySelector('.terai-quickview-close').addEventListener('click', closeQuickview);
    quickviewBackdrop.addEventListener('click', (e) => {
      if (e.target === quickviewBackdrop) closeQuickview();
    });

    const qtyInput = quickviewBackdrop.querySelector('#qv-qty-input');
    quickviewBackdrop.querySelector('#qv-qty-minus').addEventListener('click', () => {
      let val = parseInt(qtyInput.value, 10) || 1;
      if (val > 1) qtyInput.value = val - 1;
    });

    quickviewBackdrop.querySelector('#qv-qty-plus').addEventListener('click', () => {
      let val = parseInt(qtyInput.value, 10) || 1;
      qtyInput.value = val + 1;
    });
  }

  let activeQuickviewProduct = null;
  function openQuickview(product) {
    if (!quickviewBackdrop) initQuickviewModal();
    activeQuickviewProduct = product;

    const img = quickviewBackdrop.querySelector('#qv-img');
    const title = quickviewBackdrop.querySelector('#qv-title');
    const price = quickviewBackdrop.querySelector('#qv-price');
    const oldPrice = quickviewBackdrop.querySelector('#qv-old-price');
    const stock = quickviewBackdrop.querySelector('#qv-stock');
    const qtyInput = quickviewBackdrop.querySelector('#qv-qty-input');

    img.src = product.image;
    img.alt = product.title;
    title.textContent = product.title;
    price.textContent = '£' + product.price.toFixed(2);

    if (product.oldPrice) {
      oldPrice.style.display = 'inline';
      oldPrice.textContent = '£' + product.oldPrice.toFixed(2);
    } else {
      oldPrice.style.display = 'none';
    }

    stock.textContent = `✓ ${product.stock} &bull; 100% Freshness Guarantee`;
    qtyInput.value = '1';

    const addBtn = quickviewBackdrop.querySelector('#qv-btn-add');
    addBtn.onclick = () => {
      const qty = parseInt(qtyInput.value, 10) || 1;
      addToCart(product, qty);
      closeQuickview();
    };

    const buyBtn = quickviewBackdrop.querySelector('#qv-btn-buy');
    buyBtn.onclick = (e) => {
      e.preventDefault();
      const qty = parseInt(qtyInput.value, 10) || 1;
      addToCart(product, qty);
      closeQuickview();
      openSideCart(2);
    };

    quickviewBackdrop.classList.add('active');
  }

  function closeQuickview() {
    if (quickviewBackdrop) {
      quickviewBackdrop.classList.remove('active');
    }
  }

  // --- Live Search System ---
  function setupLiveSearch() {
    const searchInputs = document.querySelectorAll('.search-input');

    searchInputs.forEach(input => {
      const parentForm = input.closest('form');
      const container = parentForm ? parentForm.parentElement : input.parentElement;
      if (!container) return;

      container.style.position = 'relative';

      const resultsDropdown = document.createElement('div');
      resultsDropdown.className = 'terai-search-results';
      container.appendChild(resultsDropdown);

      input.addEventListener('input', () => {
        const query = input.value.trim().toLowerCase();
        if (query.length < 2) {
          resultsDropdown.classList.remove('active');
          resultsDropdown.innerHTML = '';
          return;
        }

        const matches = catalog.filter(p => p.title.toLowerCase().includes(query)).slice(0, 6);

        if (matches.length === 0) {
          resultsDropdown.innerHTML = `
            <div class="terai-search-empty">
              No matching products found for "<strong>${input.value}</strong>".
            </div>
          `;
        } else {
          resultsDropdown.innerHTML = `
            <div class="terai-search-header">
              <span>Matching Products (${matches.length})</span>
              <span class="text-primary" style="cursor: pointer;" id="btn-close-search-results">✕</span>
            </div>
            ${matches.map(p => `
              <div class="terai-search-item" data-id="${p.id}">
                <img src="${p.image}" alt="${p.title}" class="terai-search-thumb">
                <div class="terai-search-info">
                  <div class="terai-search-name">${p.title}</div>
                  <div class="terai-search-price">£${p.price.toFixed(2)}</div>
                </div>
                <button type="button" class="terai-search-btn" data-id="${p.id}">
                  + Basket
                </button>
              </div>
            `).join('')}
          `;

          // Close button
          resultsDropdown.querySelector('#btn-close-search-results')?.addEventListener('click', () => {
            resultsDropdown.classList.remove('active');
          });

          // Click items
          resultsDropdown.querySelectorAll('.terai-search-item').forEach(itemEl => {
            itemEl.addEventListener('click', (e) => {
              if (e.target.classList.contains('terai-search-btn')) {
                e.stopPropagation();
                const prod = getProductById(e.target.getAttribute('data-id'));
                if (prod) addToCart(prod, 1);
                return;
              }
              const prod = getProductById(itemEl.getAttribute('data-id'));
              if (prod) {
                resultsDropdown.classList.remove('active');
                openQuickview(prod);
              }
            });
          });
        }

        resultsDropdown.classList.add('active');
      });

      // Close dropdown when clicking outside
      document.addEventListener('click', (e) => {
        if (!container.contains(e.target)) {
          resultsDropdown.classList.remove('active');
        }
      });

      // Intercept submit
      if (parentForm) {
        parentForm.addEventListener('submit', (e) => {
          e.preventDefault();
          const query = input.value.trim().toLowerCase();
          resultsDropdown.classList.remove('active');
          filterProductsByQuery(query);
        });
      }
    });
  }

  function filterProductsByQuery(query) {
    if (!query) {
      catalog.forEach(p => p.element.style.display = '');
      return;
    }
    let count = 0;
    catalog.forEach(p => {
      if (p.title.toLowerCase().includes(query)) {
        p.element.style.display = '';
        count++;
      } else {
        p.element.style.display = 'none';
      }
    });

    showToast('Search Results', `Found ${count} products matching "${query}".`, 'info');
    const firstMatch = catalog.find(p => p.title.toLowerCase().includes(query));
    if (firstMatch) {
      firstMatch.element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  // --- Category Filtering ---
  function setupCategoryFiltering() {
    const categoryLinks = document.querySelectorAll('.site-categories a, .categories-menu a, .category-box a, .site-category-box a');

    categoryLinks.forEach(link => {
      link.addEventListener('click', (e) => {
        if (link.classList.contains('categories-toggle') || link.closest('.categories-toggle')) {
          return;
        }
        e.preventDefault();
        const text = link.textContent.trim();
        if (!text || text.toLowerCase() === 'all categories') {
          catalog.forEach(p => p.element.style.display = '');
          showToast('All Categories', 'Showing all grocery products.', 'info');
          return;
        }

        // Filter products matching keyword or show relevant section
        let count = 0;
        const keywords = text.toLowerCase().split(/[\s&,/]+/);

        catalog.forEach(p => {
          const title = p.title.toLowerCase();
          const matches = keywords.some(k => k.length > 2 && title.includes(k));
          if (matches) {
            p.element.style.display = '';
            count++;
          } else {
            p.element.style.display = 'none';
          }
        });

        if (count === 0) {
          // If no keyword match in titles, keep all displayed and scroll to products
          catalog.forEach(p => p.element.style.display = '');
          showToast(text, `Browsing fresh items in ${text}.`, 'info');
        } else {
          showToast(text, `Showing ${count} products in ${text}.`, 'info');
        }

        const shopSection = document.querySelector('.products');
        if (shopSection) shopSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
  }

  // --- Quantity Steppers on Product Cards ---
  function setupProductCardSteppers() {
    document.querySelectorAll('.quantity.ajax-quantity').forEach(qtyWrapper => {
      const minus = qtyWrapper.querySelector('.quantity-button.minus');
      const plus = qtyWrapper.querySelector('.quantity-button.plus');
      const input = qtyWrapper.querySelector('input.qty');

      if (minus && input) {
        minus.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          let current = parseInt(input.value, 10) || 1;
          if (current > 1) input.value = current - 1;
        });
      }

      if (plus && input) {
        plus.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          let current = parseInt(input.value, 10) || 1;
          input.value = current + 1;
        });
      }
    });
  }

  // --- Product Card Click Handlers (Add to Cart & Quickview) ---
  function setupProductCardClicks() {
    // 1. Add to cart buttons
    document.querySelectorAll('.button.ajax_add_to_cart, .button.add_to_cart_button, a[href*="add-to-cart"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();

        const productNode = btn.closest('.product, .shop-product-card');
        const id = btn.getAttribute('data-product_id') ||
                   productNode?.className.match(/post-(\d+)/)?.[1];

        const product = getProductById(id) || catalog[0];
        if (!product) return;

        const qtyInput = productNode?.querySelector('input.qty');
        const qty = qtyInput ? (parseInt(qtyInput.value, 10) || 1) : 1;

        btn.classList.add('added-success');
        const origText = btn.innerHTML;
        btn.innerHTML = '✓ Added! <i class="klb-icon-check"></i>';

        setTimeout(() => {
          btn.classList.remove('added-success');
          btn.innerHTML = origText;
        }, 1500);

        addToCart(product, qty);
      });
    });

    // 2. Quickview only on explicit quick-view eye buttons
    document.querySelectorAll('.quickview-button, .quick-view-button a, .action-icons .eye-link').forEach(el => {
      el.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();

        const productNode = el.closest('.product, .shop-product-card');
        const id = el.getAttribute('data-product_id') ||
                   productNode?.querySelector('[data-product_id]')?.getAttribute('data-product_id') ||
                   productNode?.className.match(/post-(\d+)/)?.[1];

        const product = getProductById(id) || catalog[0];
        if (product) {
          openQuickview(product);
        }
      });
    });

    // 2b. Product Thumbnail, Image, and Title clicks -> Navigate directly to product-detail.html
    document.querySelectorAll('.product .product-thumbnail a, .product .product-title a, .shop-product-card .product-thumbnail a, .shop-product-card .product-title a, a[href*="product-detail"], a[href*="/product/"]').forEach(el => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        window.location.href = '/product-detail/';
      });
    });

    // 2c. Whole product card click: clicking anywhere on a product card opens product-detail.html
    document.querySelectorAll('.shop-product-card, .product.type-product').forEach(card => {
      card.addEventListener('click', (e) => {
        // Ignore if clicking interactive controls (Add to cart, wishlist, quick view, quantity)
        if (e.target.closest('.btn-cart-pill, .ajax_add_to_cart, .add_to_cart_button, .quickview-button, .eye-link, .action-icons, .klbwl-btn, .quantity, .thumbnail-buttons')) {
          return;
        }
        window.location.href = '/product-detail/';
      });
    });

    // 3. Wishlist buttons on product cards
    document.querySelectorAll('.klbwl-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();

        const id = String(btn.getAttribute('data-product_id') || '');
        if (!id) return;
        let wishlist = getWishlist();
        const exists = wishlist.some(item => String(item.id) === id);

        if (exists) {
          wishlist = wishlist.filter(item => String(item.id) !== id);
          btn.classList.remove('active', 'liked', 'klbwl-product-in-list');
          showToast('Wishlist Updated', 'Item removed from your wishlist.', 'info');
        } else {
          const prod = getProductById(id);
          const card = btn.closest('.product, .shop-product-card');
          const title = prod ? prod.title : (card?.querySelector('.product-title a, .product-title')?.textContent?.trim() || btn.getAttribute('data-product_title') || 'Organic Farm Produce');
          let price = prod ? prod.price : 4.99;
          const priceText = card?.querySelector('.price ins .amount, .price .amount')?.textContent?.replace(/[^0-9.]/g, '');
          if (priceText) price = parseFloat(priceText);
          const image = prod ? prod.image : (card?.querySelector('.wp-post-image, img')?.getAttribute('src') || '/static/web/images/1-16-500x500.jpg');

          wishlist.push({
            id: id,
            title: title,
            price: price,
            image: image,
            stock: 'In Stock'
          });
          btn.classList.add('active', 'liked', 'klbwl-product-in-list');
          showToast('Wishlist Saved', `✓ ${title} added to your wishlist.`, 'info');
        }

        saveWishlist(wishlist);
      });
    });

    // 4. Compare buttons
    document.querySelectorAll('.klbcp-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const name = btn.getAttribute('data-product_name') || 'Product';
        showToast('Product Comparison', `${name} added to comparison table.`, 'info');
      });
    });
  }

  function updateWishlistUI() {
    const list = getWishlist();
    const count = list.length;

    document.querySelectorAll('.wishlist-count, .klbwl-wishlist-count, .klbwl-count, .wishlist .count, #wishlist-drawer-badge').forEach(el => {
      el.textContent = count;
    });

    const ids = list.map(item => String(item.id));
    document.querySelectorAll('.klbwl-btn').forEach(btn => {
      const id = String(btn.getAttribute('data-product_id') || '');
      if (ids.includes(id)) {
        btn.classList.add('active', 'liked', 'klbwl-product-in-list');
      } else {
        btn.classList.remove('active', 'liked', 'klbwl-product-in-list');
      }
    });

    renderWishlistDrawer();
  }

  // --- Location Selector Fix & Bindings ---
  function setupLocationModal() {
    const triggers = document.querySelectorAll('[data-modal="location-selector"], .location-selector-button a');
    let modal = document.getElementById('location-selector');

    triggers.forEach(trig => {
      trig.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        modal = document.getElementById('location-selector');
        if (modal) {
          modal.classList.add('active');
        } else {
          const loc = prompt('Enter your UK delivery postcode or area (e.g. SW1A 1AA, London, Birmingham):', 'London, UK');
          if (loc && loc.trim()) {
            document.querySelectorAll('.location-selector-button .action-text p').forEach(p => p.textContent = loc.trim());
            showToast('Delivery Location Set', `Delivering to ${loc.trim()}. Cold-chain delivery active.`, 'success');
          }
        }
      });
    });

    if (modal) {
      const closeButtons = modal.querySelectorAll('.close-button, .site-modal-overlay');
      closeButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          modal.classList.remove('active');
        });
      });
    }
  }

  // --- Currency Selector Logic ---
  function setupCurrencySelector() {
    const toggleBtn = document.getElementById('currency-toggle-btn');
    const dropdown = document.getElementById('currency-dropdown-card');
    const label = document.getElementById('header-currency-label');

    if (!toggleBtn || !dropdown) return;

    toggleBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      document.querySelectorAll('.header-user-dropdown, .categories-menu .site-categories').forEach(el => el.classList.remove('show'));
      dropdown.classList.toggle('show');
    });

    dropdown.querySelectorAll('.currency-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();

        const code = item.getAttribute('data-currency');
        const symbol = item.getAttribute('data-symbol');

        dropdown.querySelectorAll('.currency-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');

        if (label) {
          label.textContent = `${code} (${symbol})`;
        }

        dropdown.classList.remove('show');
        showToast('Currency Updated', `Store currency set to ${code} (${symbol}).`, 'info');
      });
    });

    document.addEventListener('click', (e) => {
      if (!dropdown.contains(e.target) && !toggleBtn.contains(e.target)) {
        dropdown.classList.remove('show');
      }
    });
  }

  // --- Order Tracking Modal Logic ---
  let trackModalBackdrop = null;
  function initOrderTrackingModal() {
    trackModalBackdrop = document.createElement('div');
    trackModalBackdrop.className = 'terai-track-modal-backdrop';
    trackModalBackdrop.id = 'terai-track-modal';

    trackModalBackdrop.innerHTML = `
      <div class="terai-track-modal-dialog">
        <button type="button" class="terai-track-close" aria-label="Close tracking modal">
          <i class="klb-icon-x"></i>
        </button>
        <div class="d-flex align-items-center gap-3 mb-3">
          <div style="width: 44px; height: 44px; border-radius: 10px; background: #eff6ff; color: #1547A8; display: flex; align-items: center; justify-content: center; font-size: 22px;">
            <i class="klb-icon-truck"></i>
          </div>
          <div>
            <h4 class="text-18 fw-bold text-dark mb-0">Track Your Order</h4>
            <p class="text-12 text-gray-500 mb-0">Live delivery tracking for Terai Food UK</p>
          </div>
        </div>
        
        <div class="mb-3">
          <label class="form-label text-12 fw-semibold text-gray-600 mb-1">Order ID or UK Phone Number</label>
          <div class="input-group">
            <input type="text" id="track-order-input" class="form-control text-13" placeholder="e.g. TF-583921" value="TF-583921">
            <button class="btn btn-primary text-13 px-3" type="button" id="btn-submit-track" style="background: #1547A8; border-color: #1547A8;">Track Now</button>
          </div>
        </div>

        <div id="track-result-box" class="bg-slate-50 p-3 rounded-3 border">
          <div class="d-flex justify-content-between align-items-center pb-2 mb-2 border-bottom">
            <div>
              <span class="text-11 text-gray-400 d-block">Order Reference</span>
              <strong class="text-14 text-dark" id="track-display-id">#TF-583921</strong>
            </div>
            <span class="badge" style="background: #ecfdf5; color: #059669; font-weight: 600; padding: 6px 10px; border-radius: 6px;">Out for Delivery</span>
          </div>

          <div class="track-timeline">
            <div class="track-step done">
              <div class="track-dot"><i class="klb-icon-check"></i></div>
              <div class="track-step-info">
                <h6>1. Order Confirmed</h6>
                <p>Payment approved & order received at 09:15 AM</p>
              </div>
            </div>
            <div class="track-step done">
              <div class="track-dot"><i class="klb-icon-check"></i></div>
              <div class="track-step-info">
                <h6>2. Fresh Picking & Packing</h6>
                <p>Chilled groceries packed with eco-cooling at 11:30 AM</p>
              </div>
            </div>
            <div class="track-step active">
              <div class="track-dot"><i class="klb-icon-truck"></i></div>
              <div class="track-step-info">
                <h6 style="color: #1547A8;">3. Out for UK Delivery</h6>
                <p>Courier in transit &bull; <strong>Estimated delivery today by 16:30</strong></p>
              </div>
            </div>
            <div class="track-step">
              <div class="track-dot"><i class="klb-icon-map-pin"></i></div>
              <div class="track-step-info">
                <h6>4. Arrived at Your Door</h6>
                <p>Contactless doorstep handover</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(trackModalBackdrop);

    trackModalBackdrop.querySelector('.terai-track-close').addEventListener('click', closeOrderTracking);
    trackModalBackdrop.addEventListener('click', (e) => {
      if (e.target === trackModalBackdrop) closeOrderTracking();
    });

    const trackBtn = trackModalBackdrop.querySelector('#btn-submit-track');
    const trackInput = trackModalBackdrop.querySelector('#track-order-input');
    const displayId = trackModalBackdrop.querySelector('#track-display-id');

    trackBtn.addEventListener('click', () => {
      const val = trackInput.value.trim();
      if (val) {
        displayId.textContent = '#' + val.replace(/^#/, '');
        showToast('Tracking Updated', `Live tracking status refreshed for ${val}.`, 'success');
      }
    });
  }

  function openOrderTracking() {
    if (!trackModalBackdrop) initOrderTrackingModal();
    trackModalBackdrop.classList.add('active');
  }

  function closeOrderTracking() {
    if (trackModalBackdrop) {
      trackModalBackdrop.classList.remove('active');
    }
  }

  function setupOrderTracking() {
    document.querySelectorAll('#btn-header-track-order, #nav-track-order-btn, a[href="#order-tracking"]:not([href="/track-order/"])').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        window.location.href = '/track-order/';
      });
    });
  }

  // --- Bulk Order >> Request Quote Modal Logic ---
  let bulkModalBackdrop = null;
  function initBulkQuoteModal() {
    if (bulkModalBackdrop) return;
    bulkModalBackdrop = document.createElement('div');
    bulkModalBackdrop.className = 'terai-generic-modal-backdrop';
    bulkModalBackdrop.id = 'terai-bulk-modal';

    bulkModalBackdrop.innerHTML = `
      <div class="terai-generic-modal-dialog">
        <button type="button" class="terai-generic-modal-close" aria-label="Close bulk order modal">
          <i class="klb-icon-x"></i>
        </button>
        <div class="d-flex align-items-center gap-3 mb-3">
          <div style="width: 48px; height: 48px; border-radius: 12px; background: #ecfdf5; color: #059669; display: flex; align-items: center; justify-content: center; font-size: 24px; flex-shrink: 0;">
            <i class="klb-icon-shopping-cart-3"></i>
          </div>
          <div>
            <div class="d-flex align-items-center gap-2 mb-1">
              <h4 class="text-18 fw-bold text-dark mb-0">Bulk Order &amp; Wholesale Quotation</h4>
              <span class="bulk-badge">B2B Trade</span>
            </div>
            <p class="text-12 text-gray-500 mb-0">Exclusive wholesale pricing, volume discounts &amp; pallet shipping across UK</p>
          </div>
        </div>

        <form id="bulk-quote-form">
          <div class="bulk-form-grid mb-3">
            <div>
              <label class="bulk-form-label" for="bulk-company">Company / Business Name *</label>
              <input type="text" id="bulk-company" class="bulk-form-input" placeholder="e.g. London Fresh Grocers Ltd" required>
            </div>
            <div>
              <label class="bulk-form-label" for="bulk-contact-name">Contact Person *</label>
              <input type="text" id="bulk-contact-name" class="bulk-form-input" placeholder="e.g. Alex Henderson" required>
            </div>
          </div>

          <div class="bulk-form-grid mb-3">
            <div>
              <label class="bulk-form-label" for="bulk-email">Work Email *</label>
              <input type="email" id="bulk-email" class="bulk-form-input" placeholder="name@company.co.uk" required>
            </div>
            <div>
              <label class="bulk-form-label" for="bulk-phone">UK Phone / WhatsApp *</label>
              <input type="tel" id="bulk-phone" class="bulk-form-input" placeholder="+44 7911 123456" required>
            </div>
          </div>

          <div class="bulk-form-grid mb-3">
            <div>
              <label class="bulk-form-label" for="bulk-category">Primary Category Needed</label>
              <select id="bulk-category" class="bulk-form-select">
                <option value="Vegetables & Exotic Produce">Fresh Asian &amp; Exotic Produce</option>
                <option value="Himalayan Rice & Grains">Himalayan Rice, Pulses &amp; Flours</option>
                <option value="Organic Spices & Herbs">Whole &amp; Ground Organic Spices</option>
                <option value="Chilled Meats & Seafood">Chilled Meats &amp; Seafood Packs</option>
                <option value="Full Grocery Assortment">Mixed Pallet / Full Assortment</option>
              </select>
            </div>
            <div>
              <label class="bulk-form-label" for="bulk-volume">Estimated Volume</label>
              <select id="bulk-volume" class="bulk-form-select">
                <option value="50kg - 250kg">Trial Volume (50kg - 250kg)</option>
                <option value="250kg - 1,000kg" selected>Medium Wholesale (250kg - 1,000kg)</option>
                <option value="1 - 3 Pallets">1 to 3 Full Pallets</option>
                <option value="Container / Standing Order">Full Truckload / Weekly Standing Order</option>
              </select>
            </div>
          </div>

          <div class="mb-3">
            <label class="bulk-form-label" for="bulk-notes">Specific Items, UK Delivery Postcode &amp; Requirements</label>
            <textarea id="bulk-notes" class="bulk-form-textarea" rows="2" placeholder="List key products or SKUs, target delivery date and UK destination postcode..."></textarea>
          </div>

          <div id="bulk-form-alert" style="display: none;" class="mb-3 p-3 rounded-2 text-13"></div>

          <button type="submit" class="bulk-submit-btn" id="btn-submit-bulk-quote">
            <i class="klb-icon-check"></i> Request Wholesale Quotation
          </button>
        </form>

        <div id="bulk-success-state" style="display: none;" class="text-center py-3">
          <div style="width: 54px; height: 54px; border-radius: 50%; background: #ecfdf5; color: #059669; display: flex; align-items: center; justify-content: center; font-size: 26px; margin: 0 auto 12px;">
            <i class="klb-icon-check"></i>
          </div>
          <h4 class="text-17 fw-bold text-dark mb-1">Quote Request TF-BQ-<span id="bulk-ref-num">8921</span> Submitted!</h4>
          <p class="text-13 text-gray-600 mb-3">Thank you for your inquiry. Our B2B commercial account manager has received your specifications and will respond with wholesale tier pricing within <strong>2 business hours</strong>.</p>
          <button type="button" class="btn btn-sm btn-outline-secondary rounded-pill px-4" id="btn-bulk-done">Close Window</button>
        </div>
      </div>
    `;

    document.body.appendChild(bulkModalBackdrop);

    bulkModalBackdrop.querySelector('.terai-generic-modal-close').addEventListener('click', closeBulkQuote);
    bulkModalBackdrop.addEventListener('click', (e) => {
      if (e.target === bulkModalBackdrop) closeBulkQuote();
    });

    const form = bulkModalBackdrop.querySelector('#bulk-quote-form');
    const successState = bulkModalBackdrop.querySelector('#bulk-success-state');
    const doneBtn = bulkModalBackdrop.querySelector('#btn-bulk-done');
    const refNum = bulkModalBackdrop.querySelector('#bulk-ref-num');

    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const randomRef = Math.floor(1000 + Math.random() * 9000);
      refNum.textContent = randomRef;
      form.style.display = 'none';
      successState.style.display = 'block';
      showToast('Wholesale Quote Requested', `Quote request #TF-BQ-${randomRef} submitted successfully!`, 'success');
    });

    doneBtn.addEventListener('click', () => {
      closeBulkQuote();
      setTimeout(() => {
        form.reset();
        form.style.display = 'block';
        successState.style.display = 'none';
      }, 300);
    });
  }

  function openBulkQuote() {
    if (!bulkModalBackdrop) initBulkQuoteModal();
    bulkModalBackdrop.classList.add('active');
  }

  function closeBulkQuote() {
    if (bulkModalBackdrop) bulkModalBackdrop.classList.remove('active');
  }

  // --- About Us Modal Logic ---
  let aboutModalBackdrop = null;
  function initAboutModal() {
    if (aboutModalBackdrop) return;
    aboutModalBackdrop = document.createElement('div');
    aboutModalBackdrop.className = 'terai-generic-modal-backdrop';
    aboutModalBackdrop.id = 'terai-about-modal';

    aboutModalBackdrop.innerHTML = `
      <div class="terai-generic-modal-dialog">
        <button type="button" class="terai-generic-modal-close" aria-label="Close about modal">
          <i class="klb-icon-x"></i>
        </button>
        <div class="text-center mb-3">
          <span class="badge" style="background: #eff6ff; color: #1547A8; font-weight: 700; padding: 5px 12px; border-radius: 20px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">Pure Organic &bull; Fresh Daily</span>
          <h3 class="text-20 fw-bold text-dark mt-2 mb-1">About Terai Food UK</h3>
          <p class="text-12 text-gray-500 mb-0">Bringing the authentic freshness of Himalayan &amp; organic farming to your British doorstep.</p>
        </div>

        <div class="bg-slate-50 p-3 rounded-3 border mb-3 text-13 text-gray-700 lh-base">
          <p class="mb-2"><strong>Terai Food</strong> was founded with a single mission: to deliver authentic, nutrient-rich organic groceries, exotic vegetables, and authentic spices without lengthy transit times or compromised quality.</p>
          <p class="mb-0">Working directly with certified organic growers and cold-chain UK distribution networks, we guarantee your produce arrives fresh, crisp, and bursting with natural flavor.</p>
        </div>

        <div class="d-flex flex-column gap-2 mb-3">
          <div class="d-flex align-items-center gap-2 text-13 text-dark">
            <i class="klb-icon-check text-success"></i>
            <span><strong>100% Guaranteed Freshness:</strong> Eco-chilled cold packs for transit</span>
          </div>
          <div class="d-flex align-items-center gap-2 text-13 text-dark">
            <i class="klb-icon-check text-success"></i>
            <span><strong>Next-Day UK Delivery:</strong> Operating 7 days a week from 7:00 to 23:00</span>
          </div>
          <div class="d-flex align-items-center gap-2 text-13 text-dark">
            <i class="klb-icon-check text-success"></i>
            <span><strong>B2C &amp; B2B Wholesale:</strong> Trusted by 25,000+ UK households &amp; restaurants</span>
          </div>
        </div>

        <div class="text-center pt-2">
          <button type="button" class="btn btn-primary rounded-pill px-4 text-13" id="btn-about-close" style="background: #1547A8; border-color: #1547A8;">Start Shopping Groceries</button>
        </div>
      </div>
    `;

    document.body.appendChild(aboutModalBackdrop);
    aboutModalBackdrop.querySelector('.terai-generic-modal-close').addEventListener('click', closeAboutModal);
    aboutModalBackdrop.querySelector('#btn-about-close').addEventListener('click', closeAboutModal);
    aboutModalBackdrop.addEventListener('click', (e) => {
      if (e.target === aboutModalBackdrop) closeAboutModal();
    });
  }

  function openAboutModal() {
    if (!aboutModalBackdrop) initAboutModal();
    aboutModalBackdrop.classList.add('active');
  }

  function closeAboutModal() {
    if (aboutModalBackdrop) aboutModalBackdrop.classList.remove('active');
  }

  // --- Blogs Modal Logic ---
  let blogModalBackdrop = null;
  function initBlogModal() {
    if (blogModalBackdrop) return;
    blogModalBackdrop = document.createElement('div');
    blogModalBackdrop.className = 'terai-generic-modal-backdrop';
    blogModalBackdrop.id = 'terai-blog-modal';

    blogModalBackdrop.innerHTML = `
      <div class="terai-generic-modal-dialog">
        <button type="button" class="terai-generic-modal-close" aria-label="Close blog modal">
          <i class="klb-icon-x"></i>
        </button>
        <div class="mb-3">
          <span class="badge" style="background: #ecfdf5; color: #059669; font-weight: 700; padding: 4px 10px; border-radius: 12px; font-size: 11px;">Food Journal</span>
          <h3 class="text-20 fw-bold text-dark mt-2 mb-1">Terai Food &bull; Recipes &amp; Living</h3>
          <p class="text-12 text-gray-500 mb-0">Organic cooking inspirations, health secrets &amp; harvest stories</p>
        </div>

        <div class="terai-blog-card">
          <img src="/static/web/images/1-16-150x150.jpg" alt="Organic spices" class="terai-blog-img">
          <div>
            <span class="text-11 text-gray-400 d-block mb-1">Recipes &bull; 5 min read</span>
            <h5 class="text-14 fw-bold text-dark mb-1">10 Authentic Himalayan &amp; Terai Spices For Hearty Cooking</h5>
            <p class="text-12 text-gray-600 mb-0">Discover the immune-boosting power of organic cumin, fenugreek, and cold-pressed mustard oil...</p>
          </div>
        </div>

        <div class="terai-blog-card">
          <img src="/static/web/images/1-30-150x150.jpg" alt="Fresh Greens" class="terai-blog-img">
          <div>
            <span class="text-11 text-gray-400 d-block mb-1">Quality &bull; 4 min read</span>
            <h5 class="text-14 fw-bold text-dark mb-1">Cold-Chain Secrets: How We Keep Groceries Fresh in the UK</h5>
            <p class="text-12 text-gray-600 mb-0">A look behind the curtain at our biodegradable thermal insulated delivery boxes...</p>
          </div>
        </div>

        <div class="terai-blog-card">
          <img src="/static/web/images/1-12-150x150.jpg" alt="Citrus Juice" class="terai-blog-img">
          <div>
            <span class="text-11 text-gray-400 d-block mb-1">Nutrition &bull; 6 min read</span>
            <h5 class="text-14 fw-bold text-dark mb-1">5 High-Protein Organic Lentil Dhal Bowls for Autumn</h5>
            <p class="text-12 text-gray-600 mb-0">Simple 20-minute vegetarian dinners that nourish the soul and taste restaurant-grade...</p>
          </div>
        </div>

        <div class="text-center pt-2">
          <button type="button" class="btn btn-outline-secondary rounded-pill px-4 text-13" id="btn-blog-close">Back to Store</button>
        </div>
      </div>
    `;

    document.body.appendChild(blogModalBackdrop);
    blogModalBackdrop.querySelector('.terai-generic-modal-close').addEventListener('click', closeBlogModal);
    blogModalBackdrop.querySelector('#btn-blog-close').addEventListener('click', closeBlogModal);
    blogModalBackdrop.addEventListener('click', (e) => {
      if (e.target === blogModalBackdrop) closeBlogModal();
    });
  }

  function openBlogModal() {
    if (!blogModalBackdrop) initBlogModal();
    blogModalBackdrop.classList.add('active');
  }

  function closeBlogModal() {
    if (blogModalBackdrop) blogModalBackdrop.classList.remove('active');
  }

  // --- Contact Modal Logic ---
  let contactModalBackdrop = null;
  function initContactModal() {
    if (contactModalBackdrop) return;
    contactModalBackdrop = document.createElement('div');
    contactModalBackdrop.className = 'terai-generic-modal-backdrop';
    contactModalBackdrop.id = 'terai-contact-modal';

    contactModalBackdrop.innerHTML = `
      <div class="terai-generic-modal-dialog">
        <button type="button" class="terai-generic-modal-close" aria-label="Close contact modal">
          <i class="klb-icon-x"></i>
        </button>
        <div class="d-flex align-items-center gap-3 mb-3">
          <div style="width: 44px; height: 44px; border-radius: 10px; background: #eff6ff; color: #1547A8; display: flex; align-items: center; justify-content: center; font-size: 22px; flex-shrink: 0;">
            <i class="klb-icon-map-pin"></i>
          </div>
          <div>
            <h4 class="text-18 fw-bold text-dark mb-0">Contact Terai Food UK</h4>
            <p class="text-12 text-gray-500 mb-0">Customer support &amp; wholesale inquiries 7 days a week</p>
          </div>
        </div>

        <div class="row g-2 mb-3">
          <div class="col-sm-6">
            <div class="p-3 bg-slate-50 rounded-3 border h-100">
              <span class="text-11 text-gray-400 d-block mb-1">Customer Helpline</span>
              <strong class="text-14 text-dark d-block mb-1">+44 (0) 20 7946 0991</strong>
              <p class="text-11 text-gray-500 mb-0">Mon – Sun: 07:00 – 23:00</p>
            </div>
          </div>
          <div class="col-sm-6">
            <div class="p-3 bg-slate-50 rounded-3 border h-100">
              <span class="text-11 text-gray-400 d-block mb-1">Email Support</span>
              <strong class="text-14 text-dark d-block mb-1">support@teraifood.co.uk</strong>
              <p class="text-11 text-gray-500 mb-0">Fast response within 30 mins</p>
            </div>
          </div>
        </div>

        <form id="contact-quick-form" class="mb-2">
          <div class="bulk-form-grid mb-2">
            <div>
              <label class="bulk-form-label">Your Name</label>
              <input type="text" class="bulk-form-input" placeholder="Full name" required>
            </div>
            <div>
              <label class="bulk-form-label">Email or Phone</label>
              <input type="text" class="bulk-form-input" placeholder="Your contact detail" required>
            </div>
          </div>
          <div class="mb-3">
            <label class="bulk-form-label">How can we help you today?</label>
            <textarea class="bulk-form-textarea" rows="2" placeholder="Ask about an order, product inquiry, or UK delivery..." required></textarea>
          </div>
          <button type="submit" class="btn btn-primary w-100 py-2 rounded-2 text-14 fw-bold" style="background: #1547A8; border-color: #1547A8;">
            Send Inquiry Message
          </button>
        </form>
      </div>
    `;

    document.body.appendChild(contactModalBackdrop);
    contactModalBackdrop.querySelector('.terai-generic-modal-close').addEventListener('click', closeContactModal);
    contactModalBackdrop.addEventListener('click', (e) => {
      if (e.target === contactModalBackdrop) closeContactModal();
    });

    contactModalBackdrop.querySelector('#contact-quick-form').addEventListener('submit', (e) => {
      e.preventDefault();
      closeContactModal();
      showToast('Message Received', 'Thank you! A customer care representative will contact you shortly.', 'success');
    });
  }

  function openContactModal() {
    if (!contactModalBackdrop) initContactModal();
    contactModalBackdrop.classList.add('active');
  }

  function closeContactModal() {
    if (contactModalBackdrop) contactModalBackdrop.classList.remove('active');
  }

  // Authentication lives on the server. Discard obsolete demo identity state.
  try {
    localStorage.removeItem('terai_auth_user_session');
    localStorage.removeItem('teraifood_auth_user');
  } catch (error) {}
  // If loaded inside an auth iframe (e.g. from an auth redirect to storefront), notify parent immediately
  if (window.self !== window.top) {
    try {
      window.parent.postMessage({ type: 'terai-auth-complete', next: '/manage-profile/' }, window.location.origin);
    } catch (e) {}
  }

  function isUserAuthenticated() {
    const meta = document.querySelector('meta[name="customer-authenticated"]');
    if (meta) {
      if (meta.content === 'true') return true;
      if (meta.content === 'false') return false;
    }
    if (/(?:^|;\s*)terai_customer_logged_in=1/.test(document.cookie)) {
      return true;
    }
    const loginBtns = document.querySelectorAll('.login-form-button, .header-account, .user');
    for (const btn of loginBtns) {
      if (btn.textContent && /my account/i.test(btn.textContent)) {
        return true;
      }
    }
    return false;
  }

  let accountDialog;
  let accountFrame;
  let accountReturnFocus;
  let previousBodyOverflow;
  function closeLoginModal() {
    if (!accountDialog?.open) return;
    accountDialog.close();
  }
  function openLoginModal() {
    if (isUserAuthenticated()) {
      window.location.assign('/manage-profile/');
      return;
    }
    accountReturnFocus = document.activeElement;
    if (!accountDialog) {
      const style = document.createElement('style');
      style.textContent = '#terai-account-dialog{width:360px;max-width:calc(100vw - 24px);max-height:calc(100dvh - 32px);padding:0;border:0;border-radius:0;background:#fff;box-shadow:0 15px 55px #0003;overflow:hidden}#terai-account-dialog::backdrop{background:rgba(15,23,42,.48)}#terai-account-dialog iframe{display:block;width:100%;height:440px;max-height:calc(100dvh - 32px);border:0;background:#fff}';
      document.head.append(style);
      accountDialog = document.createElement('dialog');
      accountDialog.id = 'terai-account-dialog';
      accountDialog.setAttribute('aria-label', 'Terai Food account');
      accountFrame = document.createElement('iframe');
      accountFrame.title = 'Sign in or create your Terai Food account';
      accountDialog.append(accountFrame);
      document.body.append(accountDialog);
      accountDialog.addEventListener('click', event => {
        if (event.target !== accountDialog) return;
        const bounds = accountDialog.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) closeLoginModal();
      });
      accountDialog.addEventListener('close', () => {
        document.body.style.overflow = previousBodyOverflow;
        accountReturnFocus?.focus();
        accountFrame.src = 'about:blank';
      });
      window.addEventListener('message', event => {
        if (event.origin !== window.location.origin || event.source !== accountFrame.contentWindow || !accountDialog.open) return;
        if (event.data?.type === 'terai-auth-close') closeLoginModal();
        if (event.data?.type === 'terai-auth-size' && Number.isFinite(event.data.height)) {
          accountFrame.style.height = Math.max(160, Math.min(event.data.height, window.innerHeight - 32)) + 'px';
        }
        if (event.data?.type === 'terai-auth-complete') {
          closeLoginModal();
          const target = event.data?.next || '/';
          window.location.assign(target);
        }
      });
    }
    if (accountDialog.open) return;
    previousBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    accountFrame.src = '/accounts/login/';
    accountDialog.showModal();
    accountFrame.focus();
  }
  window.teraiOpenLoginModal = openLoginModal;
  window.teraiCloseLoginModal = closeLoginModal;
  window.teraiShowToast = showToast;

  // --- Global Navigation & Anchor Interceptors ---
  function setupNavigationInterceptors() {
    // 1. Header Mini-Cart Button & Cart links -> Open Unified Commerce Modal (Step 1: Basket)
    document.querySelectorAll('.mini-cart-button, .header-cart, .quick-button.mini-cart-button, a[href="/cart/"], a[href="/cart/"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        openSideCart(1);
      });
    });

    // Mobile bottom bar Store button -> Refresh homepage on click if already on home
    document.querySelectorAll('.site-mobile-navbar a.store, #mobile-nav-store').forEach(link => {
      link.addEventListener('click', (e) => {
        if (window.location.pathname === '/' || window.location.pathname === '') {
          e.preventDefault();
          window.location.reload();
        }
      });
    });

    // User profile and authentication handling:
    // If logged in -> navigate straight to /manage-profile/
    // If not logged in -> open login modal
    document.querySelectorAll('.login-form-button, .user, .header-account, [data-modal="login"]').forEach(button => {
      button.addEventListener('click', event => {
        event.preventDefault();
        event.stopPropagation();
        if (isUserAuthenticated()) {
          window.location.assign('/manage-profile/');
          return;
        }
        openLoginModal();
      });
    });

    // 1b. Wishlist Drawer triggers: Open Wishlist Sidebar Drawer (440px wide)
    document.querySelectorAll('.wishlist-button, .wishlist-button a, a[href="#wishlist"], .wishlist, .header-wishlist, [data-drawer="wishlist"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        openWishlistDrawer();
      });
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeSideCart();
        closeWishlistDrawer();
        closeLoginModal();
      }
    });

        // 2. Cart Side Close & Overlay (Direct & Delegated)
    document.addEventListener('click', (e) => {
      if (e.target.closest('#drawer-close-btn, .cart-side-close, .cart-side-close-btn, [data-drawer-close]')) {
        e.preventDefault();
        e.stopPropagation();
        closeSideCart();
      }
      if (e.target.matches('.cart-side-overlay, #cart-side-overlay')) {
        e.preventDefault();
        e.stopPropagation();
        closeSideCart();
      }
      if (e.target.closest('.authentication-modal .site-close, [data-modal-close="login"]')) {
        e.preventDefault();
        e.stopPropagation();
        closeLoginModal();
      }
      if (e.target.matches('.authentication-modal .site-drawer-overlay, .authentication-modal.is-active')) {
        e.preventDefault();
        e.stopPropagation();
        closeLoginModal();
      }
    });

    // Original Direct Listeners
// 2. Cart Side Close & Overlay
    document.querySelector('.cart-widget-side .cart-side-close')?.addEventListener('click', (e) => {
      e.preventDefault();
      closeSideCart();
    });

    document.querySelector('.cart-side-overlay')?.addEventListener('click', (e) => {
      e.preventDefault();
      closeSideCart();
    });

    // 3. Checkout links -> Open Unified Commerce Modal (Step 2: Delivery & Shipping)
    document.querySelectorAll('a[href*="checkout"], .checkout-button, .button.checkout, .terai-btn-checkout').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        openSideCart(2);
      });
    });

    // 3b. Order Payment links -> Open Unified Commerce Modal (Step 3: Payment Method)
    document.querySelectorAll('a[href="/payment/"], a[href*="/payment/"], .order-payment-button, .btn-pay-now').forEach(link => {
      // Exclude profile/account tab links and in-page anchor links
      if (link.hasAttribute('data-account-tab') || link.classList.contains('account-sub-nav-link') || link.getAttribute('href')?.startsWith('#') || link.closest('.account-dashboard-wrapper') || link.closest('.account-sidebar-card')) {
        return;
      }
      link.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        openSideCart(3);
      });
    });

    // 4. Bulk Order >> Request Quote links: navigate to dedicated bulk-order.html procurement page
    document.querySelectorAll('#nav-bulk-order-btn, #btn-bulk-order, #promo-bulk-quote-btn, a[href="#bulk-order"], a[href="#bulk-quote"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        if (btn.getAttribute('href') === '/bulk-order/') return;
        e.preventDefault();
        e.stopPropagation();
        window.location.href = '/bulk-order/';
      });
    });

    // 5. About Us links: allow direct navigation to about.html page (fallback modal only if href is exactly "#about")
    document.querySelectorAll('a[href="#about"]:not([href="/about/"])').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        window.location.href = '/about/';
      });
    });

    // 6. Blogs links: allow direct navigation to blogs.html page
    document.querySelectorAll('a[href="#blog"]:not([href="/blogs/"]), a[href="#blogs"]:not([href="/blogs/"])').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        window.location.href = '/blogs/';
      });
    });

    // 7. Contact links: allow direct navigation to contact.html page
    document.querySelectorAll('a[href="#contact"]:not([href="/contact/"])').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        window.location.href = '/contact/';
      });
    });

    // 8. Clean up dead '#' links
    document.querySelectorAll('a[href="#"], a[href=""], a[href="#!"]').forEach(link => {
      link.addEventListener('click', (e) => {
        // Only prevent if no existing onclick or interactive role
        if (!link.getAttribute('data-modal') &&
            !link.getAttribute('data-drawer') &&
            !link.classList.contains('menu-drawer-toggle') &&
            !link.classList.contains('modal-button') &&
            link.getAttribute('href') !== '#wishlist') {
          e.preventDefault();
        }
      });
    });

    // 9. ESC key handler
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeSideCart();
        closeWishlistDrawer();
        closeSideCart();
        closeQuickview();
        closeOrderTracking();
        closeBulkQuote();
        closeAboutModal();
        closeBlogModal();
        closeContactModal();
        document.getElementById('location-selector')?.classList.remove('active');
      }
    });
  }

  // --- Clients Testimonials Slider ---
  function setupTestimonialsSlider() {
    const track = document.getElementById('testimonials-track');
    const wrapper = document.getElementById('testimonials-carousel-wrapper');
    const prevBtn = document.getElementById('testimonial-prev-btn');
    const nextBtn = document.getElementById('testimonial-next-btn');
    const dotsContainer = document.getElementById('testimonials-dots-container');
    const slides = Array.from(document.querySelectorAll('.testimonial-slide-item'));

    if (!track || slides.length === 0) return;

    let currentIndex = 0;
    let autoSlideTimer = null;
    let isHovered = false;

    function getVisibleCount() {
      const w = window.innerWidth;
      if (w >= 1200) return 4;
      if (w >= 860) return 3;
      if (w >= 576) return 2;
      return 1;
    }

    function getMaxIndex() {
      return Math.max(0, slides.length - getVisibleCount());
    }

    function getSlideStepWidth() {
      if (slides.length < 2) return track.clientWidth;
      const r0 = slides[0].getBoundingClientRect();
      const r1 = slides[1].getBoundingClientRect();
      return r1.left - r0.left;
    }

    function updateDots() {
      if (!dotsContainer) return;
      const dots = dotsContainer.querySelectorAll('.testimonial-dot');
      dots.forEach((dot, idx) => {
        if (idx === currentIndex) {
          dot.classList.add('active');
        } else {
          dot.classList.remove('active');
        }
      });
    }

    function goToSlide(index, smooth = true) {
      const maxIdx = getMaxIndex();
      if (index < 0) {
        currentIndex = maxIdx;
      } else if (index > maxIdx) {
        currentIndex = 0;
      } else {
        currentIndex = index;
      }

      const step = getSlideStepWidth();
      track.style.transition = smooth ? 'transform 0.45s cubic-bezier(0.22, 1, 0.36, 1)' : 'none';
      track.style.transform = `translateX(-${currentIndex * step}px)`;
      updateDots();
    }

    function nextSlide() {
      goToSlide(currentIndex + 1);
    }

    function prevSlide() {
      goToSlide(currentIndex - 1);
    }

    if (nextBtn) {
      nextBtn.addEventListener('click', (e) => {
        e.preventDefault();
        nextSlide();
        resetAutoTimer();
      });
    }

    if (prevBtn) {
      prevBtn.addEventListener('click', (e) => {
        e.preventDefault();
        prevSlide();
        resetAutoTimer();
      });
    }

    if (dotsContainer) {
      dotsContainer.addEventListener('click', (e) => {
        const dot = e.target.closest('.testimonial-dot');
        if (dot) {
          const idx = parseInt(dot.getAttribute('data-index'), 10);
          if (!isNaN(idx)) {
            goToSlide(idx);
            resetAutoTimer();
          }
        }
      });
    }

    // Auto-sliding every 3.5 seconds
    function startAutoTimer() {
      stopAutoTimer();
      autoSlideTimer = setInterval(() => {
        if (!isHovered) {
          nextSlide();
        }
      }, 3500);
    }

    function stopAutoTimer() {
      if (autoSlideTimer) {
        clearInterval(autoSlideTimer);
        autoSlideTimer = null;
      }
    }

    function resetAutoTimer() {
      startAutoTimer();
    }

    const moduleContainer = document.querySelector('.testimonials-module, .testimonials-slider-module');
    if (moduleContainer) {
      moduleContainer.addEventListener('mouseenter', () => {
        isHovered = true;
      });
      moduleContainer.addEventListener('mouseleave', () => {
        isHovered = false;
      });
    }

    // Touch & Mouse Dragging Support
    let startX = 0;
    let isDragging = false;

    if (wrapper) {
      wrapper.addEventListener('touchstart', (e) => {
        startX = e.touches[0].clientX;
        isDragging = true;
        isHovered = true;
      }, { passive: true });

      wrapper.addEventListener('touchend', (e) => {
        if (!isDragging) return;
        isDragging = false;
        isHovered = false;
        const endX = e.changedTouches[0].clientX;
        const diff = endX - startX;
        if (diff < -40) {
          nextSlide();
        } else if (diff > 40) {
          prevSlide();
        }
        resetAutoTimer();
      });

      let pointerStartX = 0;
      let pointerDown = false;

      wrapper.addEventListener('mousedown', (e) => {
        pointerStartX = e.clientX;
        pointerDown = true;
      });

      window.addEventListener('mouseup', (e) => {
        if (!pointerDown) return;
        pointerDown = false;
        const diff = e.clientX - pointerStartX;
        if (diff < -50) {
          nextSlide();
          resetAutoTimer();
        } else if (diff > 50) {
          prevSlide();
          resetAutoTimer();
        }
      });
    }

    // Handle window resize
    window.addEventListener('resize', () => {
      goToSlide(currentIndex, false);
    });

    goToSlide(0, false);
    startAutoTimer();
  }

  // --- Universal Categories Dropdown Menu ---
  const GLOBAL_CATEGORIES_HTML = `
    <nav class="site-categories collapse">
      <ul id="category-menu" class="menu">
        <li class="menu-item menu-item-has-children"><a href="/shop/"><img src="/static/web/images/apple.svg" alt="">Fruits &amp; Vegetables</a>
          <ul class="sub-menu">
            <li><a href="/shop/">Cuts &amp; Sprouts</a></li>
            <li><a href="/shop/">Exotic Fruits &amp; Veggies</a></li>
            <li><a href="/shop/">Fresh Fruits</a></li>
            <li><a href="/shop/">Fresh Vegetables</a></li>
            <li><a href="/shop/">Herbs &amp; Seasonings</a></li>
            <li><a href="/shop/">Packaged Produce</a></li>
            <li><a href="/shop/">Party Trays</a></li>
          </ul>
        </li>
        <li class="menu-item menu-item-has-children"><a href="/shop/"><img src="/static/web/images/meat.svg" alt="">Meats &amp; Seafood</a>
          <ul class="sub-menu">
            <li><a href="/shop/">Beef Products</a></li>
            <li><a href="/shop/">Chicken and Turkey Products</a></li>
            <li><a href="/shop/">Fish Varieties</a></li>
            <li><a href="/shop/">Lamb Products</a></li>
            <li><a href="/shop/">Processed Red Meat Products</a></li>
            <li><a href="/shop/">Seafood</a></li>
          </ul>
        </li>
        <li class="menu-item menu-item-has-children"><a href="/shop/"><img src="/static/web/images/boiled-egg.svg" alt="">Breaksfast &amp; Dairy</a>
          <ul class="sub-menu">
            <li><a href="/shop/">Breads and Cereal Products</a></li>
            <li><a href="/shop/">Breakfast Cereals and Bars</a></li>
            <li><a href="/shop/">Butter &amp; Margarine</a></li>
            <li><a href="/shop/">Cereals and Granolas</a></li>
            <li><a href="/shop/">Cheese Varieties</a></li>
            <li><a href="/shop/">Dairy Processing Products</a></li>
            <li><a href="/shop/">Eggs and Egg Products</a></li>
            <li><a href="/shop/">Fresh Dairy Products</a></li>
          </ul>
        </li>
        <li class="menu-item menu-item-has-children"><a href="/shop/"><img src="/static/web/images/toast-bread.svg" alt="">Breads &amp; Bakery</a>
          <ul class="sub-menu">
            <li><a href="/shop/">Bakery Pastries and Rolls</a></li>
            <li><a href="/shop/">Fresh Bread Varieties</a></li>
            <li><a href="/shop/">Glazed and Filled Products</a></li>
            <li><a href="/shop/">Gluten-Free Alternatives</a></li>
            <li><a href="/shop/">Organic and Natural Breads</a></li>
            <li><a href="/shop/">Pizza and Flatbreads</a></li>
            <li><a href="/shop/">Sandwich Bread and Wraps</a></li>
            <li><a href="/shop/">Sweets and Pastry Products</a></li>
          </ul>
        </li>
        <li class="menu-item menu-item-has-children"><a href="/shop/"><img src="/static/web/images/cup.svg" alt="">Beverages</a>
          <ul class="sub-menu">
            <li><a href="/shop/">Drink Boxes &amp; Pouches</a></li>
            <li><a href="/shop/">Coffee</a></li>
            <li><a href="/shop/">Craft Beer</a></li>
            <li><a href="/shop/">Milk &amp; Plant-Based Milk</a></li>
            <li><a href="/shop/">Soda &amp; Pop</a></li>
            <li><a href="/shop/">Sparkling Water</a></li>
          </ul>
        </li>
        <li class="menu-item"><a href="/shop/"><img src="/static/web/images/snowflake.svg" alt="">Frozen Foods</a></li>
        <li class="menu-item"><a href="/shop/"><img src="/static/web/images/bar.svg" alt="">Biscuits &amp; Snacks</a></li>
        <li class="menu-item"><a href="/shop/"><img src="/static/web/images/wheat.svg" alt="">Grocery &amp; Staples</a></li>
        <li class="menu-item"><a href="/shop/"><img src="/static/web/images/scoop.svg" alt="">Household Needs</a></li>
        <li class="menu-item"><a href="/shop/"><img src="/static/web/images/toilet-paper.svg" alt="">Healthcare</a></li>
        <li class="menu-item"><a href="/shop/"><img src="/static/web/images/baby-boy.svg" alt="">Baby &amp; Pregnancy</a></li>
      </ul>
    </nav>
  `;

  function setupGlobalCategoriesDropdown() {
    const isHomePage = document.body.classList.contains('home');
    const isShopPage = document.body.classList.contains('terai-shop-page') || window.location.pathname.includes('/shop/');

    document.querySelectorAll('.categories-menu').forEach(menu => {
      // On desktop shop page, categories are already permanently expanded in the left column (.shop-sidebar-categories)
      // Only inject site-categories on other pages or mobile shop
      let siteCat = menu.querySelector('.site-categories');
      if (!siteCat && (!isShopPage || window.innerWidth < 1200)) {
        menu.insertAdjacentHTML('beforeend', GLOBAL_CATEGORIES_HTML);
        siteCat = menu.querySelector('.site-categories');
      }

      const toggle = menu.querySelector('.categories-toggle');
      if (toggle) {
        toggle.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();

          // Close header user dropdown
          document.querySelectorAll('.header-user-dropdown').forEach(d => d.classList.remove('show'));

          // 1. HOME PAGE HANDLING
          if (isHomePage) {
            const isSticky = Boolean(menu.closest('.sticky-header'));
            if (!isSticky && window.innerWidth >= 1200) {
              // On desktop home page at the top, categories are already expanded next to the hero slider.
              // Smoothly scroll to the top without collapsing the banner layout.
              window.scrollTo({ top: 0, behavior: 'smooth' });
              return;
            }
            // If in sticky header or mobile, toggle floating dropdown
            if (siteCat) {
              const isOpen = menu.classList.contains('open') || siteCat.classList.contains('show');
              if (isOpen) {
                menu.classList.remove('open');
                siteCat.classList.remove('show');
              } else {
                menu.classList.add('open');
                siteCat.classList.add('show');
              }
            }
            return;
          }

          // 2. SHOP PAGE HANDLING
          if (isShopPage) {
            if (window.innerWidth >= 1200) {
              // On desktop shop page, categories are permanently expanded in the left column.
              // If scrolled down, smoothly scroll up to the top of shop categories.
              const shopMain = document.getElementById('main') || document.querySelector('.shop-main-layout');
              if (shopMain && window.scrollY > 150) {
                window.scrollTo({ top: shopMain.offsetTop - 50, behavior: 'smooth' });
              }
              const sidebar = document.querySelector('.shop-sidebar-categories');
              if (sidebar) {
                sidebar.style.transition = 'box-shadow 0.25s ease';
                sidebar.style.boxShadow = '0 0 0 2px #1547A8';
                setTimeout(() => { sidebar.style.boxShadow = ''; }, 1200);
              }
              return;
            } else {
              // On mobile/tablet shop page (< 1200px), toggle mobile categories dropdown
              if (!siteCat) {
                menu.insertAdjacentHTML('beforeend', GLOBAL_CATEGORIES_HTML);
                siteCat = menu.querySelector('.site-categories');
              }
              if (siteCat) {
                siteCat.classList.toggle('show');
                menu.classList.toggle('open');
              }
              return;
            }
          }

          // 3. ALL OTHER PAGES (Track Order, Blogs, Supports, Bulk Order, Manage Profile, Cart, Checkout, etc.)
          if (!siteCat) {
            menu.insertAdjacentHTML('beforeend', GLOBAL_CATEGORIES_HTML);
            siteCat = menu.querySelector('.site-categories');
          }
          if (siteCat) {
            const isOpen = menu.classList.contains('open') || siteCat.classList.contains('show');
            if (isOpen) {
              menu.classList.remove('open');
              siteCat.classList.remove('show');
            } else {
              // Close any other open categories menus
              document.querySelectorAll('.categories-menu.open').forEach(other => {
                other.classList.remove('open');
                other.querySelector('.site-categories')?.classList.remove('show');
              });
              menu.classList.add('open');
              siteCat.classList.add('show');
            }
          }
        });
      }
    });

    // Close on click outside
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.categories-menu')) {
        document.querySelectorAll('.categories-menu.open').forEach(menu => {
          menu.classList.remove('open');
          menu.querySelector('.site-categories')?.classList.remove('show');
        });
        if (!isHomePage) {
          document.querySelectorAll('.header-nav .site-categories.show').forEach(s => s.classList.remove('show'));
        } else {
          // On home sticky header, close dropdown
          document.querySelectorAll('.sticky-header .categories-menu .site-categories.show').forEach(s => s.classList.remove('show'));
        }
      }
    });
  }

  // --- Initializer ---
  function init() {
    indexProducts();
    initQuickviewModal();
    initWishlistDrawer();
    initSideCartDrawer();
    setupProductCardSteppers();
    setupProductCardClicks();
    setupLiveSearch();
    setupCategoryFiltering();
    setupLocationModal();
    setupCurrencySelector();
    setupOrderTracking();
    setupNavigationInterceptors();
    setupGlobalCategoriesDropdown();
    setupTestimonialsSlider();
    updateCartUI();
    updateWishlistUI();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();

