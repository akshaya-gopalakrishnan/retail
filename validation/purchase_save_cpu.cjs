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
    await call('Page.addScriptToEvaluateOnNewDocument',{source:'localStorage.clear(); indexedDB.deleteDatabase("retail_local_draft_recovery");'});
    await call('Network.enable'); await call('Runtime.enable'); await call('Page.enable');
    await call('Network.setCookie', {name: 'sid', value: process.env.RETAIL_SID, url: base});
    await call('Emulation.setDeviceMetricsOverride', {width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false});
    for(const [dt,name] of [['Purchase Invoice','PI-56']]) {
      await call('Page.navigate',{url:base+'/app/'+frappeSlug(dt)+'/'+name});
      await wait(`window.cur_frm?.doc?.name===${JSON.stringify(name)} && !!cur_frm.fields_dict.items`);
      await evaluate(`(async()=>{const response=await frappe.call({method:'frappe.client.get',args:{doctype:${JSON.stringify(dt)},name:${JSON.stringify(name)}}});const copy=frappe.model.copy_doc(response.message);copy.bill_no='';copy.custom_bill_number='';for(const r of copy.items){r.serial_and_batch_bundle=null;r.rejected_serial_and_batch_bundle=null;}window.perfCopy=copy.name;await frappe.set_route('Form',copy.doctype,copy.name);return true;})()`);
      await wait('cur_frm?.doc?.name===window.perfCopy && cur_frm.is_new()');
      await pause(3500);
      await call('Profiler.enable');await call('Profiler.start');
      console.log('BROWSER',dt,await evaluate(`(async()=>{
        const times=[];const trigger=cur_frm.script_manager.trigger;
        cur_frm.script_manager.trigger=function(event,...args){const start=performance.now();return Promise.resolve(trigger.call(this,event,...args)).finally(()=>times.push({event,ms:Math.round(performance.now()-start)}));};
        const start=performance.now();await Promise.race([cur_frm.save(),new Promise(r=>setTimeout(r,20000))]);await new Promise(r=>setTimeout(r,500));
        return JSON.stringify({save_ms:Math.round(performance.now()-start)-500,new:cur_frm.is_new(),dirty:cur_frm.is_dirty(),dialogs:Array.from(document.querySelectorAll('.modal.show')).map(m=>m.innerText),events:times,resources:performance.getEntriesByType('resource').filter(r=>r.startTime>=start&&r.name.includes('/api/')).map(r=>({url:r.name.split('/api/')[1],ms:Math.round(r.duration)}))});
      })()`));
      const prof=await call('Profiler.stop');fs.writeFileSync('/tmp/purchase_save_cpu.json',JSON.stringify(prof.profile));
    }
    function frappeSlug(dt){return dt.toLowerCase().replaceAll(' ','-');}
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
 socket?.close();try{process.kill(-chrome.pid,'SIGTERM');}catch(e){}
 fs.rmSync(profile,{recursive:true,force:true,maxRetries:20,retryDelay:100});
});
