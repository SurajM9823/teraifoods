// Uses products and rates from delivery.test_browser's isolated database.
const {spawn} = require('child_process');
const fs = require('fs'), os = require('os'), path = require('path'), assert = require('assert/strict');

(async () => {
  const base = 'http://127.0.0.1:8080';

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
    for (const width of [390, 1366]) {
      await page('Emulation.setDeviceMetricsOverride',{width,height:844,deviceScaleFactor:1,mobile:width<600});
      await page('Page.navigate',{url:'about:blank'});
      await until("location.href==='about:blank'");
      await page('Page.navigate',{url:base+'/'});
      await until("document.readyState==='complete' && !!window.teraiCloseNavigationDrawers && !!window.TeraiCatalog?.openSideCart");
      await evaluate("window.probeClicks=0;const probe=document.createElement('button');probe.id='click-probe';probe.textContent='Click test';probe.style.cssText='position:fixed;left:10px;top:400px;width:100px;height:45px;z-index:1000000';probe.onclick=()=>window.probeClicks++;document.body.append(probe)");
      for(let i=0;i<12;i++){
        await evaluate("document.querySelector('[data-drawer=site-categories-drawer]').click();window.TeraiCatalog.openSideCart();document.querySelector('#drawer-close-btn').click()");
        // Exit animations must not intercept clicks, even before they finish.
        await page('Input.dispatchMouseEvent',{type:'mousePressed',x:40,y:420,button:'left',clickCount:1});
        await page('Input.dispatchMouseEvent',{type:'mouseReleased',x:40,y:420,button:'left',clickCount:1});
        assert.equal(await evaluate('window.probeClicks'),i+1,'Page must accept a real click immediately after cart close');
      }
      await evaluate("window.teraiOpenLoginModal();window.teraiCloseLoginModal();window.teraiOpenLoginModal()");
      await new Promise(r=>setTimeout(r,300));
      assert.equal(await evaluate("document.querySelector('#terai-account-dialog').open"),true);
      assert(!await evaluate("document.querySelector('#terai-account-dialog iframe').src.includes('about:blank')"),'An older close event must not blank a reopened modal');
      await evaluate("window.teraiCloseLoginModal()");
      await page('Input.dispatchMouseEvent',{type:'mousePressed',x:40,y:420,button:'left',clickCount:1});
      await page('Input.dispatchMouseEvent',{type:'mouseReleased',x:40,y:420,button:'left',clickCount:1});
      assert.equal(await evaluate('window.probeClicks'),13);
      await evaluate("window.TeraiCatalog.openSideCart();window.dispatchEvent(new PageTransitionEvent('pagehide'));window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}))");
      assert.equal(await evaluate("document.querySelector('.cart-widget-side').classList.contains('open')"),false);
      console.log('Overlay regression passed at '+width+'px: 12 sidebar/cart cycles, real clicks, rapid login reopen and page restoration cleanup.');
    }
  } finally {ws?.close();edge.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});

