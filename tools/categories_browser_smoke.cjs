// Run through RUN_ADMIN_BROWSER_TESTS=1 and Django's isolated browser test.
const {spawn} = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');
const assert = require('assert/strict');

(async () => {
  assert(process.env.ADMIN_TEST_URL, 'Run through web.tests.test_backoffice_browser');
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'terai-admin-test-'));
  const output = path.resolve('scratch/categories-preview');
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
    const base = process.env.ADMIN_TEST_URL;
    await page('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
    await page('Page.navigate',{url:base+'/admin/categories/'});
    await waitFor('document.querySelector(".login-form") && document.readyState === "complete"');
    await evaluate(`document.getElementById('id_username').value=${JSON.stringify(process.env.ADMIN_TEST_USER)};document.getElementById('id_password').value=${JSON.stringify(process.env.ADMIN_TEST_PASSWORD)};document.querySelector('.login-form').requestSubmit()`);
    await waitFor('document.querySelector(".categories-page") && document.readyState === "complete"');
    await evaluate('document.querySelector(".category-heading a").click()');
    await waitFor('document.querySelector("#id_name") && document.readyState === "complete"');
    await evaluate(`document.querySelector('#id_name').value='Fresh Vegetables';document.querySelector('#id_icon').value='fa-solid fa-carrot';document.querySelector('#id_icon').dispatchEvent(new Event('change'))`);
    assert.equal(await evaluate('document.querySelector("#category-icon-preview").className'),'fa-solid fa-carrot');
    await screenshot('category-editor');
    await evaluate('document.querySelector(".category-form").requestSubmit()');
    await waitFor('document.querySelector(".category-group h2")?.textContent === "Fresh Vegetables"');
    await evaluate(`document.querySelector('a[href*="subcategory/new"]').click()`);
    await waitFor('document.querySelector("#id_category") && document.readyState === "complete"');
    assert(await evaluate('!!document.querySelector("#id_category").value'));
    await evaluate(`document.querySelector('#id_name').value='Carrots';document.querySelector('#id_icon').value='fa-solid fa-leaf';document.querySelector('.category-form').requestSubmit()`);
    await waitFor('document.querySelector(".subcategory-list h3")?.textContent === "Carrots"');
    await screenshot('categories-desktop');
    await evaluate('document.querySelector(".category-group header form").requestSubmit()');
    await waitFor('document.querySelector(".subcategory-list .category-status")?.textContent === "Hidden by parent"');
    await page('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false});
    await screenshot('categories-mobile');
    assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'));
    await evaluate(`document.querySelector('.subcategory-list a[href*="/edit/"]').click()`);
    await waitFor('document.querySelector("#id_name") && document.readyState === "complete"');
    await evaluate(`document.querySelector('#id_name').value='Organic Carrots';document.querySelector('.category-form').requestSubmit()`);
    await waitFor('document.querySelector(".subcategory-list h3")?.textContent === "Organic Carrots"');
    console.log('PASS: category and child creation, parent preselection, icon preview, deactivate, edit, and mobile layout.');
  } finally {ws?.close();edge.kill();}
})().catch(error=>{console.error(error);process.exitCode=1;});
