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

  const expandedSet = new Set();

  function statusBadge(status) {
    const s = String(status || '').toLowerCase();
    const map = {
      new: { label: 'New Request', cls: 'status-new', icon: 'klb-icon-clock' },
      under_review: { label: 'Under Review', cls: 'status-under_review', icon: 'klb-icon-eye' },
      quoted: { label: 'Quoted', cls: 'status-quoted', icon: 'klb-icon-check-circle' },
      accepted: { label: 'Accepted', cls: 'status-accepted', icon: 'klb-icon-thumbs-up' },
      declined: { label: 'Declined', cls: 'status-declined', icon: 'klb-icon-x-circle' },
      completed: { label: 'Completed', cls: 'status-completed', icon: 'klb-icon-award' },
      cancelled: { label: 'Cancelled', cls: 'status-cancelled', icon: 'klb-icon-slash' }
    };
    const item = map[s] || { label: s.replace(/_/g, ' ') || 'Pending', cls: 'status-generic', icon: 'klb-icon-info' };
    return `<span class="bulk-status-badge ${item.cls}"><i class="${item.icon} me-1"></i>${esc(item.label)}</span>`;
  }

  window.copyTrackingUrl = function(reqId) {
    const url = window.location.origin + '/bulk-order/?request=' + encodeURIComponent(reqId);
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(() => {
        alert('Direct tracking link copied to clipboard:\n' + url);
      }).catch(() => {
        prompt('Direct tracking link:', url);
      });
    } else {
      prompt('Direct tracking link:', url);
    }
  };

  window.toggleBulkDetail = function(id) {
    if (expandedSet.has(id)) {
      expandedSet.delete(id);
    } else {
      expandedSet.add(id);
    }
    const rowEl = document.querySelector(`.bulk-req-row[data-request-id="${id}"]`);
    const detailEl = document.getElementById(`bulk-detail-${id}`);
    const isOpen = expandedSet.has(id);

    if (rowEl) {
      rowEl.classList.toggle('is-expanded', isOpen);
      const chevron = rowEl.querySelector('.bulk-chevron');
      if (chevron) chevron.classList.toggle('open', isOpen);
      const btn = rowEl.querySelector('.btn-bulk-expand');
      if (btn) {
        btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        btn.classList.toggle('is-active', isOpen);
        const label = btn.querySelector('.btn-label');
        if (label) label.textContent = isOpen ? 'Hide' : 'Details';
        const icon = btn.querySelector('.bulk-btn-icon');
        if (icon) icon.classList.toggle('rotate', isOpen);
      }
    }
    if (detailEl) {
      detailEl.classList.toggle('is-open', isOpen);
      detailEl.classList.toggle('is-hidden', !isOpen);
    }
  };

  function renderDetailRow(row) {
    const items = Array.isArray(row.items) ? row.items : [];
    const replies = Array.isArray(row.replies) ? row.replies : [];
    const totalQty = items.reduce((sum, it) => sum + (Number(it.quantity) || 0), 0);
    const totalEst = items.reduce((sum, it) => sum + ((Number(it.quantity) || 0) * (Number(it.requested_price) || 0)), 0);

    return `
      <div class="bulk-detail-container">
        <!-- Top bar with reference & actions -->
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 pb-2 mb-3 border-bottom" style="border-color: #cbd5e1 !important;">
          <div class="d-flex align-items-center gap-2">
            <span class="text-13 fw-bold text-dark">Order Specification:</span>
            <span class="font-monospace text-primary fw-bold text-13">${esc(row.number)}</span>
            <span class="text-12 text-muted">· Placed on ${new Date(row.created_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
          </div>
          <div class="d-flex align-items-center gap-2">
            <button type="button" class="btn-po-action-mini" onclick="window.copyTrackingUrl('${esc(row.id)}')">
              <i class="klb-icon-copy me-1"></i> Copy Direct Tracking Link
            </button>
            <button type="button" class="btn-po-action-mini" onclick="window.print()">
              <i class="klb-icon-printer me-1"></i> Print PO
            </button>
          </div>
        </div>

        <!-- 1. Requested Line Items Subtable -->
        <div class="mb-3">
          <h6 class="text-12 fw-bold text-uppercase text-muted mb-2">
            <i class="klb-icon-package text-primary me-1"></i> Requested Line Items (${items.length})
          </h6>
          <div class="table-responsive border" style="border-color: #cbd5e1 !important;">
            <table class="table table-sm table-hover mb-0 bulk-items-subtable">
              <thead class="table-light">
                <tr>
                  <th style="width: 40px;" class="text-center">#</th>
                  <th>Product Description</th>
                  <th style="width: 140px;">SKU</th>
                  <th style="width: 130px;">Pack / Unit</th>
                  <th class="text-center" style="width: 80px;">Qty</th>
                  <th class="text-end" style="width: 110px;">Guide Price</th>
                  <th class="text-end" style="width: 120px;">Est. Subtotal</th>
                </tr>
              </thead>
              <tbody>
                ${items.map((it, idx) => {
                  const q = Number(it.quantity) || 1;
                  const p = Number(it.requested_price) || 0;
                  const lineTotal = (q * p).toFixed(2);
                  return `<tr>
                    <td class="text-center text-muted text-11">${idx + 1}</td>
                    <td><strong class="text-dark">${esc(it.description)}</strong></td>
                    <td><code class="text-muted text-11">${esc(it.sku || 'CUSTOM')}</code></td>
                    <td class="text-12">${esc(it.unit || 'Standard')}</td>
                    <td class="text-center fw-bold text-13">${esc(it.quantity)}</td>
                    <td class="text-end text-12">${p > 0 ? '£' + p.toFixed(2) : '<span class="text-muted">—</span>'}</td>
                    <td class="text-end fw-semibold text-12">${p > 0 ? '£' + lineTotal : '<span class="text-muted">—</span>'}</td>
                  </tr>`;
                }).join('')}
              </tbody>
              <tfoot class="table-light">
                <tr>
                  <td colspan="4" class="text-end fw-bold text-12">Total Line Items:</td>
                  <td class="text-center fw-bold text-13 text-primary">${totalQty}</td>
                  <td class="text-end fw-bold text-12">Estimated Target:</td>
                  <td class="text-end fw-bold text-13 text-primary">£${totalEst.toFixed(2)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>

        <!-- 2. Delivery & Contact Details -->
        <div class="row g-3 mb-3">
          <div class="col-md-6">
            <div class="p-3 border h-100 bg-white" style="border-color: #cbd5e1 !important;">
              <h6 class="text-12 fw-bold text-uppercase text-muted mb-2">
                <i class="klb-icon-map-pin text-primary me-1"></i> Delivery &amp; Shipping Specs
              </h6>
              <div class="text-13 text-dark mb-1">
                <strong>Recipient Address:</strong> ${esc(row.address)}
              </div>
              <div class="text-13 text-dark mb-1">
                <strong>City &amp; Postcode:</strong> ${esc(row.city_postcode)}
              </div>
              <div class="text-13 text-dark mb-1">
                <strong>Target Delivery Date:</strong> ${esc(row.requested_date || 'Flexible / ASAP')}
              </div>
              <div class="text-12 text-muted mt-2 pt-2 border-top" style="border-color: #e2e8f0 !important;">
                <strong>Buyer Notes / Instructions:</strong><br>
                <span style="white-space: pre-wrap;">${esc(row.notes || 'No special delivery instructions provided.')}</span>
              </div>
            </div>
          </div>
          <div class="col-md-6">
            <div class="p-3 border h-100 bg-white" style="border-color: #cbd5e1 !important;">
              <h6 class="text-12 fw-bold text-uppercase text-muted mb-2">
                <i class="klb-icon-user text-primary me-1"></i> Buyer &amp; Organization Specs
              </h6>
              <div class="text-13 text-dark mb-1">
                <strong>Company / Business:</strong> ${esc(row.company || 'Private Buyer')}
              </div>
              <div class="text-13 text-dark mb-1">
                <strong>Contact Person:</strong> ${esc(row.contact_name)}
              </div>
              <div class="text-13 text-dark mb-1">
                <strong>Email:</strong> <a href="mailto:${esc(row.email)}" class="text-primary text-decoration-none">${esc(row.email)}</a>
              </div>
              <div class="text-13 text-dark mb-1">
                <strong>Phone:</strong> <a href="tel:${esc(row.phone)}" class="text-primary text-decoration-none">${esc(row.phone)}</a>
              </div>
              <div class="text-12 text-muted mt-2 pt-2 border-top" style="border-color: #e2e8f0 !important;">
                <strong>Current Status:</strong> ${statusBadge(row.status)}
              </div>
            </div>
          </div>
        </div>

        <!-- 3. Official Quotation & Commercial Terms -->
        <div class="p-3 mb-3 border" style="background: ${row.quoted_total !== null ? '#f0fdf4; border-color: #86efac !important;' : '#f8fafc; border-color: #cbd5e1 !important;'}">
          <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
            <div class="d-flex align-items-center gap-2">
              <span class="badge ${row.quoted_total !== null ? 'bg-success' : 'bg-secondary'} text-white px-2 py-1 text-11">
                ${row.quoted_total !== null ? 'Official Store Quote' : 'Quote Pending'}
              </span>
              <h6 class="text-13 fw-bold mb-0 text-dark">Commercial Pricing &amp; Terms</h6>
            </div>
            <div>
              ${row.quoted_total !== null ? `
                <span class="text-16 fw-bold text-success">Quoted Total: £${esc(row.quoted_total)}</span>
              ` : `
                <span class="text-12 text-muted fw-semibold"><i class="klb-icon-clock me-1"></i> Awaiting formal store quotation</span>
              `}
            </div>
          </div>
          <div class="row g-2 text-12">
            <div class="col-md-6">
              <strong>Delivery Terms:</strong> ${esc(row.delivery_terms || 'Awaiting confirmation from dispatch team')}
            </div>
            <div class="col-md-6">
              <strong>Payment Terms:</strong> ${esc(row.payment_terms || 'Awaiting confirmation from accounts team')}
            </div>
          </div>
        </div>

        <!-- 4. Updates & Replies Timeline -->
        <div>
          <h6 class="text-12 fw-bold text-uppercase text-muted mb-2">
            <i class="klb-icon-message-square text-primary me-1"></i> Updates and replies (${replies.length})
          </h6>
          ${replies.length > 0 ? `
            <div class="bulk-replies-timeline">
              ${replies.map(r => {
                const replyDate = new Date(r.created_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
                return `
                  <div class="p-3 mb-2 border bg-white" style="border-color: #cbd5e1 !important; border-left: 3px solid #634c9f !important;">
                    <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
                      <div>${statusBadge(r.status)}</div>
                      <div class="text-11 text-muted"><i class="klb-icon-clock me-1"></i>${esc(replyDate)}</div>
                    </div>
                    <div class="text-13 text-dark mb-2" style="white-space: pre-wrap; line-height: 1.5;">${esc(r.message)}</div>
                    ${r.quote && (r.quote.total != null || r.quote.delivery || r.quote.payment) ? `
                      <div class="p-2 bg-light border text-12" style="border-color: #e2e8f0 !important;">
                        ${r.quote.total != null ? `<div class="fw-bold text-success mb-1">Quote £${esc(r.quote.total)}</div>` : ''}
                        ${r.quote.delivery ? `<div><strong>Delivery terms:</strong> ${esc(r.quote.delivery)}</div>` : ''}
                        ${r.quote.payment ? `<div><strong>Payment terms:</strong> ${esc(r.quote.payment)}</div>` : ''}
                      </div>
                    ` : ''}
                  </div>
                `;
              }).join('')}
            </div>
          ` : `
            <div class="p-3 border text-12 text-muted fst-italic bg-light text-center" style="border-color: #e2e8f0 !important;">
              No replies yet. Your request is queued with our wholesale sales desk.
            </div>
          `}
        </div>
      </div>
    `;
  }

  function renderTable(rows) {
    if (!rows || rows.length === 0) {
      return `
        <div class="bulk-empty-state p-4 text-center border bg-white my-3" style="border-color: #cbd5e1 !important;">
          <div class="mb-2 text-muted" style="font-size: 28px;"><i class="klb-icon-inbox"></i></div>
          <h5 class="text-14 fw-bold text-dark mb-1">No Bulk Requests Found</h5>
          <p class="text-12 text-muted mb-0">No requests in this session. Submit a request above, sign in to your account, or open the secure tracking link from your email.</p>
        </div>
      `;
    }

    return `
      <div class="bulk-table-responsive my-3">
        <table class="bulk-requests-table table table-hover mb-0">
          <thead>
            <tr>
              <th style="width: 36px;" class="text-center" aria-label="Toggle"></th>
              <th style="width: 140px;">PO Request #</th>
              <th>Buyer / Company</th>
              <th style="width: 130px;">Target Date</th>
              <th>Items</th>
              <th style="width: 130px;">Status</th>
              <th style="width: 130px;" class="text-end">Quoted Total</th>
              <th style="width: 90px;" class="text-end">Details</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map(row => {
              const isOpen = expandedSet.has(row.id);
              const items = Array.isArray(row.items) ? row.items : [];
              const firstDesc = items[0]?.description || 'Custom line items';
              const reqDate = row.requested_date ? esc(row.requested_date) : 'Flexible / ASAP';
              const dateCreated = new Date(row.created_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });

              return `
                <tr class="bulk-req-row ${isOpen ? 'is-expanded' : ''}" data-request-id="${esc(row.id)}" onclick="window.toggleBulkDetail('${esc(row.id)}')">
                  <td class="text-center">
                    <span class="bulk-chevron ${isOpen ? 'open' : ''}">
                      <i class="klb-icon-chevron-down"></i>
                    </span>
                  </td>
                  <td>
                    <strong class="bulk-po-num text-primary">${esc(row.number)}</strong>
                    <span class="d-block text-11 text-muted">${esc(dateCreated)}</span>
                  </td>
                  <td>
                    <span class="fw-semibold text-dark text-13 d-block">${esc(row.company || 'Private Buyer')}</span>
                    <span class="text-11 text-muted">${esc(row.contact_name)}</span>
                  </td>
                  <td>
                    <span class="text-12 text-dark"><i class="klb-icon-calendar me-1 text-muted"></i>${reqDate}</span>
                  </td>
                  <td>
                    <span class="badge bg-light text-dark border text-11 me-1">${items.length} item${items.length === 1 ? '' : 's'}</span>
                    <span class="text-12 text-muted text-truncate d-inline-block align-middle" style="max-width: 180px;" title="${esc(firstDesc)}">
                      ${esc(firstDesc)}
                    </span>
                  </td>
                  <td>
                    ${statusBadge(row.status)}
                  </td>
                  <td class="text-end">
                    ${row.quoted_total !== null ? `
                      <span class="bulk-quote-amount text-success fw-bold text-13">£${esc(row.quoted_total)}</span>
                    ` : `
                      <span class="badge bg-warning-subtle text-warning-emphasis border border-warning-subtle text-11">Awaiting Quote</span>
                    `}
                  </td>
                  <td class="text-end">
                    <button type="button" class="btn-bulk-expand ${isOpen ? 'is-active' : ''}" aria-expanded="${isOpen ? 'true' : 'false'}" onclick="event.stopPropagation(); window.toggleBulkDetail('${esc(row.id)}')">
                      <span class="btn-label">${isOpen ? 'Hide' : 'Details'}</span>
                      <i class="klb-icon-chevron-down bulk-btn-icon ${isOpen ? 'rotate' : ''}"></i>
                    </button>
                  </td>
                </tr>
                <tr class="bulk-detail-row ${isOpen ? 'is-open' : 'is-hidden'}" id="bulk-detail-${esc(row.id)}">
                  <td colspan="8" class="p-0 border-0">
                    ${renderDetailRow(row)}
                  </td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    `;
  }

  async function refresh() {
    const requested = new URLSearchParams(location.search).get('request');
    let rows = [];
    if (requested) {
      try {
        const single = await api('/api/bulk/requests/' + encodeURIComponent(requested) + '/');
        rows = [single];
        expandedSet.add(single.id);
        const moreBtn = document.getElementById('bulk-more');
        if (moreBtn) moreBtn.hidden = true;
      } catch (e) {
        say(e.message, true);
        return;
      }
    } else {
      for (let page = 1; page <= pages; page++) {
        const result = await api('/api/bulk/requests/?page=' + page);
        rows.push(...result.requests);
        const moreBtn = document.getElementById('bulk-more');
        if (moreBtn) moreBtn.hidden = !result.has_more;
      }
      if (expandedSet.size === 0 && rows.length > 0) {
        expandedSet.add(rows[0].id);
      }
    }
    list.innerHTML = renderTable(rows);
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
