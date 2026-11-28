// Real Chromium validation; credentials come only from the temporary Python harness.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const WebSocket = require('../../frappe/node_modules/ws');
const assert = require('node:assert/strict');
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'purchase-packing-chrome-'));
const chrome = spawn('/home/adler/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome', [
    '--headless=new', '--no-sandbox', '--disable-dev-shm-usage', '--remote-debugging-port=0',
    '--autoplay-policy=no-user-gesture-required',
    '--host-resolver-rules=MAP retail-test.localhost 127.0.0.1', '--no-proxy-server', '--user-data-dir=' + profile
], {stdio: 'ignore', detached: true});
let socket;
(async () => {
    const portFile = path.join(profile, 'DevToolsActivePort');
    for (let i = 0; i < 100 && !fs.existsSync(portFile); i++) await pause(100);
    const [port, endpoint] = fs.readFileSync(portFile, 'utf8').trim().split('\n');
    socket = new WebSocket('ws://127.0.0.1:' + port + endpoint);
    await new Promise(resolve => socket.once('open', resolve));
    let id = 0;
    const pending = new Map();
    const errors = [];
    socket.on('message', bytes => {
        const msg = JSON.parse(bytes);
        if (msg.id) {
            const waiter = pending.get(msg.id);
            pending.delete(msg.id);
            if (msg.error) waiter.reject(new Error(JSON.stringify(msg.error)));
            else waiter.resolve(msg.result);
        }
        if (msg.method === 'Runtime.exceptionThrown') errors.push(msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text);
    });
    const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
        const next = ++id; pending.set(next, {resolve, reject});
        socket.send(JSON.stringify({id: next, method, params, sessionId}));
    });
    const target = await send('Target.createTarget', {url: 'about:blank'});
    const session = (await send('Target.attachToTarget', {targetId: target.targetId, flatten: true})).sessionId;
    const call = (method, params) => send(method, params, session);
    const evaluate = async expression => {
        const result = await call('Runtime.evaluate', {expression, awaitPromise: true, returnByValue: true});
        if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
        return result.result.value;
    };
    const wait = async expression => {
        for (let i = 0; i < 100; i++) { if (await evaluate(expression)) return; await pause(300); }
        throw new Error('Timeout: ' + expression + '; ' + JSON.stringify(errors));
    };
    const base = process.env.RETAIL_URL;
    await call('Network.enable'); await call('Runtime.enable'); await call('Page.enable');
    await call('Network.setCookie', {name: 'sid', value: process.env.RETAIL_SID, url: base});
    await call('Emulation.setDeviceMetricsOverride', {width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false});
    await call('Page.navigate',{url:base+'/app/sales-invoice/SI-92'});
    await wait('window.cur_frm?.doc?.name==="SI-92" && !!cur_frm.fields_dict.items');
    await pause(5000);
    console.log(await evaluate(`(async()=>{
      const grid=cur_frm.fields_dict.items.grid;
      const columns=grid.visible_columns.map(c=>Array.isArray(c)?c[0]?.fieldname:c.fieldname);
      if(!columns.includes('batch_no')||!columns.includes('serial_no'))throw Error('Missing tracking columns '+JSON.stringify(columns));
      await cur_frm.script_manager.trigger('before_submit');
      await new Promise(r=>setTimeout(r,500));
      const d=window.cur_dialog;
      if(!d||d.title!=='Enter Batch / Serial Numbers')throw Error('Missing tracking popup');
      const fields=d.fields.filter(f=>f.fieldname?.startsWith('tracking_'));
      if(!fields.length)throw Error('No missing fields');
      const buttons=d.fields.filter(f=>f.fieldtype==='Button' && f.label==='Create Batch');if(!buttons.length)throw Error('Missing Create Batch button');const output={create_batch_buttons:buttons.length,columns,popup:d.title,missing_fields:fields.length,labels:fields.map(f=>f.label),docstatus:cur_frm.doc.docstatus};
      d.hide();return JSON.stringify(output);
    })()`));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
 socket?.close();try{process.kill(-chrome.pid,'SIGTERM');}catch(e){}
 fs.rmSync(profile,{recursive:true,force:true,maxRetries:20,retryDelay:100});
});
