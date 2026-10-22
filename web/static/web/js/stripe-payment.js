/* Stripe owns all payment fields; client secrets live only in this closure. */
(() => {
  let scriptPromise, mounted, serial = 0, confirming = false;
  const loadStripe = () => {
    if (window.Stripe) return Promise.resolve();
    if (!scriptPromise) scriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://js.stripe.com/dahlia/stripe.js';
      const timer = setTimeout(() => { script.remove(); scriptPromise = null; reject(new Error('Payment form could not load. Please retry.')); }, 20000);
      script.onload = () => { clearTimeout(timer); resolve(); };
      script.onerror = () => { clearTimeout(timer); script.remove(); scriptPromise = null; reject(new Error('Payment form could not load. Please retry.')); };
      document.head.append(script);
    });
    return scriptPromise;
  };
  function reset() {
    serial++;
    mounted?.payment?.destroy();
    mounted?.express?.destroy();
    mounted = null;
  }
  async function confirm(expressEvent) {
    if (confirming || !mounted?.actions) return;
    confirming = true;
    const current = mounted;
    current.message.textContent = 'Checking payment…';
    const confirmBtn = document.getElementById('btn-drawer-confirm-pay') || document.getElementById('btn-final-pay');
    const originalBtnText = confirmBtn ? confirmBtn.textContent : '';
    if (confirmBtn) {
      confirmBtn.disabled = true;
      confirmBtn.textContent = 'Processing Payment…';
    }
    try {
      const order = await window.TeraiOrders.api(`/api/orders/${current.orderId}/payment-status/`, {});
      if (order.payment_status === 'paid' || order.payment_status === 'refunded') {
        location.assign('/track-order/?order=' + current.orderId); return;
      }
      if (order.fulfilment_status !== 'pending_payment' || order.cancellation_status !== 'none') throw new Error('This order is no longer payable. Check its status before trying again.');
      const result = await current.actions.confirm({redirect: 'if_required',
        ...(expressEvent ? {expressCheckoutConfirmEvent: expressEvent} : {})});
      if (result.type === 'error') throw new Error(result.error.message);
      current.message.textContent = 'Payment submitted. Verifying your order…';
      current.message.style.display = 'block';
      current.message.style.background = '#f0fdf4';
      current.message.style.border = '1px solid #bbf7d0';
      current.message.style.color = '#166534';
      // A browser success is never used to mark an order paid.
      await window.TeraiOrders.api(`/api/orders/${current.orderId}/payment-status/`, {});
      location.assign('/track-order/?order=' + current.orderId);
    } catch (error) {
      current.message.textContent = error.message;
      current.message.style.display = 'block';
      current.message.style.background = '#fef2f2';
      current.message.style.border = '1px solid #fecaca';
      current.message.style.color = '#b91c1c';
      if (window.TeraiCatalog?.showToast) {
        window.TeraiCatalog.showToast('Payment Issue', error.message, 'warning');
      }
    } finally {
      confirming = false;
      if (confirmBtn) {
        confirmBtn.disabled = false;
        confirmBtn.textContent = originalBtnText;
      }
    }
  }
  async function mount(root, data) {
    reset();
    const version = serial;
    root.innerHTML = '<p role="status">Loading secure payment form…</p>';
    await loadStripe();
    if (version !== serial) return;
    const stripe = window.Stripe(data.publishable_key);
    const checkout = stripe.initCheckoutElementsSdk({clientSecret: data.client_secret,
      elementsOptions: {loader: 'auto', savedPaymentMethod: {enableSave: 'never', enableRedisplay: 'never'},
        appearance: {theme: 'stripe', variables: {colorPrimary: '#634c9f', colorText: '#0f172a',
          fontFamily: 'Arial, sans-serif', borderRadius: '0px', fontSizeBase: '14px'}}}});
    const loaded = await checkout.loadActions();
    if (version !== serial) return;
    if (loaded.type === 'error') throw new Error(loaded.error.message);
    root.innerHTML = '<div data-stripe-express></div><div data-stripe-payment></div><p data-stripe-total class="text-13 fw-bold mt-2"></p><p data-stripe-message role="status" aria-live="polite" style="margin-top: 10px; padding: 8px 12px; font-size: 12px; font-weight: 600; border-radius: 4px; display: none;"></p>';
    const message = root.querySelector('[data-stripe-message]');
    const update = session => { root.querySelector('[data-stripe-total]').textContent = 'Total to pay: ' + session.total.total.amount; };
    update(loaded.actions.getSession());
    checkout.on('change', session => { if (version === serial) update(session); });
    const payment = checkout.createPaymentElement({layout: 'accordion'});
    const express = checkout.createExpressCheckoutElement();
    mounted = {actions: loaded.actions, payment, express, message, orderId: data.order_id};
    payment.on('loaderror', () => { message.textContent = 'Payment form could not load. Please retry or reopen payment.'; });
    express.on('confirm', event => confirm(event));
    express.mount(root.querySelector('[data-stripe-express]'));
    payment.mount(root.querySelector('[data-stripe-payment]'));
    message.textContent = 'Test payment. Payment details are securely collected by Stripe.';
  }
  window.TeraiEmbeddedPayment = {mount, reset, confirm, get ready() { return !!mounted?.actions; }};
  window.addEventListener('pagehide', reset);
})();
