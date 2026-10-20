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
    await page('Page.navigate',{url:base+'/shop/'});
    await until('!!window.TeraiCatalog?.getCart');
    const grams={id:process.env.DELIVERY_GRAMS_PRODUCT,title:'Browser grams',price:4,quantity:2,catalogVersion:2,image:''};
    const kilos={id:process.env.DELIVERY_KILOS_PRODUCT,title:'Browser kilograms',price:6,quantity:1,catalogVersion:2,image:''};
    await evaluate(`window.TeraiCatalog.saveCart(${JSON.stringify([grams])})`);
    await until("document.getElementById('drawer-shipping-val')?.textContent === '£2.50'");
    assert.equal(await evaluate("document.getElementById('drawer-total-val').textContent"),'£10.50');
    await evaluate(`window.TeraiCatalog.saveCart(${JSON.stringify([grams,kilos])})`);
    await until("document.getElementById('drawer-shipping-val')?.textContent === '£5.00'");
    assert.equal(await evaluate("document.getElementById('drawer-total-val').textContent"),'£19.00');
    assert.equal(await evaluate("document.getElementById('checkout-delivery-eta-text').textContent"),'Estimated delivery: 2–4 days');
    await evaluate(`window.TeraiCatalog.saveCart(${JSON.stringify([{...kilos,quantity:5}])})`);
    await until("document.getElementById('drawer-shipping-val')?.textContent === 'Unavailable'");
    assert.equal(await evaluate("document.getElementById('drawer-total-val').textContent"),'—');
    if(process.env.ORDER_BROWSER_FLOW==='1') {
      await evaluate(`window.TeraiCatalog.saveCart(${JSON.stringify([grams])});window.TeraiCatalog.openCheckout();`);
      await until("document.getElementById('drawer-pane-2').classList.contains('active')");
      const contact={name:'Browser Guest',email:'browser@example.com',phone:'07700900123',line1:'1 Test Street',city:'London',postcode:'SW1A 1AA'};
      await evaluate(`Object.entries(${JSON.stringify(contact)}).forEach(([key,value])=>document.querySelector('#order-contact-form [name="'+key+'"]').value=value);document.getElementById('btn-proceed-to-pay').click();`);
      await until("document.getElementById('drawer-pane-3').classList.contains('active')");
      await evaluate("document.getElementById('form-drawer-payment').requestSubmit()");
      await until("location.pathname==='/track-order/' && !!document.querySelector('#real-orders [data-order]')");
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
      await until("document.querySelector('#real-orders [data-order]')?.textContent.includes('Payment: paid')");
      assert.equal(await evaluate("window.TeraiCatalog.getCart().length"),0);
      console.log('Guest browser checkout passed: contact/address, hosted-session redirect, signed webhook, tracking and basket clearing.');
    }
    console.log('Delivery UI passed: 300 gm boundary, mixed gm/kg basket, estimate, unsupported weight.');
  } finally {ws?.close();edge.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
