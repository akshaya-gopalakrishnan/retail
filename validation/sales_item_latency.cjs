// Real Chromium validation; credentials come only from the temporary Python harness.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const WebSocket = require('../../frappe/node_modules/ws');
const assert = require('node:assert/strict');
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'sales-item-chrome-'));
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
    await call('Page.navigate', {url: base + '/app/sales-invoice/new-sales-invoice'});
    await wait('window.cur_frm?.doc?.doctype === "Sales Invoice" && window.retail?.transaction_items && !!cur_frm.fields_dict.items?.grid?.__retail_scroll_options && !!cur_frm.__retail_item_refresh_batching');
    const results=[];
    await evaluate(`(async()=>{
        const customers=await frappe.db.get_list('Customer',{fields:['name'],limit:1});
        await cur_frm.set_value('customer',customers[0].name);
        await frappe.after_ajax();
        await new Promise(r=>setTimeout(r,1500));
    })()`);
    for (const mode of ['name','barcode','row-batch']) {
        const result=await evaluate(`(async()=>{
            performance.clearResourceTimings();
            const start=performance.now();
            const count=${mode === 'row-batch' ? 3 : 1};
            for(let i=0;i<count;i++){
                const row=cur_frm.doc.items.find(r=>!r.item_code)||cur_frm.add_child('items');
                await frappe.model.set_value(row.doctype,row.name,${JSON.stringify(mode === 'barcode' ? 'custom_barcode_scan' : 'item_code')},${JSON.stringify(mode === 'barcode' ? 'AJB123' : 'I-54')});
            }
            await frappe.after_ajax();
            const filled_ms=Math.round(performance.now()-start);
            await new Promise(r=>setTimeout(r,1200));
            await retail.transaction_items.flushVatTaxRows(cur_frm);
            await retail.transaction_items.refreshVatDisplays(cur_frm);
            return {filled_ms,rows:cur_frm.doc.items.map(r=>({item:r.item_code,uom:r.uom,factor:r.conversion_factor,qty:r.qty,rate:r.rate,amount:r.amount,vat:r.custom_vat_amount,inclusive:r.custom_amount_including_vat})),requests:performance.getEntriesByType('resource').filter(r=>r.name.includes('/api/')).map(r=>({url:r.name.replace(location.origin,''),ms:Math.round(r.duration)}))};
        })()`);
        results.push({mode,...result});console.log(JSON.stringify(results[results.length-1]));
    }
    // Exercise the actual Multiple Items quantity dialog and native selector path.
    await evaluate(`window.multiCheck=Object.create(frappe.ui.form.LinkSelector.prototype);
        Object.assign(multiCheck,{target:cur_frm.fields_dict.items.grid,fieldname:'item_code',qty_fieldname:'qty'});
        window.multiDone=false;multiCheck.set_in_grid('I-54').then(()=>window.multiDone=true);true`);
    await wait('!!window.cur_dialog?.fields_dict?.qty');
    await evaluate(`(async()=>{const dialog=window.cur_dialog;await dialog.set_value('qty',1);dialog.get_primary_btn().click();})()`);
    await wait('window.multiDone');
    fs.writeFileSync(process.env.RETAIL_PROFILE_OUTPUT || '/tmp/sales-item-latency.json',JSON.stringify({results,errors},null,2));
    assert.deepEqual(errors,[]);
    assert.equal(results.at(-1).rows.length,5);
    for(const row of results.at(-1).rows){
        assert.equal(row.item,'I-54');
        assert.equal(row.qty,1);
        assert.equal(row.factor,row.uom==='Box-10'?10:1);
        assert.ok(row.rate>0);
        assert.ok(Math.abs(row.amount-row.qty*row.rate)<0.01);
        assert.ok(Math.abs(row.inclusive-row.amount-row.vat)<0.02);
    }
})().catch(error => {console.error(error); process.exitCode=1;}).finally(async ()=>{
    socket?.close();
    try { process.kill(-chrome.pid, 'SIGTERM'); } catch (error) { if (error.code !== 'ESRCH') throw error; }
    if (chrome.exitCode === null) await Promise.race([new Promise(resolve=>chrome.once('exit',resolve)),pause(2000)]);
    fs.rmSync(profile,{recursive:true,force:true,maxRetries:20,retryDelay:100});
});
