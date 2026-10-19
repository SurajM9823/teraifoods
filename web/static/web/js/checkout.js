/**
 * Terai Food - Checkout Page Script
 * UK Address Lookup, Interactive Map Confirmation, & Order Handling
 */
document.addEventListener('DOMContentLoaded', function () {
  'use strict';

  // 1. Initialize Map on Checkout Page
  const checkoutMap = window.TeraiFoodMap.initUkMapInstance({
    containerId: 'checkout-delivery-map',
    postcodeInputId: 'checkout-postcode-input',
    houseInputId: 'checkout-house-input',
    cityInputId: 'checkout-city-input',
    statusId: 'checkout-lookup-status',
    badgeId: 'checkout-map-badge'
  });

  // Current location button on checkout
  const checkoutGeoBtn = document.getElementById('btn-checkout-geolocate');
  if (checkoutGeoBtn && checkoutMap) {
    checkoutGeoBtn.addEventListener('click', function (e) {
      e.preventDefault();
      checkoutMap.locateCurrentPosition();
    });
  }

  // Search button on checkout
  const checkoutSearchBtn = document.getElementById('btn-checkout-search-postcode');
  if (checkoutSearchBtn && checkoutMap) {
    checkoutSearchBtn.addEventListener('click', function (e) {
      e.preventDefault();
      const pc = document.getElementById('checkout-postcode-input').value.trim();
      if (pc) {
        checkoutMap.lookupPostcode(pc, true);
      }
    });
  }

  // 2. Shipping calculation & Order Summary
  let savedCart = [];
  try {
    const raw = localStorage.getItem('teraifood_cart');
    if (raw) savedCart = JSON.parse(raw);
  } catch (e) {}

  let subtotal = 8.78;
  if (savedCart && savedCart.length > 0) {
    subtotal = savedCart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    const orderItemsContainer = document.querySelector('.order-items-list');
    if (orderItemsContainer) {
      orderItemsContainer.innerHTML = savedCart.map(item => `
        <div class="order-item-row">
          <img src="${item.image}" alt="${item.title}" class="order-item-img">
          <div class="flex-fill">
            <h4 class="order-item-title">${item.title}</h4>
            <div class="order-item-meta">Qty: ${item.quantity} &bull; Fresh Batch</div>
          </div>
          <div class="order-item-price">&pound;${(item.price * item.quantity).toFixed(2)}</div>
        </div>
      `).join('');
    }
    const subtotalTextEl = document.querySelector('.totals-breakdown .text-dark');
    if (subtotalTextEl) subtotalTextEl.textContent = '£' + subtotal.toFixed(2);
  }

  let shippingCost = subtotal >= 50 ? 0.00 : 3.99;
  let discount = 0.00;

  function updateOrderTotals() {
    const total = Math.max(0, subtotal + shippingCost - discount);
    const shippingEl = document.getElementById('summary-shipping-cost');
    const totalEl = document.getElementById('summary-total-cost');
    const btnTotalEl = document.getElementById('btn-place-order-total');

    if (shippingEl) shippingEl.textContent = shippingCost === 0 ? 'FREE' : '£' + shippingCost.toFixed(2);
    if (totalEl) totalEl.textContent = '£' + total.toFixed(2);
    if (btnTotalEl) btnTotalEl.textContent = '£' + total.toFixed(2);
  }

  // Shipping method change
  const shippingRadios = document.querySelectorAll('input[name="shipping_method"]');
  shippingRadios.forEach(radio => {
    radio.addEventListener('change', function () {
      if (this.value === 'standard') {
        shippingCost = 3.99;
      } else if (this.value === 'express') {
        shippingCost = 5.99;
      } else if (this.value === 'click_collect') {
        shippingCost = 0.00;
      }
      updateOrderTotals();
    });
  });

  // Payment method selection visual styling
  const paymentOptions = document.querySelectorAll('.checkout-payment-option');
  paymentOptions.forEach(opt => {
    opt.addEventListener('click', function () {
      paymentOptions.forEach(o => o.classList.remove('selected'));
      this.classList.add('selected');
      const radio = this.querySelector('input[type="radio"]');
      if (radio) radio.checked = true;

      // Show/hide card details form
      const cardDetails = document.getElementById('credit-card-fields');
      if (cardDetails) {
        if (radio && radio.value === 'card') {
          cardDetails.style.display = 'block';
        } else {
          cardDetails.style.display = 'none';
        }
      }
    });
  });

  // Coupon code handler
  const couponBtn = document.getElementById('btn-apply-coupon');
  const couponInput = document.getElementById('coupon-input');
  const couponMsg = document.getElementById('coupon-message');

  if (couponBtn && couponInput) {
    couponBtn.addEventListener('click', function (e) {
      e.preventDefault();
      const code = couponInput.value.trim().toUpperCase();
      if (code === 'TERAI10' || code === 'GROCERY10') {
        discount = subtotal * 0.10;
        if (couponMsg) {
          couponMsg.textContent = '✓ Coupon applied: 10% discount (-£' + discount.toFixed(2) + ')';
          couponMsg.className = 'text-12 text-success mt-1 d-block';
        }
        document.getElementById('summary-discount-row').style.display = 'flex';
        document.getElementById('summary-discount-val').textContent = '-£' + discount.toFixed(2);
        updateOrderTotals();
      } else if (code) {
        if (couponMsg) {
          couponMsg.textContent = 'Invalid promo code. Use code TERAI10 for 10% off!';
          couponMsg.className = 'text-12 text-danger mt-1 d-block';
        }
      }
    });
  }

  // 3. Checkout Form Submission
  const checkoutForm = document.getElementById('teraifood-checkout-form');
  const successModal = document.getElementById('order-success-modal');

  if (checkoutForm) {
    checkoutForm.addEventListener('submit', function (e) {
      e.preventDefault();

      const fname = document.getElementById('checkout-fname').value.trim();
      const lname = document.getElementById('checkout-lname').value.trim();
      const email = document.getElementById('checkout-email').value.trim();
      const phone = document.getElementById('checkout-phone').value.trim();
      const postcode = document.getElementById('checkout-postcode-input').value.trim();
      const houseNumber = document.getElementById('checkout-house-input').value.trim();
      const city = document.getElementById('checkout-city-input').value.trim() || 'London';

      if (!postcode) {
        alert('Please enter your UK postcode for delivery confirmation.');
        document.getElementById('checkout-postcode-input').focus();
        return;
      }

      // Save confirmed address
      if (checkoutMap) {
        const details = checkoutMap.getDetails();
        window.TeraiFoodMap.saveAddress({
          ...details,
          isAll: false,
          label: details.houseNumber ? `${details.houseNumber}, ${details.postcode}` : details.postcode
        });
        window.TeraiFoodMap.updateHeaderDeliverTo(details.postcode);
      }

      // Generate random order ID
      const orderId = 'TF-' + Math.floor(100000 + Math.random() * 900000);
      const fullAddress = `${houseNumber ? houseNumber + ', ' : ''}${city}, ${postcode}`;

      document.getElementById('modal-order-id').textContent = '#' + orderId;
      document.getElementById('modal-delivery-to').textContent = fullAddress;
      document.getElementById('modal-customer-name').textContent = `${fname} ${lname}`;

      if (successModal) {
        localStorage.removeItem('teraifood_cart');
        successModal.classList.add('show');
      }
    });
  }

  // Close modal button
  const closeModalBtn = document.getElementById('btn-close-success-modal');
  if (closeModalBtn && successModal) {
    closeModalBtn.addEventListener('click', function () {
      successModal.classList.remove('show');
      window.location.href = '/';
    });
  }

  updateOrderTotals();
});

