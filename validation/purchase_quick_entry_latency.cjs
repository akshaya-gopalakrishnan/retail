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
    await call('Page.navigate', {url: base + '/app/purchase-receipt/new-purchase-receipt'});
    await wait('window.cur_frm?.doc?.doctype === "Purchase Receipt" && window.retail?.purchase_packing_search');

    const results = [];
    for (const latency of [0, 150]) for (const dt of ['Purchase Receipt', 'Purchase Invoice']) {
        await call('Network.emulateNetworkConditions', {offline:false,latency:0,downloadThroughput:-1,uploadThroughput:-1});
        await evaluate(`if(window.cur_frm)cur_frm.doc.__unsaved=0;frappe.new_doc(${JSON.stringify(dt)});true`);
        await wait(`window.cur_frm?.doc?.doctype === ${JSON.stringify(dt)} && cur_frm.is_new()`);
        await wait('Array.from(document.querySelectorAll(".custom-actions button")).some(b=>b.textContent.trim()==="Quick Entry" && b.getClientRects().length)');
        await evaluate('Array.from(document.querySelectorAll(".custom-actions button")).find(b=>b.textContent.trim()==="Quick Entry" && b.getClientRects().length).click()');
        await wait('cur_frm.__quick_receipt?.dialog.$wrapper.is(":visible")');
        await evaluate(`(async()=>{
            window.testEntry=cur_frm.__quick_receipt;
            const suppliers=await frappe.db.get_list('Supplier',{fields:['name'],limit:1});
            const warehouses=await frappe.db.get_list('Warehouse',{fields:['name'],filters:{company:cur_frm.doc.company,is_group:0},limit:1});
            await testEntry.dialog.set_value('supplier',suppliers[0].name);
            await testEntry.dialog.set_value('set_warehouse',warehouses[0].name);
            await testEntry.queue;await testEntry.settle();
            window.profilePhases=[];
            for(const method of ['add','prepareItem','setRowValue','render','rowReady']){
                const original=testEntry[method];
                testEntry[method]=function(...args){
                    const start=performance.now();
                    const done=()=>profilePhases.push({method,field:method==='setRowValue'?args[1]:undefined,ms:Math.round(performance.now()-start)});
                    const result=original.apply(this,args);
                    if(result?.then)return result.then(value=>{done();return value;},error=>{done();throw error;});
                    done();return result;
                };
            }
            return true;
        })()`);
        await call('Network.emulateNetworkConditions', {offline:false,latency,downloadThroughput:-1,uploadThroughput:-1});
        for(const [label,scan] of [['first',{item_code:'I-54',uom:'Box-10',barcode:'AJB123'}],['repeat',{item_code:'I-54',uom:'Box-10',barcode:'AJB123'}]]){
            const value=await evaluate(`(async()=>{
                performance.clearResourceTimings();profilePhases.length=0;
                const start=performance.now();
                await testEntry.enqueue(()=>testEntry.add(${JSON.stringify(scan)}));
                const elapsed=performance.now()-start;
                const rows=cur_frm.doc.items.map(r=>({item:r.item_code,uom:r.uom,factor:r.conversion_factor,qty:r.qty,rate:r.rate,amount:r.amount,tax_rate:r.tax_rate,barcode:r.barcode,cur_sell:r.custom_cur_sell_rate}));
                const requests=performance.getEntriesByType('resource').filter(r=>r.name.includes('/api/')).map(r=>({url:r.name.replace(location.origin,''),ms:Math.round(r.duration)}));
                await testEntry.settle();
                const settledRows=cur_frm.doc.items.map(r=>({item:r.item_code,uom:r.uom,factor:r.conversion_factor,qty:r.qty,rate:r.rate,amount:r.amount,tax_rate:r.tax_rate,barcode:r.barcode,cur_sell:r.custom_cur_sell_rate,net_amount:r.net_amount}));
                return {ms:Math.round(elapsed),settled_ms:Math.round(performance.now()-start),phases:profilePhases,requests,rows,settledRows};
            })()`);
            results.push({doctype:dt,latency,label,...value});
            console.log(JSON.stringify(results[results.length-1]));
        }
        await evaluate('testEntry.dialog.hide();true');
    }
    fs.writeFileSync(process.env.RETAIL_PROFILE_OUTPUT || '/tmp/purchase-quick-entry-latency.json',JSON.stringify({results,errors},null,2));
    assert.deepEqual(errors,[]);
})().catch(error => {console.error(error); process.exitCode=1;}).finally(async ()=>{
    socket?.close();
    try { process.kill(-chrome.pid, 'SIGTERM'); } catch (error) { if (error.code !== 'ESRCH') throw error; }
    if (chrome.exitCode === null) await Promise.race([new Promise(resolve=>chrome.once('exit',resolve)),pause(2000)]);
    fs.rmSync(profile,{recursive:true,force:true,maxRetries:20,retryDelay:100});
});
