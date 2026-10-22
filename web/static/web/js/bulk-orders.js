(() => {
  'use strict';
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const api = async (url, body, key) => {
    const csrf = decodeURIComponent(document.cookie.split('; ').find(c => c.startsWith('csrftoken='))?.slice(10) || '');
    const response = await fetch(url, {
      method: body ? 'POST' : 'GET',
      credentials: 'same-origin',
      cache: 'no-store',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf,
        ...(key ? { 'Idempotency-Key': key } : {})
      },
      ...(body ? { body: JSON.stringify(body) } : {})
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.errors?.join(' ') || 'Unable to load bulk request.');
    return result;
  };

  const form = document.getElementById('bulk-po-form');
  const message = document.getElementById('bulk-message');
  const list = document.getElementById('bulk-request-list');
  const feedback = document.getElementById('po-submit-feedback');
  const sideStatus = document.getElementById('side-save-status');
  if (!form) return;

  const value = id => (document.getElementById(id)?.value || '').trim();
  const STORAGE_KEY = 'terai_bulk_delivery_details';
  const UK_POSTCODE_REGEX = /([A-Z]{1,2}[0-9][A-Z0-9]?\s*[0-9][A-Z]{2})$/i;

  const say = (text, isError = false) => {
    if (!message) return;
    message.textContent = text;
    if (text) {
      message.className = isError ? 'alert alert-danger p-2 my-2 text-13' : 'alert alert-success p-2 my-2 text-13';
    } else {
      message.className = '';
    }
  };

  const showSubmitFeedback = (html, type = 'info') => {
    if (!feedback) return;
    feedback.innerHTML = html;
    feedback.className = `alert alert-${type} p-2 my-2 text-12 fw-semibold`;
    feedback.style.display = 'block';
  };

  const clearSubmitFeedback = () => {
    if (!feedback) return;
    feedback.innerHTML = '';
    feedback.style.display = 'none';
  };

  let pages = 1, busy = false;

  function getDeliveryData() {
    return {
      company: value('buyer-company-name'),
      contact_name: value('buyer-contact-name'),
      address: value('buyer-address'),
      city_postcode: value('buyer-city-postcode'),
      phone: value('buyer-phone-email'),
      email: value('buyer-email'),
      requested_date: value('po-delivery-date'),
      notes: value('buyer-notes')
    };
  }

  function validateDelivery(showUI = true) {
    const d = getDeliveryData();
    const clearBorders = () => {
      ['buyer-company-name', 'buyer-contact-name', 'buyer-address', 'buyer-city-postcode', 'buyer-phone-email', 'buyer-email', 'po-delivery-date'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.borderColor = '';
      });
    };

    const fail = (id, msg) => {
      if (showUI) {
        clearBorders();
        const el = document.getElementById(id);
        if (el) {
          el.style.borderColor = '#dc2626';
          el.focus();
        }
        if (sideStatus) {
          sideStatus.innerHTML = `<span style="color:#dc2626; font-weight:600;"><i class="klb-icon-alert-circle me-1"></i> ${esc(msg)}</span>`;
          sideStatus.style.display = 'block';
        }
      }
      return false;
    };

    if (!d.company) return fail('buyer-company-name', 'Please enter Company / Business name.');
    if (!d.contact_name) return fail('buyer-contact-name', 'Please enter Contact Person.');
    if (!d.address) return fail('buyer-address', 'Please enter Delivery Street Address.');
    if (!d.city_postcode) return fail('buyer-city-postcode', 'Please enter Town/City and UK Postcode.');

    const cleanPostcode = d.city_postcode.toUpperCase().trim();
    const pcMatch = cleanPostcode.match(UK_POSTCODE_REGEX);
    if (!pcMatch || pcMatch[1].startsWith('JE') || pcMatch[1].startsWith('GY') || pcMatch[1].startsWith('IM')) {
      return fail('buyer-city-postcode', 'Enter town/city and a valid UK postcode (e.g. London SW1A 1AA).');
    }

    const cleanPhone = d.phone.replace(/[\s().-]/g, '');
    if (!cleanPhone || !/^(?:\+44|0044|0)[0-9]{9,10}$/.test(cleanPhone)) {
      return fail('buyer-phone-email', 'Enter a valid UK contact number (e.g. 07700 900123).');
    }

    if (!d.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(d.email)) {
      return fail('buyer-email', 'Enter a valid contact email address.');
    }

    if (d.requested_date) {
      const today = new Date().toISOString().split('T')[0];
      if (d.requested_date < today) {
        return fail('po-delivery-date', 'Requested delivery date cannot be in the past.');
      }
    }

    clearBorders();
    return true;
  }

  window._doSaveDelivery = window.saveDeliveryDetails = () => {
    if (!validateDelivery(true)) return;

    const d = getDeliveryData();
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(d));
    } catch {}

    const saveBtn = document.getElementById('btn-save-delivery') || document.querySelector('.btn-po-side-save');
    if (saveBtn) {
      const originalHTML = saveBtn.innerHTML;
      saveBtn.innerHTML = '<i class="klb-icon-check" style="font-weight:900;"></i> Details Saved!';
      saveBtn.style.background = '#166534';
      saveBtn.style.borderColor = '#166534';
      setTimeout(() => {
        saveBtn.innerHTML = originalHTML;
        saveBtn.style.background = '';
        saveBtn.style.borderColor = '';
      }, 3000);
    }

    if (sideStatus) {
      sideStatus.innerHTML = '<div style="color:#166534; font-weight:600; background:#f0fdf4; border:1px solid #bbf7d0; padding:6px 8px;"><i class="klb-icon-check-circle me-1"></i> Delivery &amp; Ship To info saved! Add product items in the matrix to submit your quote request.</div>';
      sideStatus.style.display = 'block';
      setTimeout(() => { if (sideStatus) sideStatus.style.display = 'none'; }, 6000);
    }

    // Do NOT scroll down to #bulk-tracking with no request info!
    // Focus the first empty product description in the table so user naturally moves to product lines
    const firstDesc = document.querySelector('.po-row .row-desc');
    if (firstDesc && !firstDesc.value.trim()) {
      firstDesc.focus();
    }
  };

  function loadSavedDeliveryDetails() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const d = JSON.parse(raw);
      if (d.company && !document.getElementById('buyer-company-name').value) document.getElementById('buyer-company-name').value = d.company;
      if (d.contact_name && !document.getElementById('buyer-contact-name').value) document.getElementById('buyer-contact-name').value = d.contact_name;
      if (d.address && !document.getElementById('buyer-address').value) document.getElementById('buyer-address').value = d.address;
      if (d.city_postcode && !document.getElementById('buyer-city-postcode').value) document.getElementById('buyer-city-postcode').value = d.city_postcode;
      if (d.phone && !document.getElementById('buyer-phone-email').value) document.getElementById('buyer-phone-email').value = d.phone;
      if (d.email && !document.getElementById('buyer-email').value) document.getElementById('buyer-email').value = d.email;
      if (d.requested_date && !document.getElementById('po-delivery-date').value) document.getElementById('po-delivery-date').value = d.requested_date;
      if (d.notes && !document.getElementById('buyer-notes').value) document.getElementById('buyer-notes').value = d.notes;

      if (sideStatus && d.company) {
        sideStatus.innerHTML = '<span style="color:#166534; font-size:10.5px; font-weight:600;"><i class="klb-icon-check"></i> Loaded saved delivery details</span>';
        sideStatus.style.display = 'block';
        setTimeout(() => { if (sideStatus) sideStatus.style.display = 'none'; }, 3000);
      }
    } catch {}
  }

  // Live input validation listeners to clear error borders on typing
  ['buyer-company-name', 'buyer-contact-name', 'buyer-address', 'buyer-city-postcode', 'buyer-phone-email', 'buyer-email'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('input', () => {
      el.style.borderColor = '';
      if (sideStatus && sideStatus.textContent.includes('Please enter')) {
        sideStatus.style.display = 'none';
      }
    });
  });

  window.handleProductSearch = async input => {
    const row = input.closest('tr'), query = input.value.trim(), drop = row.querySelector('.item-suggest-dropdown');
    clearTimeout(input.searchTimer);
    row.querySelector('.row-sku').value = '';
    drop.classList.remove('active');
    const version = input.searchVersion = (input.searchVersion || 0) + 1;
    if (!query) { drop.classList.remove('active'); return; }
    input.searchTimer = setTimeout(async () => {
      try {
        const result = await api('/api/products/?q=' + encodeURIComponent(query));
        if (input.searchVersion !== version || !input.isConnected) return;
        drop.replaceChildren();
        for (const product of result.products.slice(0, 8)) {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'suggest-item';
          button.textContent = product.name + ' — ' + (product.sku || '') + ' (retail guide £' + product.price + ')';
          button.onclick = () => {
            const r = input.closest('tr');
            r.querySelector('.row-sku').value = product.sku || '';
            input.value = product.name;
            r.querySelector('.row-price').value = product.price;
            r.querySelector('.row-unit').value = product.weight + ' ' + product.weight_unit;
            drop.classList.remove('active');
            window.calcRow(input);
          };
          drop.append(button);
        }
        if (!drop.childNodes.length) drop.textContent = 'Custom material: describe the product and pack required.';
        drop.classList.add('active');
      } catch {
        if (input.searchVersion !== version) return;
        drop.textContent = 'Search unavailable; you can enter a product description manually.';
        drop.classList.add('active');
      }
    }, 200);
  };

  function card(row) {
    return `<article class="po-sheet my-3 p-3"><h3 class="text-15">${esc(row.number)} · ${esc(row.status.replaceAll('_', ' '))}</h3><p>${esc(row.company)} · ${esc(row.contact_name)}<br>${esc(row.email)} · ${esc(row.phone)}<br>${esc(row.address)}, ${esc(row.city_postcode)}<br>Requested delivery: ${esc(row.requested_date || 'Not specified')}</p><ul>${row.items.map(i => `<li>${esc(i.quantity)} × ${esc(i.description)} — ${esc(i.unit)} (${esc(i.sku)})</li>`).join('')}</ul><p>${esc(row.notes)}</p><p>${row.quoted_total !== null ? 'Quoted total: £' + esc(row.quoted_total) : 'Awaiting store quote'}</p><p>Delivery: ${esc(row.delivery_terms || 'Awaiting confirmation')}<br>Payment: ${esc(row.payment_terms || 'Awaiting confirmation')}</p><h4 class="text-15">Updates and replies</h4>${row.replies.map(r => `<div class="border-top py-2"><strong>${esc(r.status.replaceAll('_', ' '))} · ${new Date(r.created_at).toLocaleString('en-GB')}</strong><p style="white-space:pre-wrap">${esc(r.message)}</p>${r.quote.total != null ? `<p>Quote £${esc(r.quote.total)}<br>${esc(r.quote.delivery)}<br>${esc(r.quote.payment)}</p>` : ''}</div>`).join('')}</article>`;
  }

  async function refresh() {
    const requested = new URLSearchParams(location.search).get('request');
    if (requested) {
      list.innerHTML = card(await api('/api/bulk/requests/' + encodeURIComponent(requested) + '/'));
      document.getElementById('bulk-more').hidden = true;
      return;
    }
    let rows = [];
    for (let page = 1; page <= pages; page++) {
      const result = await api('/api/bulk/requests/?page=' + page);
      rows.push(...result.requests);
      document.getElementById('bulk-more').hidden = !result.has_more;
    }
    list.innerHTML = rows.map(card).join('') || '<p>No requests in this session. Submit a request above, sign in to your account, or open the secure tracking link from your email.</p>';
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy) return;
    clearSubmitFeedback();

    // 1. Validate delivery & ship-to sidebar
    if (!validateDelivery(true)) {
      showSubmitFeedback('<i class="klb-icon-alert-triangle me-1"></i> Please complete the Delivery &amp; Ship To details in the left sidebar.', 'warning');
      return;
    }

    // 2. Validate line items
    const rows = [...document.querySelectorAll('.po-row')];
    const items = rows
      .filter(r => r.querySelector('.row-desc')?.value.trim())
      .map(r => ({
        description: r.querySelector('.row-desc').value.trim(),
        sku: r.querySelector('.row-sku')?.value || '',
        unit: r.querySelector('.row-unit')?.value || '',
        quantity: Number(r.querySelector('.row-qty')?.value) || 1,
        requested_price: r.querySelector('.row-price')?.value || '0'
      }));

    if (items.length === 0) {
      showSubmitFeedback('<i class="klb-icon-alert-circle me-1"></i> Please enter at least one product description and quantity in the items table.', 'warning');
      const firstDesc = document.querySelector('.po-row .row-desc');
      if (firstDesc) {
        firstDesc.style.borderColor = '#dc2626';
        firstDesc.focus();
      }
      return;
    }

    for (const item of items) {
      if (!item.quantity || item.quantity < 1 || item.quantity > 100000) {
        showSubmitFeedback('<i class="klb-icon-alert-circle me-1"></i> Each item line must have a quantity between 1 and 100,000.', 'warning');
        return;
      }
    }

    // Save details locally for user's convenience
    const d = getDeliveryData();
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(d)); } catch {}

    const body = {
      company: d.company,
      contact_name: d.contact_name,
      email: d.email,
      phone: d.phone,
      address: d.address,
      city_postcode: d.city_postcode,
      requested_date: d.requested_date,
      notes: d.notes,
      items
    };

    const fingerprint = JSON.stringify(body);
    let attempt;
    try { attempt = JSON.parse(sessionStorage.getItem('bulk-attempt')); } catch {}
    if (!attempt || attempt.fingerprint !== fingerprint) {
      attempt = { fingerprint, key: crypto.randomUUID() };
      sessionStorage.setItem('bulk-attempt', JSON.stringify(attempt));
    }

    busy = true;
    const button = form.querySelector('[type=submit]');
    const originalBtnText = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<i class="klb-icon-clock"></i> Submitting Request...';

    try {
      const result = await api('/api/bulk/requests/', body, attempt.key);
      sessionStorage.removeItem('bulk-attempt');
      history.replaceState(null, '', '/bulk-order/?request=' + result.request.id);
      say(result.request.number + ' received. Your request and store replies appear below. Save the secure tracking link from your email.');
      showSubmitFeedback(`<i class="klb-icon-check-circle me-1"></i> Bulk request <strong>${esc(result.request.number)}</strong> submitted successfully! You can track it below.`, 'success');
      await refresh();
      document.getElementById('bulk-tracking').scrollIntoView({ behavior: 'smooth' });
    } catch (error) {
      say(error.message, true);
      showSubmitFeedback(`<i class="klb-icon-alert-circle me-1"></i> ${esc(error.message)}`, 'danger');
    } finally {
      busy = false;
      button.disabled = false;
      button.innerHTML = originalBtnText;
    }
  });

  document.getElementById('bulk-refresh').onclick = () => refresh().catch(e => say(e.message, true));
  document.getElementById('bulk-more').onclick = () => { pages++; refresh().catch(e => say(e.message, true)); };

  if (document.querySelectorAll('.po-row').length === 0 && typeof window.addNewRow === 'function') {
    window.addNewRow();
  }
  if (typeof window.recalculateGrandTotal === 'function') {
    window.recalculateGrandTotal();
  }
  loadSavedDeliveryDetails();

  (async () => {
    try {
      const token = new URLSearchParams(location.hash.slice(1)).get('access');
      if (token) {
        await api('/api/bulk/access/', { token });
        history.replaceState(null, '', location.pathname + location.search);
      }
      await refresh();
    } catch (error) {
      say(error.message, true);
    }
  })();

  setInterval(() => {
    if (!document.hidden) refresh().catch(e => say(e.message, true));
  }, 15000);
})();
