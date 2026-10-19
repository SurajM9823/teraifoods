// Run through RUN_ADMIN_BROWSER_TESTS=1 and Django's isolated browser test.
const {spawn} = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');
const assert = require('assert/strict');

(async () => {
  const base = process.env.CUSTOMER_TEST_URL || 'http://localhost:8080';
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'terai-customer-test-'));
  const output = path.resolve('scratch/category-storefront');
  fs.mkdirSync(output, {recursive: true});
  const edge = spawn('C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', ['--headless=new', '--disable-gpu', '--remote-debugging-port=0', '--user-data-dir=' + profile, 'about:blank'], {windowsHide: true, stdio:'ignore'});
  let ws;
  try {
    let port;
    for(let i=0;i<80;i++) {
      try {port=fs.readFileSync(path.join(profile,'DevToolsActivePort'),'utf8').split('\n')[0];break;} catch {await new Promise(r=>setTimeout(r,100));}
    }
    const endpoint=(await (await fetch(`http://127.0.0.1:${port}/json/version`)).json()).webSocketDebuggerUrl;
    ws=new WebSocket(endpoint);
    await new Promise(r=>ws.onopen=r);
    let id=0;const pending=new Map();const exceptions=[];
    ws.onmessage=e=>{const d=JSON.parse(e.data);if(d.id){pending.get(d.id)?.(d);pending.delete(d.id);}if(d.method==='Runtime.exceptionThrown')exceptions.push(d.params.exceptionDetails.text);};
    const send=(method,params={},sessionId)=>new Promise(resolve=>{const key=++id;pending.set(key,resolve);ws.send(JSON.stringify({id:key,method,params,...(sessionId?{sessionId}:{})}));});
    const target=(await send('Target.createTarget',{url:'about:blank'})).result.targetId;
    const session=(await send('Target.attachToTarget',{targetId:target,flatten:true})).result.sessionId;
    const page=(m,p)=>send(m,p,session);
    await page('Runtime.enable');await page('Page.enable');
    const evaluate=async expression=>(await page('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})).result?.result?.value;
    const pause=ms=>new Promise(r=>setTimeout(r,ms));
    const waitFor=async expression=>{for(let i=0;i<80;i++){if(await evaluate(expression))return;await pause(100);}throw new Error('Timed out: '+expression);};
    const screenshot=async name=>{await evaluate('document.fonts.ready.then(()=>true)');fs.writeFileSync(path.join(output,name+'.png'),Buffer.from((await page('Page.captureScreenshot',{format:'png'})).result.data,'base64'));};

    await page('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
    for (const route of ['/', '/shop/', '/contact/']) {
      await page('Page.navigate',{url:base+route});
      await waitFor('document.readyState === "complete" && document.querySelector(".site-categories [data-backend-category]")');
      assert.equal(await evaluate('new Set(Array.from(document.querySelectorAll("[data-backend-category]")).map(a=>a.dataset.backendCategory)).size'),11);
      assert(await evaluate('document.querySelector(".site-categories img").src.endsWith("apple.svg")'));
      if(route==='/') await screenshot('homepage-desktop');
    }
    await page('Page.navigate',{url:base+'/shop/?category=beverages'});
    await waitFor('document.readyState === "complete" && document.querySelector(".shop-product-card")');
    assert(await evaluate('Array.from(document.querySelectorAll(".shop-product-card")).filter(p=>getComputedStyle(p).display!=="none").every(p=>p.dataset.category==="beverages")'));
    for (const route of ['/', '/shop/', '/contact/']) {
      await page('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false});
      await page('Page.navigate',{url:base+route});
      await waitFor(`document.readyState === "complete" && document.querySelector('[data-drawer="site-categories-drawer"]')`);
      await evaluate(`document.querySelector('[data-drawer="site-categories-drawer"]').click()`);
      await waitFor('getComputedStyle(document.querySelector(".site-categories-drawer")).visibility === "visible"');
      await pause(600);
      assert.equal(await evaluate('document.querySelectorAll(".site-categories-drawer .site-categories > ul > li").length'),11);
      assert(await evaluate('(() => { const a=document.querySelector(".site-categories-drawer a"); const r=a.getBoundingClientRect(); return r.width>0 && r.height>0 && r.top>=0 && r.top<innerHeight; })()'));
      await screenshot('mobile-'+(route==='/'?'home':route.replaceAll('/','')));
    }
    console.log('PASS: shared menus on home/shop/contact, original artwork, category links, and mobile drawers.');
  } finally {ws?.close();edge.kill();}
})().catch(error=>{console.error(error);process.exitCode=1;});
