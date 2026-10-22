(() => {
  'use strict';
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const api=async(url,body,key)=>{
    const csrf=decodeURIComponent(document.cookie.split('; ').find(c=>c.startsWith('csrftoken='))?.slice(10)||'');
    const response=await fetch(url,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json','X-CSRFToken':csrf,...(key?{'Idempotency-Key':key}:{})},...(body?{body:JSON.stringify(body)}:{})});
    const result=await response.json();if(!response.ok)throw new Error(result.errors?.join(' ')||'Unable to load bulk request.');return result;
  };
  const form=document.getElementById('bulk-po-form'),message=document.getElementById('bulk-message'),list=document.getElementById('bulk-request-list');
  if(!form)return;
  const value=id=>document.getElementById(id).value.trim();
  const say=text=>{message.textContent=text;};
  let pages=1,busy=false;
  window.saveDeliveryDetails=()=>{say('Delivery details will be saved when you submit this request.');document.getElementById('bulk-tracking').scrollIntoView({block:'center'});};
  window.handleProductSearch=async input=>{
    const query=input.value.trim(),drop=input.closest('tr').querySelector('.item-suggest-dropdown');
    if(!query){drop.classList.remove('active');return;}
    try {
      const result=await api('/api/products/?q='+encodeURIComponent(query));
      if(input.value.trim()!==query)return;
      drop.replaceChildren();
      for(const product of result.products.slice(0,8)){
        const button=document.createElement('button');button.type='button';button.className='suggest-item';button.textContent=product.name+' — '+(product.sku||'')+' (retail guide £'+product.price+')';
        button.onclick=()=>{const row=input.closest('tr');row.querySelector('.row-sku').value=product.sku||'';input.value=product.name;row.querySelector('.row-price').value=product.price;drop.classList.remove('active');window.calcRow(input);};drop.append(button);
      }
      if(!drop.childNodes.length)drop.textContent='Custom material: describe the product and pack required.';
      drop.classList.add('active');
    }catch{drop.textContent='Search unavailable; you can enter a product description manually.';drop.classList.add('active');}
  };
  function card(row){
    return `<article class="po-sheet my-3 p-3"><h3 class="text-15">${esc(row.number)} · ${esc(row.status.replaceAll('_',' '))}</h3><p>${esc(row.company)} · ${esc(row.contact_name)}<br>${esc(row.email)} ? ${esc(row.phone)}<br>${esc(row.address)}, ${esc(row.city_postcode)}<br>Requested delivery: ${esc(row.requested_date||'Not specified')}</p><ul>${row.items.map(i=>`<li>${esc(i.quantity)} × ${esc(i.description)} — ${esc(i.unit)} (${esc(i.sku)})</li>`).join('')}</ul><p>${esc(row.notes)}</p><p>${row.quoted_total!==null?'Quoted total: £'+esc(row.quoted_total):'Awaiting store quote'}</p><p>Delivery: ${esc(row.delivery_terms||'Awaiting confirmation')}<br>Payment: ${esc(row.payment_terms||'Awaiting confirmation')}</p><h4 class="text-15">Updates and replies</h4>${row.replies.map(r=>`<div class="border-top py-2"><strong>${esc(r.status.replaceAll('_',' '))} · ${new Date(r.created_at).toLocaleString('en-GB')}</strong><p style="white-space:pre-wrap">${esc(r.message)}</p>${r.quote.total!=null?`<p>Quote £${esc(r.quote.total)}<br>${esc(r.quote.delivery)}<br>${esc(r.quote.payment)}</p>`:''}</div>`).join('')}</article>`;
  }
  async function refresh(){
    const requested=new URLSearchParams(location.search).get('request');
    if(requested){list.innerHTML=card(await api('/api/bulk/requests/'+encodeURIComponent(requested)+'/'));document.getElementById('bulk-more').hidden=true;return;}
    let rows=[];
    for(let page=1;page<=pages;page++){const result=await api('/api/bulk/requests/?page='+page);rows.push(...result.requests);document.getElementById('bulk-more').hidden=!result.has_more;}
    list.innerHTML=rows.map(card).join('')||'<p>No requests in this session. Submit a request above, sign in to your account, or open the secure tracking link from your email.</p>';
  }
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(busy||!form.reportValidity())return;
    const items=[...document.querySelectorAll('.po-row')].filter(r=>r.querySelector('.row-desc').value.trim()).map(r=>({description:r.querySelector('.row-desc').value.trim(),sku:r.querySelector('.row-sku').value,unit:r.querySelector('.row-unit').value,quantity:Number(r.querySelector('.row-qty').value),requested_price:r.querySelector('.row-price').value||'0'}));
    const body={company:value('buyer-company-name'),contact_name:value('buyer-contact-name'),email:value('buyer-email'),phone:value('buyer-phone-email'),address:value('buyer-address'),city_postcode:value('buyer-city-postcode'),requested_date:value('po-delivery-date'),notes:value('buyer-notes'),items};
    const fingerprint=JSON.stringify(body);let attempt;try{attempt=JSON.parse(sessionStorage.getItem('bulk-attempt'));}catch{}
    if(!attempt||attempt.fingerprint!==fingerprint){attempt={fingerprint,key:crypto.randomUUID()};sessionStorage.setItem('bulk-attempt',JSON.stringify(attempt));}
    busy=true;const button=form.querySelector('[type=submit]');button.disabled=true;
    try{const result=await api('/api/bulk/requests/',body,attempt.key);history.replaceState(null,'','/bulk-order/?request='+result.request.id);say(result.request.number+' received. Your request and store replies appear below. Save the secure tracking link from your email.');await refresh();document.getElementById('bulk-tracking').scrollIntoView({behavior:'smooth'});}
    catch(error){say(error.message);document.getElementById('bulk-tracking').scrollIntoView({block:'center'});}
    finally{busy=false;button.disabled=false;}
  });
  document.getElementById('bulk-refresh').onclick=()=>refresh().catch(e=>say(e.message));
  document.getElementById('bulk-more').onclick=()=>{pages++;refresh().catch(e=>say(e.message));};
  window.addNewRow();window.recalculateGrandTotal();
  (async()=>{try{const token=new URLSearchParams(location.hash.slice(1)).get('access');if(token){await api('/api/bulk/access/',{token});history.replaceState(null,'',location.pathname+location.search);}await refresh();}catch(error){say(error.message);}})();
  setInterval(()=>{if(!document.hidden)refresh().catch(e=>say(e.message));},15000);
})();
