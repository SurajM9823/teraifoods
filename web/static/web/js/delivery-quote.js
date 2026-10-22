/* Update existing summary text only; shipping amounts always come from Django. */
(() => {
  let key = '', requestedAt = 0, controller, timer;
  window.addEventListener('delivery:request', event => {
    const items = event.detail || [];
    const voucher=window.TeraiOrders?.voucherPayload?.()||{};
    const next = JSON.stringify([items.map(i => [String(i.id), Number(i.quantity)]).sort(),voucher]);
    if (next === key && Date.now() - requestedAt < 20000) return;
    key = next; requestedAt = Date.now();
    controller?.abort(); clearTimeout(timer);
    if (!items.length) return;
    timer = setTimeout(async () => {
      controller = new AbortController();
      try {
        const csrf = document.cookie.split('; ').find(v => v.startsWith('csrftoken='))?.slice('csrftoken='.length) ||
          document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
        const response = await fetch('/api/cart/quote/', {method:'POST', signal:controller.signal,
          headers:{'Content-Type':'application/json', 'X-CSRFToken':decodeURIComponent(csrf)},
          body:JSON.stringify({...voucher,items:items.map(i => ({product_id:Number(i.id), quantity:Number(i.quantity)})), country:'GB'})});
        const quote = await response.json();
        if (next !== key) return;
        if (response.ok) window.dispatchEvent(new CustomEvent('delivery:quote', {detail:{items, quote}}));
        else {
          window.dispatchEvent(new CustomEvent('delivery:quote', {detail:{items, quote:null}}));
          document.querySelectorAll('#drawer-shipping-val, #checkout-summary-delivery-fee, #checkout-delivery-price-text, #drawer-step3-shipping')
            .forEach(node => {node.textContent = 'Unavailable'; node.title = (quote.errors || []).join(' ');});
        }
      } catch (error) {
        if (error.name !== 'AbortError' && next === key)
          window.dispatchEvent(new CustomEvent('delivery:quote', {detail:{items, quote:null}}));
      }
    }, 200);
  });
})();
