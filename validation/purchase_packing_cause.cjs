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
    for (const dt of ['Purchase Receipt', 'Purchase Invoice']) for (const mode of (process.env.RETAIL_CAUSE_MODES || 'native-stock,legacy-packing,packing-selection').split(',')) {
        await call('Network.emulateNetworkConditions', {offline:false,latency:0,downloadThroughput:-1,uploadThroughput:-1});
        await evaluate(`(async()=>{if(window.cur_frm)cur_frm.doc.__unsaved=0;await frappe.new_doc(${JSON.stringify(dt)});return true;})()`);
        await wait(`cur_frm?.doc?.doctype === ${JSON.stringify(dt)} && cur_frm.is_new()`);
        assert.equal(await evaluate('typeof retail.purchase_packing_search.installScanner === "function" && !retail.purchase_packing_search.installScanner.toString().includes("trigger_from_barcode_scanner")'),true,'Load the final Retail scanner hook; clear site script cache if stale');
        await evaluate(`(async()=>{
            const suppliers=await frappe.db.get_list('Supplier',{fields:['name'],limit:1});
            const warehouses=await frappe.db.get_list('Warehouse',{fields:['name'],filters:{company:cur_frm.doc.company,is_group:0},limit:1});
            await cur_frm.set_value({supplier:suppliers[0].name,set_warehouse:warehouses[0].name});
            await frappe.after_ajax();
            await new Promise(resolve=>setTimeout(resolve,1500));
            await retail.transaction_items.flushVatTaxRows(cur_frm);
            window.testRow=cur_frm.doc.items.find(r=>!r.item_code)||cur_frm.add_child('items');
            cur_frm.refresh_field('items');
            if(!${JSON.stringify(mode)}.endsWith('scan'))cur_frm.fields_dict.items.grid.grid_rows_by_docname[testRow.name].toggle_view(true);
            return true;
        })()`);
        if(!mode.endsWith('scan')) {
            await wait('cur_frm.fields_dict.items.grid.grid_rows_by_docname[testRow.name].grid_form?.fields_dict.item_code?.$input?.length === 1');
            await evaluate('window.testControl=cur_frm.fields_dict.items.grid.grid_rows_by_docname[testRow.name].grid_form.fields_dict.item_code;testControl.$input.focus().val("AJB123").trigger("input");true');
            await wait('testControl.__retail_packing_search && testControl.awesomplete._list.some(r=>r.packing?.barcode==="AJB123")');
        }
        await call('Network.emulateNetworkConditions', {offline:false,latency:150,downloadThroughput:-1,uploadThroughput:-1});
        const value=await evaluate(`(async()=>{
            performance.clearResourceTimings();const start=performance.now();
            if(${JSON.stringify(mode)}.endsWith('scan')) {
                const scanner=cur_frm.cscript.barcode_scanner, scan=scanner.process_scan;
                retail.purchase_packing_search.installScanner(cur_frm);
                const savedUpdate=scanner.update_table, savedBarcode=scanner.set_barcode;
                if(${JSON.stringify(mode)}==='legacy-scan') {
                    scanner.__retail_packing_input=true;
                    scanner.update_table=erpnext.utils.BarcodeScanner.prototype.update_table;
                    scanner.set_barcode=erpnext.utils.BarcodeScanner.prototype.set_barcode;
                }
                const update=scanner.update_table;
                scanner.update_table=function(data,...args){window.scanDiagnostic={data,installed:this.__retail_packing_input,form:cur_frm.doc.doctype};return update.call(this,data,...args);};
                let scanned;
                scanner.process_scan=function(...args){
                    const hasInput=Boolean(this.scan_barcode_field.value);
                    const promise=scan.apply(this,args);
                    if(hasInput) scanned=promise;
                    return promise;
                };
                try {
                    await cur_frm.set_value('scan_barcode','AJB123');
                    await Promise.race([scanned,new Promise((_,reject)=>setTimeout(()=>reject(new Error('Scanner did not complete')),15000))]);
                } finally {scanner.process_scan=scan;scanner.update_table=savedUpdate;scanner.set_barcode=savedBarcode;}
            } else if(${JSON.stringify(mode)}==='packing-selection') {
                testControl.awesomplete.goto(testControl.awesomplete._list.findIndex(r=>r.packing?.barcode==='AJB123'));
                testControl.awesomplete.select();
                await new Promise(resolve=>setTimeout(resolve,0));
                while(testControl.__retail_packing_busy)await new Promise(resolve=>setTimeout(resolve,16));
            } else {
                await testControl.set_value('I-54');
                if(${JSON.stringify(mode)}==='legacy-packing') {
                    while(testRow.__retail_vat_syncing||testRow.__retail_sell_price_syncing)await new Promise(resolve=>setTimeout(resolve,16));
                    await frappe.model.set_value(testRow.doctype,testRow.name,'uom','Box-10');
                    testRow.barcode='AJB123';testRow.custom_item_barcode='AJB123';cur_frm.dirty();cur_frm.refresh_field('items');
                }
            }
            const add_ms=Math.round(performance.now()-start);
            await frappe.after_ajax();await new Promise(resolve=>setTimeout(resolve,1200));await frappe.after_ajax();
            await retail.transaction_items.flushVatTaxRows(cur_frm);
            while(testRow.__retail_vat_syncing||testRow.__retail_sell_price_syncing)await new Promise(resolve=>setTimeout(resolve,16));
            return {add_ms,settled_ms:Math.round(performance.now()-start),diagnostic:window.scanDiagnostic,row:{item:testRow.item_code,uom:testRow.uom,factor:testRow.conversion_factor,qty:testRow.qty,rate:testRow.rate,amount:testRow.amount,net_amount:testRow.net_amount,barcode:testRow.barcode},requests:performance.getEntriesByType('resource').filter(r=>r.name.includes('/api/')).map(r=>({url:r.name.replace(location.origin,''),start:Math.round(r.startTime-start),ms:Math.round(r.duration)}))};
        })()`);
        assert.equal(value.row.item,'I-54');
        assert.equal(value.row.uom,mode==='native-stock'?'Nos':'Box-10');
        assert.equal(value.row.factor,mode==='native-stock'?1:10);
        assert.equal(value.row.rate,mode==='native-stock'?28.57:285.71);
        assert.equal(value.row.amount,value.row.rate*value.row.qty);
        results.push({doctype:dt,mode,...value});console.log(JSON.stringify(results[results.length-1]));
    }
    fs.writeFileSync(process.env.RETAIL_CAUSE_OUTPUT || '/tmp/purchase-packing-cause.json',JSON.stringify({results,errors},null,2));
    assert.deepEqual(errors,[]);
})().catch(error => {console.error(error); process.exitCode=1;}).finally(async ()=>{
    socket?.close();
    try { process.kill(-chrome.pid, 'SIGTERM'); } catch (error) { if (error.code !== 'ESRCH') throw error; }
    if (chrome.exitCode === null) await Promise.race([new Promise(resolve=>chrome.once('exit',resolve)),pause(2000)]);
    fs.rmSync(profile,{recursive:true,force:true,maxRetries:20,retryDelay:100});
});
