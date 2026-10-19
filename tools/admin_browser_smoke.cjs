// Run through RUN_ADMIN_BROWSER_TESTS=1 and Django's isolated browser test.
const {spawn} = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');
const assert = require('assert/strict');

(async () => {
  assert(process.env.ADMIN_TEST_URL, 'Run through web.tests.test_backoffice_browser');
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'terai-admin-test-'));
  const output = path.resolve('scratch/admin-preview');
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
    await page('Page.navigate',{url:process.env.ADMIN_TEST_URL+'/admin/'});
    await waitFor('document.querySelector(".login-form") && document.readyState === "complete"');
    assert((await evaluate('location.pathname'))==='/admin/login');
    await screenshot('login-desktop');
    await page('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false});
    await screenshot('login-mobile');
    assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'));
    await page('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
    await evaluate(`document.getElementById('id_username').value=${JSON.stringify(process.env.ADMIN_TEST_USER)};document.getElementById('id_password').value=${JSON.stringify(process.env.ADMIN_TEST_PASSWORD)};document.querySelector('.login-form').requestSubmit()`);
    await waitFor('document.querySelector(".dashboard-content") && document.readyState === "complete"');
    await screenshot('dashboard-desktop');
    assert.equal(await evaluate('Math.round(document.querySelector(".sidebar").getBoundingClientRect().width)'),80);
    await page('Input.dispatchMouseEvent',{type:'mouseMoved',x:35,y:200});await pause(350);
    assert.equal(await evaluate('Math.round(document.querySelector(".sidebar").getBoundingClientRect().width)'),258);
    await screenshot('dashboard-hover');
    await page('Input.dispatchMouseEvent',{type:'mouseMoved',x:500,y:200});await pause(350);
    assert.equal(await evaluate('Math.round(document.querySelector(".sidebar").getBoundingClientRect().width)'),80);
    await evaluate('document.querySelector(".pin-button").click()');
    await page('Page.reload');
    await waitFor('document.body.classList.contains("sidebar-pinned")');
    await pause(350);
    assert.equal(await evaluate('Math.round(document.querySelector(".workspace").getBoundingClientRect().left)'),258);
    await evaluate('document.querySelector(".pin-button").click()');
    await page('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false});await pause(350);
    assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'));
    assert(await evaluate('document.querySelector(".sidebar").inert'));
    await screenshot('dashboard-mobile');
    await evaluate('document.querySelector(".mobile-menu").click()');await pause(350);
    assert(await evaluate('document.querySelector(".workspace").inert && !document.querySelector(".sidebar").inert'));
    await screenshot('dashboard-mobile-menu');
    await page('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    assert(await evaluate('!document.body.classList.contains("sidebar-mobile-open")'));
    await evaluate('document.querySelector(".mobile-menu").click()');
    await evaluate('document.querySelector(".logout-button").click()');
    await waitFor('document.querySelector(".login-form") && document.readyState === "complete"');
    await page('Page.navigate',{url:process.env.ADMIN_TEST_URL+'/admin/'});
    await waitFor('document.querySelector(".login-form") && document.readyState === "complete"');
    assert.equal(exceptions.length,0,JSON.stringify(exceptions));
    console.log('PASS: real login, hover expansion/collapse, persistent pin, mobile navigation, Escape, protected routes, CSRF logout, and no JS exceptions.');
  } finally {ws?.close();edge.kill();}
})().catch(error=>{console.error(error);process.exitCode=1;});
