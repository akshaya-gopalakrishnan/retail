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
    await call('Page.navigate',{url:base+'/app/purchase-invoice/PI-56'});
    await wait('window.cur_frm?.doc?.name==="PI-56" && !!cur_frm.fields_dict.items');
    await pause(4000);
    console.log(await evaluate(`(async()=>{
      await cur_frm.script_manager.trigger('before_submit');
      await new Promise(resolve=>setTimeout(resolve,500));
      const d=window.cur_dialog;
      const fields=d.fields.filter(f=>f.fieldname?.startsWith('tracking_'));
      const serial=fields.find(f=>f.fieldtype==='Small Text');
      const auto=fields.some(f=>f.label.includes('Row 48:'));
      if(!serial.description.includes('Required serial numbers: 1.'))throw Error(serial.description);
      if(auto)throw Error('Auto batch still required');
      const values=Object.fromEntries(fields.map(f=>[f.fieldname,f.fieldtype==='Small Text'?'LOCAL-CHECK-ONLY':'LOCAL-CHECK-ONLY']));
      const original=cur_frm.save;let called=false;
      cur_frm.save=async(action,callback)=>{called=true;callback({});};
      try{await d.primary_action(values);}finally{cur_frm.save=original;}
      await new Promise(resolve=>setTimeout(resolve,500));return JSON.stringify({serial_description:serial.description,auto_batch_prompt:auto,save_called:called,popup_closed:!d.$wrapper.is(':visible'),docstatus:cur_frm.doc.docstatus});
    })()`));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
 socket?.close();try{process.kill(-chrome.pid,'SIGTERM');}catch(e){}
 fs.rmSync(profile,{recursive:true,force:true,maxRetries:20,retryDelay:100});
});
