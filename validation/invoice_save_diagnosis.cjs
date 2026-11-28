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
    await call('Page.addScriptToEvaluateOnNewDocument',{source:`window.initDirty=[];const probe=setInterval(()=>{if(!window.frappe?.ui?.form?.Form)return;const p=frappe.ui.form.Form.prototype;const orig=p.dirty;p.dirty=function(){initDirty.push(new Error().stack);return orig.apply(this,arguments)};clearInterval(probe)},0);`});
    await call('Page.navigate', {url: base + '/app/sales-invoice/SI-92'});
    await wait('window.cur_frm?.doc?.name === "SI-92" && !!cur_frm.fields_dict.items');
    await pause(5000);
    console.log('INITIAL',await evaluate('JSON.stringify({dirty:cur_frm.is_dirty(),primary:cur_frm.page.btn_primary.text(),initDirty})'));
    console.log('SAVE',await evaluate('(async()=>{window.dirtyCalls=[];const orig=cur_frm.dirty;cur_frm.dirty=function(){dirtyCalls.push(new Error().stack);return orig.apply(this,arguments)};await cur_frm.save();await frappe.after_ajax();await new Promise(r=>setTimeout(r,4000));return JSON.stringify({dirty:cur_frm.is_dirty(),primary:cur_frm.page.btn_primary.text(),calls:dirtyCalls})})()'));
    console.log('RELOAD',await evaluate('(async()=>{dirtyCalls.length=0;window.valueCalls=[];const orig=frappe.model.set_value;frappe.model.set_value=function(dt,dn,field,value,...args){const d=locals[dt]?.[dn];if(d&&((typeof field==="string"&&d[field]!==value)||typeof field==="object"))valueCalls.push({dt,dn,field,value,stack:new Error().stack});return orig.call(this,dt,dn,field,value,...args)};await cur_frm.reload_doc();await frappe.after_ajax();await new Promise(r=>setTimeout(r,5000));return JSON.stringify({dirty:cur_frm.is_dirty(),primary:cur_frm.page.btn_primary.text(),calls:dirtyCalls,values:valueCalls})})()'));

})().catch(error => {console.error(error); process.exitCode=1;}).finally(async ()=>{
    socket?.close();
    try { process.kill(-chrome.pid, 'SIGTERM'); } catch (error) { if (error.code !== 'ESRCH') throw error; }
    fs.rmSync(profile,{recursive:true,force:true,maxRetries:20,retryDelay:100});
});
