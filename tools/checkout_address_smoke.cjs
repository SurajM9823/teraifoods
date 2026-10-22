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
    const navigate=async suffix=>{await page('Page.navigate',{url:base+suffix});await until("!!document.getElementById('order-contact-form') && location.search==='"+new URL(base+suffix).search+"'");};
    await navigate('/shop/?address-test=guest');
    await evaluate(`Object.entries({name:'Guest Buyer',email:'guest@example.com',phone:'07700900123',line1:'1 Guest Street',city:'London',postcode:'SW1A 1AA'}).forEach(([key,value])=>document.querySelector('#order-contact-form [name="'+key+'"]').value=value);document.getElementById('remember-checkout').checked=true;document.getElementById('order-contact-form').requestSubmit()`);
    await until("JSON.parse(localStorage.getItem('teraifood_uk_address'))?.remember_checkout");
    await evaluate('sessionStorage.clear()');
    await navigate('/shop/?address-test=restore');
    assert.equal(await evaluate("document.getElementById('checkout-line1').value"),'1 Guest Street');
    await evaluate("document.getElementById('clear-checkout-details').click()");
    assert.equal(await evaluate("localStorage.getItem('teraifood_uk_address')"),null);
    assert.equal(await evaluate("document.getElementById('checkout-line1').value"),'');
    // A guest address must not be silently adopted by the account on sign-in.
    await evaluate(`localStorage.setItem('teraifood_uk_address',JSON.stringify({name:'Guest',line1:'Guest must not merge',remember_checkout:true,expires_at:Date.now()+86400000}))`);
    const [cookieName,...cookieValue]=process.env.CHECKOUT_AUTH_COOKIE.split('=');
    await page('Network.setCookie',{name:cookieName,value:cookieValue.join('='),url:base,path:'/'});
    await navigate('/shop/?address-test=account');
    await until("document.getElementById('checkout-line1').value==='2 Account Street'");
    assert.equal(await evaluate("document.getElementById('checkout-email').value"),'owner@example.com');
    assert.equal(await evaluate("document.querySelectorAll('#checkout-saved-address option').length"),2);
    await evaluate("document.getElementById('checkout-saved-address').value='';document.getElementById('checkout-line1').value='3 Account Street';document.getElementById('remember-checkout').checked=true;document.getElementById('order-contact-form').requestSubmit()");
    await until("document.querySelectorAll('#checkout-saved-address option').length===3");
    await evaluate("document.getElementById('order-contact-form').requestSubmit()");
    await new Promise(r=>setTimeout(r,400));
    assert.equal(await evaluate("document.querySelectorAll('#checkout-saved-address option').length"),3);
    await evaluate("window.confirm=()=>true;const select=document.getElementById('checkout-saved-address');select.value=[...select.options].find(o=>o.textContent.includes('3 Account Street')).value;document.getElementById('delete-checkout-address').click()");
    await until("document.querySelectorAll('#checkout-saved-address option').length===2");
    console.log('Address browser passed: guest consent/restore/clear, account isolation/default restore, explicit save/dedup/delete.');
  } finally {ws?.close();edge.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
