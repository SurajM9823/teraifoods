// Capture the approved page at desktop, tablet and mobile widths.
const {spawn} = require('child_process');
const fs = require('fs'), os = require('os'), path = require('path');
(async () => {
  const base = process.env.STOREFRONT_TEST_URL || 'http://127.0.0.1:8012';
  const output = process.env.VISUAL_OUTPUT || 'scratch/product-baseline/screenshots';
  fs.mkdirSync(output, {recursive:true});
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'terai-visual-'));
  const edge = spawn('C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    ['--headless=new','--disable-gpu','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],
    {windowsHide:true,stdio:'ignore'});
  let ws;
  try {
    let port;
    for(let i=0;i<100;i++){try{port=fs.readFileSync(path.join(profile,'DevToolsActivePort'),'utf8').split('\n')[0];break;}catch{await new Promise(r=>setTimeout(r,100));}}
    ws = new WebSocket((await (await fetch(`http://127.0.0.1:${port}/json/version`)).json()).webSocketDebuggerUrl);
    await new Promise(r=>ws.onopen=r);
    let id=0;const pending=new Map();
    ws.onmessage=e=>{const d=JSON.parse(e.data);if(d.id){pending.get(d.id)?.(d);pending.delete(d.id);}};
    const send=(method,params={},sessionId)=>new Promise(resolve=>{const key=++id;pending.set(key,resolve);ws.send(JSON.stringify({id:key,method,params,...(sessionId?{sessionId}:{})}));});
    const target=(await send('Target.createTarget',{url:'about:blank'})).result.targetId;
    const session=(await send('Target.attachToTarget',{targetId:target,flatten:true})).result.sessionId;
    const page=(m,p)=>send(m,p,session);
    await page('Page.enable');
    for(const width of [1440,768,390]){
      await page('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
      for(const [name,route] of Object.entries({home:'/',shop:'/shop/',detail:'/product-detail/',category:'/shop/?category=beverages',search:'/shop/?q=rice'})){
        await page('Page.navigate',{url:base+route});
        await new Promise(r=>setTimeout(r,1800));
        await page('Runtime.evaluate',{expression:'document.fonts.ready',awaitPromise:true});
        fs.writeFileSync(path.join(output,`${name}-${width}.png`),Buffer.from((await page('Page.captureScreenshot',{format:'png'})).result.data,'base64'));
      }
    }
    console.log('Captured 15 viewport screenshots in '+output);
  }finally{ws?.close();edge.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
