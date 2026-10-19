// Run through RUN_ADMIN_BROWSER_TESTS=1 and Django's isolated browser test.
const {spawn} = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');
const assert = require('assert/strict');

(async () => {
  const base = process.env.CUSTOMER_TEST_URL;
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'terai-customer-test-'));
  const output = path.resolve('scratch/customer-navigation');
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
    await page('Page.navigate',{url:base+'/'});
    await waitFor('document.querySelector(".login-form-button") && document.readyState === "complete"');
    await evaluate('document.querySelector(".login-form-button a").click()');
    await waitFor('document.querySelector("#terai-account-dialog iframe")?.contentDocument?.querySelector("input[name=login]")');
    await evaluate(`const d=document.querySelector('#terai-account-dialog iframe').contentDocument;d.querySelector('[name=login]').value='customer@example.test';d.querySelector('[name=password]').value=${JSON.stringify(process.env.CUSTOMER_TEST_PASSWORD)};d.querySelector('[name=password]').form.requestSubmit()`);
    await waitFor(`document.querySelector('meta[name="customer-authenticated"]')?.content === "true" && location.pathname === "/"`);
    assert(await evaluate('!document.querySelector("#terai-account-dialog")?.open'));
    await evaluate('document.querySelector(".login-form-button a").click()');
    await waitFor('location.pathname === "/manage-profile/" && document.querySelector(".account-dashboard-wrapper")');
    assert(await evaluate('document.body.innerText.includes("customer@example.test")'));
    assert(await evaluate('!document.querySelector(".auth-card")'));
    await screenshot('profile-desktop');
    await page('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false});
    await screenshot('profile-mobile');
    assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'));
    await evaluate(`document.querySelector('form[action="/accounts/logout/"]').requestSubmit()`);
    await waitFor('location.pathname === "/" && document.readyState === "complete"');
    await page('Page.navigate',{url:base+'/accounts/login/'});
    await waitFor('document.querySelector("input[name=login]") && document.readyState === "complete"');
    await evaluate(`document.querySelector('[name=login]').value='customer@example.test';document.querySelector('[name=password]').value=${JSON.stringify(process.env.CUSTOMER_TEST_PASSWORD)};document.querySelector('[name=password]').form.requestSubmit()`);
    await waitFor(`location.pathname === "/" && document.querySelector('meta[name="customer-authenticated"]')?.content === "true"`);
    console.log('PASS: popup and standalone login return home; user icon opens full profile; mobile profile fits.');
  } finally {ws?.close();edge.kill();}
})().catch(error=>{console.error(error);process.exitCode=1;});
