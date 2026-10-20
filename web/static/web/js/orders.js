/* Server-authoritative checkout and order tracking, using existing UI classes. */
(() => {
  'use strict';
  const esc = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const csrf = () => decodeURIComponent(document.cookie.split('; ').find(v=>v.startsWith('csrftoken='))?.slice(10) || '');
  const api = async (url, data, method='POST') => {
    const response = await fetch(url,{method:data===undefined?'GET':method,credentials:'same-origin',cache:'no-store',
      headers:{'X-CSRFToken':csrf(),...(data instanceof FormData?{}:{'Content-Type':'application/json'})},
      ...(data===undefined?{}:{body:data instanceof FormData?data:JSON.stringify(data)})});
    const result = await response.json();
    if(!response.ok) throw new Error(result.errors?.join(' ') || 'Unable to complete request.');
    return result;
  };
  const notify = message => window.TeraiCatalog?.showToast('Order update',message,'info');
  const read = key => {try{return JSON.parse(sessionStorage.getItem(key)||'null');}catch{return null;}};
  const store = (key,value) => sessionStorage.setItem(key,JSON.stringify(value));
  const fields = [
    ['name','Full name','text',true],['email','Email address','email',true],['phone','UK contact number','tel',true],
    ['line1','House / street address','text',true],['line2','Address line 2','text',false],
    ['city','Town / city','text',true],['county','County','text',false],['postcode','UK postcode','text',true],
    ['instructions','Delivery instructions','text',false]
  ];
  let contact=read('order-contact')||{}, pending=false;
  function contactForm(prefix, values={}) {
    return fields.map(([key,label,type,required])=>`<label class="d-block mb-2">${label}${required?' *':''}<input class="cart-drawer-form-input form-control" name="${key}" id="${prefix}-${key}" type="${type}" value="${esc(values[key])}" maxlength="${key==='instructions'?500:150}" ${required?'required':''}></label>`).join('');
  }
  function readContact(root) {
    const data={country:'GB'};
    for(const [key] of fields) data[key]=root.querySelector(`[name="${key}"]`)?.value.trim()||'';
    return data;
  }
  function addressValid() {
    const root=document.getElementById('order-contact-form');
    if(root) contact=readContact(root);
    if(!root?.reportValidity()) {
      const edit=document.getElementById('checkout-address-edit-view');
      if(edit) edit.style.display='block';
      notify('Enter your contact details and UK delivery address.');
      return false;
    }
    store('order-contact',contact);
    syncContact();
    return true;
  }
  function syncContact() {
    const values={'disp-cust-name':contact.name,'disp-cust-phone':contact.phone,'disp-cust-address':[contact.line1,contact.line2,contact.city,contact.postcode].filter(Boolean).join(', '),'disp-cust-note':contact.instructions,
      'display-recipient-name':contact.name,'display-recipient-phone':contact.phone,'display-address-full':[contact.line1,contact.line2,contact.city,contact.postcode].filter(Boolean).join(', '),'display-address-landmark':contact.instructions,'display-invoice-email':contact.email};
    for(const [id,value] of Object.entries(values)){const node=document.getElementById(id);if(node)node.textContent=value||'Enter delivery details';}
  }
  async function checkout() {
    if(pending) return;
    if(!addressValid()) {window.TeraiCatalog?.openCheckout();return;}
    const selected=window.TeraiCatalog?.selectedItems?.()||[];
    if(!selected.length){notify('Your basket is empty.');return;}
    const body={email:contact.email,address:contact,items:selected.map(i=>({product_id:Number(i.id),quantity:Number(i.quantity)}))};
    const fingerprint=JSON.stringify(body);
    let attempt=read('checkout-attempt');
    if(!attempt || attempt.fingerprint!==fingerprint) {
      attempt={fingerprint,key:crypto.randomUUID()};store('checkout-attempt',attempt);
    }
    pending=true;
    try {
      const response=await fetch('/api/orders/checkout/',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf(),'Idempotency-Key':attempt.key},body:JSON.stringify(body)});
      const result=await response.json();
      if(!response.ok) throw new Error(result.errors?.join(' ')||'Unable to start payment.');
      store('pending-order',{id:result.order.id,items:body.items});
      location.assign(result.payment_url);
    }catch(error){notify(error.message);}finally{pending=false;}
  }
  window.TeraiOrders={checkout,addressValid,api};

  function configureCheckout() {
    const edit=document.getElementById('checkout-address-edit-view');
    if(edit && !document.getElementById('order-contact-form')) {
      edit.innerHTML=`<form id="order-contact-form">${contactForm('checkout',contact)}<button class="checkout-save-addr-btn" type="submit">Save Address</button></form>`;
      edit.style.display='block';
      edit.querySelector('form').addEventListener('submit',e=>{e.preventDefault();if(addressValid())notify('Delivery details saved for checkout.');});
      edit.querySelector('[name=postcode]').addEventListener('blur',async e=>{
        const postcode=e.target.value.trim();if(!postcode)return;
        try {
          const response=await fetch('https://api.postcodes.io/postcodes/'+encodeURIComponent(postcode),{signal:AbortSignal.timeout(5000)});
          const data=await response.json();
          if(data.result && e.target.value.trim()===postcode) {
            e.target.value=data.result.postcode;
            const city=edit.querySelector('[name=city]');if(!city.value)city.value=data.result.admin_district||'';
          }
        }catch{/* Manual entry remains available when postcode lookup is offline. */}
      });
    }
    // Collection is hosted by Stripe; this site never reads a PAN or CVC.
    const cardBox=document.getElementById('drawer-card-box');
    if(cardBox) cardBox.innerHTML='<p>Continue to Stripe secure checkout to enter your test card details.</p>';
    document.querySelectorAll('.cart-drawer-payment-tile').forEach(tile=>{
      if(tile.dataset.payment!=='card') {tile.hidden=true;tile.querySelectorAll('input').forEach(i=>i.disabled=true);}
    });
    const standalone=document.getElementById('panel-card');
    if(standalone) standalone.innerHTML='<div class="payment-panel-header"><h3>Secure card payment</h3><p>Card details are collected by Stripe. Use a Stripe test card.</p></div>';
    document.querySelectorAll('.payment-tile-card').forEach(tile=>{
      if(tile.dataset.method!=='card') {tile.hidden=true;tile.setAttribute('aria-disabled','true');}
    });
    const proceed=document.getElementById('btn-proceed-to-pay');
    if(proceed && document.getElementById('customer-authenticated')?.textContent!=='true' && !document.getElementById('continue-as-guest')) {
      const guest=document.createElement('button');guest.type='button';guest.id='continue-as-guest';
      guest.className='cart-drawer-btn-secondary';guest.textContent='Continue as Guest';
      guest.addEventListener('click',()=>{edit.style.display='block';edit.querySelector('input')?.focus();});
      proceed.before(guest);
    }
    syncContact();
    document.addEventListener('click',e=>{
      if(e.target.closest('#btn-proceed-pay, #edit-address-btn, #edit-invoice-btn, #btn-edit-invoice-info')) {
        e.preventDefault();e.stopImmediatePropagation();window.TeraiCatalog?.openCheckout();
      }
      if(e.target.closest('#confirm-pay-btn')){e.preventDefault();e.stopImmediatePropagation();checkout();}
    },true);
    const cart=window.TeraiCatalog?.getCart()||[];
    if(cart.length) window.dispatchEvent(new CustomEvent('delivery:request',{detail:cart}));
  }
  window.addEventListener('delivery:quote',e=>{
    const q=e.detail.quote;
    for(const [id,value] of Object.entries({'summary-items-total':q?.subtotal,'summary-delivery-fee':q?.delivery_charge,'summary-total-val':q?.total,'modal-pay-amount':q?.total})) {
      const el=document.getElementById(id);if(el)el.textContent=value||'—';
    }
    document.querySelectorAll('.summary-total-amount,.payment-summary-card .summary-line-val').forEach(el=>el.textContent=q?'£'+q.total:'—');
    const pay=document.getElementById('btn-final-pay');if(pay)pay.textContent=q?'Continue to Stripe · £'+q.total:'Continue to Stripe';
    const eta=document.getElementById('delivery-date-text');if(eta){eta.parentElement.firstChild.textContent='Estimated delivery: ';eta.textContent=q?.delivery.estimate||'2–4 days';}
    const pkg=document.getElementById('checkout-product-item');
    if(pkg) pkg.innerHTML=(q?.items||[]).map(i=>`<div class="checkout-item-info"><img class="checkout-item-thumb" src="${esc(i.image)}" alt="${esc(i.name)}" width="64"><h5>${esc(i.name)}</h5><span>Qty: ${i.quantity} · £${esc(i.price)}</span></div>`).join('')||'<p>Your basket is empty or delivery is unavailable.</p>';
  });

  const stages=['placed','confirmed','preparing','ready_for_dispatch','dispatched','out_for_delivery','delivered'];
  const label=s=>String(s).replaceAll('_',' ');
  function orderCard(o) {
    const index=stages.indexOf(o.fulfilment_status), progress=Math.max(0,index)/6*100;
    return `<article class="order-group-card order-item-card" data-order="${esc(o.id)}" data-status="${o.group}" data-keywords="${esc(o.number+' '+o.items.map(i=>i.name).join(' '))}">
      <div class="order-group-header"><div class="d-flex align-items-center gap-3"><span class="store-badge">Terai Foods</span><span>Order <strong>${esc(o.number)}</strong></span><span class="text-gray-400">${new Date(o.created_at).toLocaleDateString('en-GB')}</span></div><span class="order-status-pill status-${o.group}">${esc(label(o.fulfilment_status))}</span></div>
      <div class="order-tracking-stepper"><div class="d-flex justify-content-between"><span>Estimated delivery: ${esc(o.delivery_estimate||'Contact support')}</span><span>Payment: ${esc(o.payment_status)} · Refund: ${esc(o.refund_status)}</span></div>
      <div class="stepper-progress-wrap"><div class="stepper-progress-bar"><div class="stepper-progress-active" style="width:${progress}%"></div></div>${['Order Placed','Preparing','Dispatched','Delivered'].map((s,i)=>`<div class="step-node ${index>=[0,2,4,6][i]?'completed':''}"><div class="step-dot"><i class="klb-icon-check"></i></div><span class="step-label">${s}</span></div>`).join('')}</div>
      <p>${esc(o.address.name)} · ${esc([o.address.line1,o.address.line2,o.address.city,o.address.postcode].filter(Boolean).join(', '))}</p><p>${esc(o.address.instructions)}</p>
      ${o.tracking_url && /^https:\/\//.test(o.tracking_url)?`<a href="${esc(o.tracking_url)}" target="_blank" rel="noopener">Courier tracking ${esc(o.tracking_reference)}</a>`:''}</div>
      ${o.items.map(i=>`<div class="order-item-row">${i.image?`<img class="order-item-thumb" src="${esc(i.image)}" alt="${esc(i.name)}">`:''}<div class="order-item-info"><h6 class="order-item-title">${esc(i.name)}</h6>${i.can_review?`<button class="btn-track-action" data-review-line="${i.id}" data-product="${i.product_id}">Write a review</button>`:''}</div><div class="order-item-price">£${esc(i.unit_price)}</div><div class="order-item-qty">Qty: ${i.quantity}</div></div>`).join('')}
      <div class="order-group-footer"><span>Total £${esc(o.total)} · Delivery £${esc(o.delivery_charge)}</span><div>${o.can_cancel?'<button class="btn-track-action" data-order-action="cancel">Cancel order</button>':''}${o.can_return?'<button class="btn-track-action" data-order-action="return">Request return</button>':''}${o.fulfilment_status==='pending_payment' && o.cancellation_status==='none'?'<button class="btn-track-action" data-order-action="payment">Retry payment</button>':''}<button class="btn-track-action" data-order-action="support">Contact support</button></div></div>
      <details class="p-3"><summary>Order updates</summary><ol>${o.events.map(e=>`<li>${new Date(e.created_at).toLocaleString('en-GB')} · ${esc(e.message)}</li>`).join('')}</ol></details></article>`;
  }
  async function tracking() {
    const root=document.getElementById('real-orders');if(!root)return;
    const orders=new Map(), sockets=new Map(), versions=new Map();
    const update=o=>{
      const previous=versions.get(o.id);
      if(previous!==undefined && o.version<=previous)return;
      versions.set(o.id,o.version);orders.set(o.id,o);
      const element=root.querySelector(`[data-order="${o.id}"]`);
      if(element)element.outerHTML=orderCard(o);else {if(!orders.size || root.querySelector('p')){if(!root.querySelector('article'))root.textContent='';}root.insertAdjacentHTML('beforeend',orderCard(o));}
      const groups=['all','in-transit','processing','completed','cancelled'];
      for(const selector of ['.order-tab-count','.cat-count'])document.querySelectorAll(selector).forEach((el,i)=>el.textContent=[...orders.values()].filter(v=>groups[i]==='all'||v.group===groups[i]).length);
      if(previous!==undefined && 'Notification' in window && Notification.permission==='granted')new Notification(o.number,{body:label(o.fulfilment_status)});
      const pending=read('pending-order');
      if(o.payment_status==='paid' && pending?.id===o.id) {
        const bought=new Map(pending.items.map(i=>[String(i.product_id),i.quantity]));
        window.TeraiCatalog?.saveCart(window.TeraiCatalog.getCart().map(i=>({...i,quantity:i.quantity-(bought.get(String(i.id))||0)})).filter(i=>i.quantity>0));
        sessionStorage.removeItem('pending-order');sessionStorage.removeItem('checkout-attempt');
      }
    };
    const connect=id=>{
      if(sockets.has(id))return;
      let retry=1000, stopped=false, heartbeat;
      const open=()=>{
        if(stopped)return;
        const ws=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws/orders/${id}/`);
        sockets.set(id,ws);
        ws.onopen=()=>{retry=1000;heartbeat=setInterval(()=>{if(ws.readyState===1)ws.send(JSON.stringify({type:'ping'}));},25000);};
        ws.onmessage=e=>{try{const d=JSON.parse(e.data);if(d.order)update(d.order);}catch{}};
        ws.onclose=e=>{clearInterval(heartbeat);if(e.code===4403){stopped=true;root.querySelector(`[data-order="${id}"]`)?.remove();return;}setTimeout(open,retry);retry=Math.min(30000,retry*2);};
      };open();
    };
    async function sync() {
      const requested=new URLSearchParams(location.search).get('order');
      const list=requested?[await api(`/api/orders/${encodeURIComponent(requested)}/`)]: (await api('/api/orders/history/')).orders;
      for(const order of list){update(order);connect(order.id);}
      if(!list.length)root.innerHTML='<p>No orders are available in this session. Use the secure tracking link from your order email, or sign in.</p>';
    }
    try {
      const token=new URLSearchParams(location.hash.slice(1)).get('access');
      if(token){await api('/api/orders/access/',{token});history.replaceState(null,'',location.pathname+location.search);}
      await sync();
    } catch(e){root.textContent=e.message;}
    setInterval(()=>{if(!document.hidden)sync().catch(()=>{});},30000);
    root.addEventListener('click',async e=>{
      const action=e.target.closest('[data-order-action]'),review=e.target.closest('[data-review-line]');
      try {
        if(action) {
          const name=action.dataset.orderAction, id=action.closest('[data-order]').dataset.order;
          const reason=name==='payment'?'':prompt(name==='cancel'?'Reason for cancellation:':name==='support'?'Your message (up to 500 characters):':'Reason for return:');
          if(reason===null)return;
          action.disabled=true;
          const result=await api(`/api/orders/${id}/action/`,{action:name,reason});
          if(result.payment_url)location.assign(result.payment_url);else update(result);
        }
        if(review) {
          const existing=root.querySelector('#order-review-form');existing?.remove();
          review.insertAdjacentHTML('afterend',`<form id="order-review-form" class="pdp-review-item"><input type="hidden" name="order_line" value="${review.dataset.reviewLine}"><label>Rating<select name="rating" class="form-control">${[5,4,3,2,1].map(n=>`<option>${n}</option>`).join('')}</select></label><label>Title<input name="title" class="form-control" maxlength="150"></label><label>Review<textarea name="text" class="form-control" required maxlength="5000"></textarea></label><label>Photos (up to four)<input name="images" type="file" multiple accept="image/jpeg,image/png,image/webp,image/avif"></label><button class="btn-track-action">Submit review</button></form>`);
          root.querySelector('#order-review-form').onsubmit=async ev=>{ev.preventDefault();try{await api(`/api/orders/reviews/${review.dataset.product}/`,new FormData(ev.target));ev.target.remove();review.remove();notify('Review submitted for moderation.');}catch(error){notify(error.message);}};
        }
      }catch(error){notify(error.message);}finally{if(action)action.disabled=false;}
    });
    document.getElementById('order-browser-notifications')?.addEventListener('click',()=>{if('Notification'in window)Notification.requestPermission();});
  }

  async function addresses() {
    if(document.getElementById('customer-authenticated')?.textContent!=='true')return;
    let data;
    try{data=await api('/api/orders/addresses/');}catch{return;}
    const edit=document.getElementById('order-contact-form');
    if(edit && data.addresses.length) {
      const select=document.createElement('select');select.className='form-control';select.setAttribute('aria-label','Saved delivery address');
      select.innerHTML='<option value="">Choose a saved address</option>'+data.addresses.map(a=>`<option value="${a.id}">${esc(a.line1+', '+a.postcode)}</option>`).join('');
      select.onchange=()=>{const a=data.addresses.find(a=>String(a.id)===select.value);if(!a)return;contact={...a,email:contact.email||''};for(const [key]of fields){const input=edit.querySelector(`[name="${key}"]`);if(input)input.value=contact[key]||'';}syncContact();};
      edit.prepend(select);
    }
    const pane=document.getElementById('pane-address');if(!pane)return;
    const body=pane.querySelector('.account-card-body');if(!body)return;
    const render=()=>{
      body.innerHTML=`<div id="saved-addresses">${data.addresses.map(a=>`<p>${esc(a.name)} · ${esc(a.line1)} · ${esc(a.postcode)} ${a.is_default?'(Default)':''} <button class="btn-track-action" data-edit="${a.id}">Edit</button><button class="btn-track-action" data-delete="${a.id}">Delete</button></p>`).join('')||'<p>No saved addresses.</p>'}</div>
      <form id="saved-address-form">${contactForm('saved')}<label><input type="checkbox" name="is_default">Default address</label><button class="btn btn-primary" type="submit">Save address</button><button type="reset" class="btn">New address</button></form>`;
      const form=body.querySelector('form');form.querySelector('[name=email]').closest('label').remove();
      let id=null;
      form.onreset=()=>{id=null;};
      form.onsubmit=async e=>{e.preventDefault();try{await api('/api/orders/addresses/'+(id?id+'/':''),{...readContact(form),is_default:form.elements.is_default.checked},id?'PATCH':'POST');data=await api('/api/orders/addresses/');render();}catch(error){notify(error.message);}};
      body.onclick=async e=>{
        const edit=e.target.closest('[data-edit]'),del=e.target.closest('[data-delete]');
        if(edit){const a=data.addresses.find(a=>String(a.id)===edit.dataset.edit);id=a.id;for(const [key]of fields)if(form.elements[key])form.elements[key].value=a[key]||'';form.elements.is_default.checked=a.is_default;}
        if(del && confirm('Delete this saved address?')){try{await api(`/api/orders/addresses/${del.dataset.delete}/`,{},'DELETE');data=await api('/api/orders/addresses/');render();}catch(error){notify(error.message);}}
      };
    };render();
  }
  async function reviews() {
    const root=document.getElementById('real-product-reviews');if(!root)return;
    let product;try{product=JSON.parse(document.getElementById('catalog-detail').textContent);}catch{return;}if(!product)return;
    try{
      const data=await api(`/api/orders/reviews/${product.id}/`);
      root.innerHTML=data.reviews.map(r=>`<div class="pdp-review-item"><div class="pdp-review-stars">${'★'.repeat(r.rating)}${'☆'.repeat(5-r.rating)}</div><div class="pdp-review-author"><strong>${esc(r.name)}</strong> <span class="pdp-verified-badge">✓ Verified Purchase</span> · ${new Date(r.date).toLocaleDateString('en-GB')}</div><h4>${esc(r.title)}</h4><div class="pdp-review-content">${esc(r.text)}</div><div class="pdp-review-photos">${r.images.map(url=>`<div class="pdp-review-photo"><img src="${esc(url)}" alt="Review photo" loading="lazy"></div>`).join('')}</div></div>`).join('')||'<p>No reviews yet. Delivered purchases can be reviewed from My Orders.</p>';
      const score=document.querySelector('.pdp-big-score');if(score)score.innerHTML=`${Number(data.summary.average||0).toFixed(1)}<span class="pdp-score-scale">/5</span>`;
      document.querySelectorAll('.pdp-meta-left .pdp-gold-stars,.pdp-score-block .pdp-gold-stars').forEach(el=>{
        const rating=Math.round(data.summary.average||0);el.textContent='★'.repeat(rating)+'☆'.repeat(5-rating);
      });
      document.querySelectorAll('.pdp-score-block .text-muted,.pdp-meta-link[href="#reviews-section"]').forEach(el=>el.textContent=data.summary.count+' Ratings');
      document.querySelectorAll('.pdp-bar-row').forEach((row,i)=>{const count=data.histogram?.[5-i]||0;row.querySelector('.pdp-bar-count').textContent=count;row.querySelector('.pdp-bar-fill').style.width=(data.summary.count?count/data.summary.count*100:0)+'%';});
    }catch(error){root.textContent=error.message;}
  }
  async function notifications() {
    const container=document.getElementById('order-notifications');if(!container)return;
    try {
      const data=await api('/api/orders/notifications/');
      container.innerHTML=data.notifications.map(n=>`<p><a href="/track-order/?order=${esc(n.event__order__public_id)}">${esc(n.event__message)}</a> · ${new Date(n.event__created_at).toLocaleString('en-GB')} ${n.read_at?'':`<button type="button" class="btn-track-action" data-read="${n.id}">Mark read</button>`}</p>`).join('')||'<p>No order updates yet.</p>';
      container.onclick=async e=>{const button=e.target.closest('[data-read]');if(button){await api('/api/orders/notifications/',{id:Number(button.dataset.read)});notifications();}};
    }catch{container.textContent='Unable to load order updates.';}
  }
  const ready=()=>{configureCheckout();tracking();addresses();reviews();notifications();setInterval(()=>{if(!document.hidden)notifications();},30000);};
  if(document.readyState!=='complete')document.addEventListener('DOMContentLoaded',ready);else ready();
})();
