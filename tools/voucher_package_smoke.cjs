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
    await page('Page.navigate',{url:base+'/'});
    await until("!!document.querySelector('a[href=\"/product-detail/?product=browser-package\"]')");
    await evaluate("document.querySelector('a[href=\"/product-detail/?product=browser-package\"]').click()");
    await until("!!window.TeraiCatalog?.addDetail");
    assert.match(await evaluate('document.body.textContent'),/Package contents/);
    await evaluate("document.getElementById('pdp-btn-cart').click();window.TeraiCatalog.openCheckout()");
    await until("document.getElementById('terai-account-dialog')?.open");
    await evaluate("document.getElementById('continue-as-guest').click()");
    await until("document.getElementById('drawer-pane-2').classList.contains('active')");
    const contact={name:'Voucher Buyer',email:'voucher@example.invalid',phone:'07700900123',line1:'1 Example Street',city:'London',postcode:'SW1A 1AA'};
    await evaluate(`Object.entries(${JSON.stringify(contact)}).forEach(([key,value])=>document.querySelector('#order-contact-form [name="'+key+'"]').value=value);document.getElementById('checkout-promo-input').value=${JSON.stringify(process.env.TEST_VOUCHER_CODE)};document.getElementById('btn-checkout-apply-promo').click();`);
    await until("document.getElementById('checkout-promo-feedback').textContent.includes('Remaining to pay: GBP 0')");
    assert.match(await evaluate("document.getElementById('checkout-promo-feedback').textContent"),/unused value is forfeited/);
    await evaluate("document.getElementById('btn-proceed-to-pay').click()");
    await until("document.getElementById('drawer-pane-3').classList.contains('active')");
    assert.equal(await evaluate("document.getElementById('btn-drawer-confirm-pay').textContent"),'Confirm order');
    await evaluate("document.getElementById('form-drawer-payment').requestSubmit()");
    await until("location.pathname==='/track-order/' && document.getElementById('real-orders')?.textContent.includes('Payment: paid')");
    assert.match(await evaluate("document.getElementById('real-orders').textContent"),/Voucher applied/);
    assert.equal(await evaluate('window.TeraiCatalog.getCart().length'),0);
    console.log('Package banner, details, basket, voucher validation and fully funded checkout passed.');
  } finally {ws?.close();edge.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
