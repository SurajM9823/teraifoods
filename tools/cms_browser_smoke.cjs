// Run through RUN_ADMIN_BROWSER_TESTS=1 and Django's isolated browser test.
const {spawn} = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');
const assert = require('assert/strict');

(async () => {
  assert(process.env.ADMIN_TEST_URL, 'Run through web.tests.test_backoffice_browser');
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'terai-admin-test-'));
  const output = path.resolve('scratch/cms-preview');
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
    await page('Page.navigate',{url:process.env.ADMIN_TEST_URL+'/admin/cms/'});
    await waitFor('document.querySelector(".login-form") && document.readyState === "complete"');
    await evaluate(`document.getElementById('id_username').value=${JSON.stringify(process.env.ADMIN_TEST_USER)};document.getElementById('id_password').value=${JSON.stringify(process.env.ADMIN_TEST_PASSWORD)};document.querySelector('.login-form').requestSubmit()`);
    await waitFor('document.querySelector(".cms-page") && document.readyState === "complete"');
    assert.equal(await evaluate('document.querySelectorAll(".cms-grid article").length'),6);
    await screenshot('cms-desktop');
    await evaluate('document.querySelector(".cms-grid article a").click()');
    await waitFor('document.querySelector("#id_title") && document.readyState === "complete"');
    await evaluate('document.querySelector("#id_title").value="Fresh groceries for your table";document.querySelector(".cms-form").requestSubmit()');
    await waitFor('document.querySelector(".cms-grid") && document.readyState === "complete"');
    await page('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false});
    await screenshot('cms-mobile');
    assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'));
    for(const width of [1440,390]) {
      await page('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
      await page('Page.navigate',{url:process.env.ADMIN_TEST_URL+'/'});
      await waitFor('document.querySelector(".klb-slider .slick-list") && document.readyState === "complete"');
      assert(await evaluate('document.querySelector(".klb-slider").innerText.includes("Fresh groceries for your table")'));
      assert(await evaluate('!document.querySelector(".klb-slider .banner-price")'));
      assert(await evaluate('Array.from(document.querySelectorAll(".klb-slider img")).every(i=>i.complete && i.naturalWidth>0)'));
      assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'));
      await evaluate('document.querySelector(".klb-slider").scrollIntoView({block:"center"})');
      await pause(400);
      await screenshot('carousel-'+width);
    }
    console.log('PASS: CMS login, editor save, shared homepage content, desktop/mobile layout and carousel images.');
  } finally {ws?.close();edge.kill();}
})().catch(error=>{console.error(error);process.exitCode=1;});
