// Uses products and rates from delivery.test_browser's isolated database.
const {spawn} = require('child_process');
const fs = require('fs'), os = require('os'), path = require('path'), assert = require('assert/strict');

(async () => {
  const base = process.env.DELIVERY_TEST_URL;
  assert(base && process.env.DELIVERY_GRAMS_PRODUCT, 'Run through delivery.test_browser');
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'terai-delivery-test-'));
  const edge = spawn('C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    ['--headless=new', '--disable-gpu', '--remote-debugging-port=0', '--user-data-dir='+profile, 'about:blank'],
    {windowsHide:true, stdio:'ignore'});
  let ws;
  try {
    let port;
    for (let i=0;i<100;i++) {
      try { port=fs.readFileSync(path.join(profile,'DevToolsActivePort'),'utf8').split('\n')[0]; break; }
      catch { await new Promise(r=>setTimeout(r,100)); }
    }
    assert(port, 'Edge did not start');
    ws=new WebSocket((await (await fetch(`http://127.0.0.1:${port}/json/version`)).json()).webSocketDebuggerUrl);
    await new Promise(r=>ws.onopen=r);
    let id=0; const pending=new Map();
    ws.onmessage=e=>{const d=JSON.parse(e.data);if(d.id){pending.get(d.id)?.(d);pending.delete(d.id);}};
    const send=(method,params={},sessionId)=>new Promise(resolve=>{
      const key=++id; pending.set(key,resolve); ws.send(JSON.stringify({id:key,method,params,...(sessionId?{sessionId}:{})}));
    });
    const target=(await send('Target.createTarget',{url:'about:blank'})).result.targetId;
    const session=(await send('Target.attachToTarget',{targetId:target,flatten:true})).result.sessionId;
    const page=(m,p)=>send(m,p,session);
    const evaluate=async expression=>{
      const result=await page('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
      assert(!result.result?.exceptionDetails, JSON.stringify(result.result?.exceptionDetails));
      return result.result?.result?.value;
    };
    const until=async expression=>{
      for(let i=0;i<100;i++){if(await evaluate(expression))return;await new Promise(r=>setTimeout(r,100));}
      throw new Error('Timed out: '+expression);
    };
    await page('Page.enable');
    if(process.env.BULK_BROWSER_FLOW==='1') {
      await page('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
      await page('Page.navigate',{url:base+'/bulk-order/'});
      await until("!!document.querySelector('.po-row') && !!document.querySelector('#buyer-email')");
      await evaluate("const input=document.querySelector('.row-desc');input.value='Mobile';input.dispatchEvent(new Event('input',{bubbles:true}))");
      await until("!!document.querySelector('.item-suggest-dropdown.active button')");
      assert.equal(await evaluate("getComputedStyle(document.querySelector('.po-row')).display"),'grid');
      assert(await evaluate("document.querySelector('.item-suggest-dropdown').getBoundingClientRect().right<=innerWidth"),'Mobile search results must fit the viewport');
      await evaluate("document.querySelector('.item-suggest-dropdown button').click()");
      assert.equal(await evaluate("document.querySelector('.row-sku').value"),'MOBILE-RICE');
      assert.match(await evaluate("document.querySelector('.row-unit').value"),/150/);

      await evaluate(`Object.entries({'buyer-company-name':'Browser Grocer','buyer-contact-name':'Test Buyer','buyer-email':'browser@example.invalid','buyer-phone-email':'07700900123','buyer-address':'1 Example Street','buyer-city-postcode':'London SW1A 1AA','buyer-notes':'Morning delivery'}).forEach(([id,value])=>document.getElementById(id).value=value);document.querySelector('.row-desc').value='Custom rice';document.querySelector('.row-unit').value='5kg bag';document.querySelector('.row-price').value='4.50';document.getElementById('bulk-po-form').requestSubmit();`);
      await until("document.getElementById('bulk-request-list')?.textContent.includes('TF-BQ-')");
      const requestId=await evaluate("new URLSearchParams(location.search).get('request')");
      assert(requestId);
      const adminUrl=base+'/admin/bulk-orders/'+requestId+'/';
      const adminResponse=await fetch(adminUrl,{headers:{Cookie:process.env.BULK_ADMIN_COOKIE}});
      assert.equal(adminResponse.status,200);
      const html=await adminResponse.text();
      assert.match(html,/Morning delivery/);
      const csrf=html.match(/name="csrfmiddlewaretoken" value="([^"]+)"/)[1];
      const cookie=process.env.BULK_ADMIN_COOKIE+'; '+adminResponse.headers.getSetCookie().map(c=>c.split(';')[0]).join('; ');
      const posted=await fetch(adminUrl,{method:'POST',redirect:'manual',headers:{Cookie:cookie,Referer:adminUrl,'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({csrfmiddlewaretoken:csrf,version:'1',status:'quoted',quoted_total:'55.00',delivery_terms:'Delivery within 4 days',payment_terms:'Invoice before dispatch',message:'Your requested rice is available.'})});
      assert.equal(posted.status,302,await posted.text());
      await evaluate("document.getElementById('bulk-refresh').click()");
      await until("document.getElementById('bulk-request-list')?.textContent.includes('Your requested rice is available.')");
      assert.match(await evaluate("document.getElementById('bulk-request-list').textContent"),/55.00/);
      await page('Page.navigate',{url:base+'/bulk-order/'});
      await until("document.getElementById('bulk-request-list')?.textContent.includes('Your requested rice is available.')");
      console.log('Bulk browser flow passed: submission, admin quote, same-page tracking and persistent history.');
      return;
    }
    if(process.env.ORDER_RETURN_URL) {
      await page('Page.navigate',{url:base+process.env.ORDER_RETURN_URL});
      await until("!!document.querySelector('[data-order-action=return]')");
      await evaluate("document.querySelector('[data-order-action=return]').click()");
      await until("!!document.querySelector('#order-return-form')");
      await evaluate(`var f=document.querySelector('#order-return-form');f.elements.reason.value='Damaged item';f.elements.refund_preference.value='bank';f.elements.refund_preference.dispatchEvent(new Event('change'));f.elements.account_name.value='Browser Buyer';f.elements.sort_code.value='12-34-56';f.elements.account_number.value='12345678';f.requestSubmit();`);
      await until("document.querySelector('#real-orders').textContent.includes('Return: requested')");
      assert.equal(await evaluate("!!document.querySelector('[data-order-action=return]')"),false);
      assert.equal(await evaluate("document.querySelector('#real-orders').textContent.includes('12345678')"),false);
      await evaluate("document.querySelector('[data-review-line]').click()");
      await until("!!document.querySelector('#order-review-form')");
      await evaluate("var f=document.querySelector('#order-review-form');f.elements.text.value='Delivered purchase review';f.requestSubmit()");
      await until("!document.querySelector('#order-review-form')");
      assert.equal(await evaluate("!!document.querySelector('[data-review-line]')"),false);
      console.log('Delivered-order browser return and verified review passed.');
      return;
    }
    if(process.env.ORDER_BROWSER_FLOW==='1') {
      await page('Page.navigate',{url:base+'/product-detail/?product=browser-grams'});
      await until('!!window.TeraiCatalog?.getWishlist');
      await evaluate("document.getElementById('pdp-btn-wishlist').click();document.getElementById('pdp-btn-cart').click()");
      await until('window.TeraiCatalog.getWishlist().length===1 && window.TeraiCatalog.getCart().length===1');
      assert.equal(await evaluate('window.TeraiCatalog.getWishlist()[0].title'),'Browser grams');
      await page('Page.navigate',{url:base+'/product-detail/?product=browser-grams'});
      await until('!!window.TeraiCatalog?.getWishlist');
      assert.equal(await evaluate('window.TeraiCatalog.getWishlist().length'),1);
      await evaluate('window.TeraiCatalog.saveCart([])');
    }
    await page('Page.navigate',{url:base+'/shop/'});
    await until('!!window.TeraiCatalog?.getCart');
    const grams={id:process.env.DELIVERY_GRAMS_PRODUCT,title:'Browser grams',price:4,quantity:2,catalogVersion:2,image:''};
    const kilos={id:process.env.DELIVERY_KILOS_PRODUCT,title:'Browser kilograms',price:6,quantity:1,catalogVersion:2,image:''};
    await evaluate(`window.TeraiCatalog.saveCart(${JSON.stringify([grams])})`);
    await until("document.getElementById('drawer-shipping-val')?.textContent === '£2.50'");
    assert.equal(await evaluate("document.getElementById('drawer-total-val').textContent"),'£10.50');
    if(process.env.ORDER_BROWSER_FLOW==='1') {
      await page('Page.navigate',{url:base+'/cart/'});
      await until("document.getElementById('summary-shipping-fee')?.textContent === '£2.50'");
      assert.equal(await evaluate("document.getElementById('summary-grand-total').textContent"),'10.50');
      await evaluate("document.querySelector('.item-select-checkbox').click()");
      await until("document.getElementById('summary-grand-total').textContent === '—'");
      await evaluate("document.querySelector('.item-select-checkbox').click()");
      await until("document.getElementById('summary-grand-total').textContent === '10.50'");
      await evaluate("document.getElementById('checkout-button').click()");
      await until("document.getElementById('terai-account-dialog')?.open");
      assert.equal(await evaluate("document.getElementById('drawer-pane-2').classList.contains('active')"),false);
      assert.equal(await evaluate("getComputedStyle(document.getElementById('continue-as-guest')).display"),'inline-flex');
      await page('Page.navigate',{url:base+'/shop/'});
      await until('!!window.TeraiCatalog?.getCart');
    }
    await evaluate(`window.TeraiCatalog.saveCart(${JSON.stringify([grams,kilos])})`);
    await until("document.getElementById('drawer-shipping-val')?.textContent === '£5.00'");
    assert.equal(await evaluate("document.getElementById('drawer-total-val').textContent"),'£19.00');
    assert.equal(await evaluate("document.getElementById('checkout-delivery-eta-text').textContent"),'Estimated delivery: 2–4 days');
    await evaluate(`window.TeraiCatalog.saveCart(${JSON.stringify([{...kilos,quantity:5}])})`);
    await until("document.getElementById('drawer-shipping-val')?.textContent === 'Unavailable'");
    assert.equal(await evaluate("document.getElementById('drawer-total-val').textContent"),'—');
    if(process.env.ORDER_BROWSER_FLOW==='1') {
      await evaluate("window.teraiOpenLoginModal()");
      await until("document.getElementById('terai-account-dialog')?.open");
      assert.equal(await evaluate("getComputedStyle(document.getElementById('continue-as-guest')).display"),'none');
      await evaluate("window.teraiCloseLoginModal()");
      await evaluate(`window.TeraiCatalog.saveCart(${JSON.stringify([grams])});window.TeraiCatalog.openSideCart(1);document.getElementById("btn-drawer-proceed-checkout").click();`);
      await until("document.getElementById('terai-account-dialog')?.open");
      assert.equal(await evaluate("document.getElementById('drawer-pane-2').classList.contains('active')"),false);
      assert.equal(await evaluate("document.getElementById('continue-as-guest').hidden"),false);
      await evaluate("document.getElementById('continue-as-guest').click()");
      await until("document.getElementById('drawer-pane-2').classList.contains('active')");
      assert.equal(await evaluate("document.getElementById('terai-account-dialog').open"),false);
      assert.equal(await evaluate("!!document.querySelector('#drawer-pane-2 #continue-as-guest')"),false);
      const contact={name:'Browser Guest',email:'browser@example.com',phone:'07700900123',line1:'1 Test Street',city:'London',postcode:'SW1A 1AA'};
      await evaluate(`Object.entries(${JSON.stringify(contact)}).forEach(([key,value])=>document.querySelector('#order-contact-form [name="'+key+'"]').value=value);document.getElementById('btn-proceed-to-pay').click();`);
      await until("document.getElementById('drawer-pane-3').classList.contains('active')");
      await evaluate("document.getElementById('form-drawer-payment').requestSubmit()");
      if(process.env.ORDER_BROWSER_DEMO==='1') {
        await until("location.pathname==='/payment/' && document.getElementById('btn-final-pay')?.textContent.includes('Confirm demo payment')");
        assert.match(await evaluate("document.getElementById('panel-card').textContent"),/No money will be charged/);
        await evaluate("document.getElementById('btn-final-pay').click()");
      }
      await until("location.pathname==='/track-order/' && !!document.querySelector('#real-orders [data-order]')");
      if(process.env.ORDER_BROWSER_DEMO!=='1') {
      assert.match(await evaluate("document.getElementById('real-orders').textContent"),/pending payment/);
      const orderId=await evaluate("document.querySelector('[data-order]').dataset.order");
      const event={id:'evt_browser_test',type:'checkout.session.completed',livemode:false,data:{object:{
        id:'cs_browser_test',metadata:{order_id:orderId},payment_status:'paid',currency:'gbp',amount_total:1050,payment_intent:'pi_browser_test'}}};
      const raw=JSON.stringify(event),timestamp=String(Math.floor(Date.now()/1000));
      const signature=require('crypto').createHmac('sha256','whsec_browser_test').update(timestamp+'.'+raw).digest('hex');
      const response=await fetch(base+'/api/orders/webhook/stripe/',{method:'POST',headers:{'Content-Type':'application/json','Stripe-Signature':`t=${timestamp},v1=${signature}`},body:raw});
      assert.equal(response.status,200,await response.text());
      // Reload exercises missed-event recovery and the secure guest session.
      await page('Page.navigate',{url:base+'/track-order/?order='+orderId});
      }
      await until("document.querySelector('#real-orders [data-order]')?.textContent.includes('Payment: paid')");
      assert.equal(await evaluate("window.TeraiCatalog.getCart().length"),0);
      console.log('Guest browser checkout passed: contact/address, hosted-session redirect, signed webhook, tracking and basket clearing.');
    }
    console.log('Delivery UI passed: 300 gm boundary, mixed gm/kg basket, estimate, unsupported weight.');
  } finally {ws?.close();edge.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
