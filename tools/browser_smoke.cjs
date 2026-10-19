const {spawn} = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

(async () => {
  const baseURL = process.env.STOREFRONT_TEST_URL || 'http://127.0.0.1:8000';
  fs.mkdirSync('scratch', {recursive:true});
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'terai-django-'));
  const edge = spawn('C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', ['--headless=new', '--disable-gpu', '--remote-debugging-port=9377', '--user-data-dir=' + profile, 'about:blank'], {windowsHide: true, stdio: 'ignore'});
  let ws;
  try {
    let endpoint;
    for(let i=0;i<50;i++) {
      try { endpoint = (await (await fetch('http://127.0.0.1:9377/json/version')).json()).webSocketDebuggerUrl; break; } catch { await new Promise(r=>setTimeout(r,200)); }
    }
    ws = new WebSocket(endpoint);
    await new Promise(r=>ws.onopen=r);
    let id=0; const pending = new Map(); const errors=[];
    ws.onmessage = e => {const d=JSON.parse(e.data); if(d.id) {pending.get(d.id)?.(d);pending.delete(d.id);} if(d.method==='Runtime.exceptionThrown') errors.push(d.params.exceptionDetails.text + ': ' + (d.params.exceptionDetails.exception?.description || ''));};
    const send=(method,params={},sessionId)=>new Promise(resolve=>{const key=++id;pending.set(key,resolve);ws.send(JSON.stringify({id:key,method,params,...(sessionId?{sessionId}:{})}));});
    const target=(await send('Target.createTarget',{url:'about:blank'})).result.targetId;
    const session=(await send('Target.attachToTarget',{targetId:target,flatten:true})).result.sessionId;
    const page=(m,p)=>send(m,p,session);
    await page('Runtime.enable');
    await page('Page.enable');
    const evaluate=async expression=>(await page('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})).result?.result?.value;
    const pages=(await (await fetch(baseURL + '/api/pages/')).json()).pages;
    const results=[];
    for(const width of (process.env.INTERACTIONS_ONLY ? [] : [1440,390])) {
      await page('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
      for(const route of pages) {
        errors.length=0;
        await page('Page.navigate',{url:baseURL+route.url});
        await new Promise(r=>setTimeout(r,650));
        for(let i=0;i<15;i++){if(await evaluate('document.readyState === "complete"')) break; await new Promise(r=>setTimeout(r,200));}
        const info=await evaluate(`({title:document.title,overflow:document.documentElement.scrollWidth>innerWidth+2,broken:[...document.images].filter(i=>i.complete && !i.naturalWidth).map(i=>i.getAttribute('src')),links:[...document.querySelectorAll('a[href]')].map(a=>a.href).filter(u=>u.includes('127.0.0.1')&&u.includes('.html'))})`);
        results.push({width,route:route.url,...info,errors:[...errors]});
        if(['home','shop','cart','blogs-himalayan-spices-guide','product-detail'].includes(route.slug)) {
          const screenshot=(await page('Page.captureScreenshot',{format:'png'})).result.data;
          fs.writeFileSync(path.join('scratch',`django-${route.slug}-${width}.png`),Buffer.from(screenshot,'base64'));
        }
      }
    }
    if(results.length) fs.writeFileSync('scratch/django-browser-results.json',JSON.stringify(results,null,2));
    await page('Page.navigate',{url:baseURL + '/shop/'});
    await new Promise(r=>setTimeout(r,1500));
    for(let i=0;i<60;i++){if(await evaluate('document.readyState === "complete"')) break; await new Promise(r=>setTimeout(r,200));}
    await new Promise(r=>setTimeout(r,500));
    const added=await evaluate(`(()=>{localStorage.removeItem('teraifood_cart');const button=document.querySelector('.btn-cart-pill, .button.ajax_add_to_cart, .button.add_to_cart_button'); if(!button)return {error:'No cart button'};button.click();return JSON.parse(localStorage.getItem('teraifood_cart')||'[]');})()`);
    await page('Page.navigate',{url:baseURL + '/cart/'});
    await new Promise(r=>setTimeout(r,1200));
    for(let i=0;i<60;i++){if(await evaluate('document.readyState === "complete"')) break; await new Promise(r=>setTimeout(r,200));}
    const cart=await evaluate(`({stored:JSON.parse(localStorage.getItem('teraifood_cart')||'[]'),text:document.body.textContent})`);
    const interactions={added,cartDrawerContainsProduct:added.length>0 && cart.text.includes(added[0].title),correctPrice:added[0]?.price===8.99,persisted:JSON.stringify(added)===JSON.stringify(cart.stored)};
    fs.writeFileSync('scratch/django-interaction-results.json',JSON.stringify(interactions,null,2));
    console.log(JSON.stringify({pagesChecked:results.length,interactions},null,2));
    if(!interactions.cartDrawerContainsProduct || !interactions.correctPrice || !interactions.persisted) process.exitCode=1;
  } finally {ws?.close(); edge.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
