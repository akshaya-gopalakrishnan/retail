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




    const mode=process.env.RETAIL_PROFILE_MODE||'full';
    const dt=process.env.RETAIL_PROFILE_DOCTYPE||'Purchase Invoice';
    await evaluate(`(async()=>{if(cur_frm)cur_frm.doc.__unsaved=0;await frappe.new_doc(${JSON.stringify(dt)});return true})()`);
    await wait(`cur_frm?.doc?.doctype===${JSON.stringify(dt)} && cur_frm.is_new()`);
    await evaluate(`(async()=>{
        const s=await frappe.db.get_list('Supplier',{fields:['name'],limit:1});
        const w=await frappe.db.get_list('Warehouse',{fields:['name'],filters:{company:cur_frm.doc.company,is_group:0},limit:1});
        await cur_frm.set_value({supplier:s[0].name,set_warehouse:w[0].name});
        await frappe.after_ajax();await new Promise(r=>setTimeout(r,1500));
        await retail.transaction_items.flushVatTaxRows(cur_frm);
        window.profileItems=await frappe.db.get_list('Item',{fields:['name'],filters:{disabled:0,is_purchase_item:1},limit:20});
        return true;
    })()`);
    if(mode==='quick'){
        await wait('Array.from(document.querySelectorAll(".custom-actions button")).some(b=>b.textContent.trim()==="Quick Entry"&&b.getClientRects().length)');
        await evaluate('Array.from(document.querySelectorAll(".custom-actions button")).find(b=>b.textContent.trim()==="Quick Entry"&&b.getClientRects().length).click();true');
        await wait('cur_frm.__quick_receipt?.dialog.$wrapper.is(":visible")');
        await pause(1200);
        await evaluate('(async()=>{await cur_frm.__quick_receipt.queue;await cur_frm.__quick_receipt.settle();return true})()');
    }
    await evaluate(`(()=>{
        window.profileStats={};window.profileLong=[];
        new PerformanceObserver(list=>{for(const e of list.getEntries())profileLong.push(Math.round(e.duration))}).observe({entryTypes:['longtask']});
        function wrap(object,key,label){const fn=object?.[key];if(typeof fn!=='function')return;object[key]=function(...args){const t=performance.now();try{return fn.apply(this,args)}finally{const s=profileStats[label]||={calls:0,sync_ms:0};s.calls++;s.sync_ms+=performance.now()-t}}}
        const f=cur_frm,g=f.fields_dict.items.grid;
        wrap(g,'refresh','grid_refresh');wrap(g,'update_docfield_property','grid_property');
        wrap(f.fields_dict.items,'refresh','items_refresh');
        wrap(f.cscript,'calculate_taxes_and_totals','totals');
        const row=g.grid_rows?.[0];if(row){wrap(Object.getPrototypeOf(row),'refresh','row_refresh');wrap(Object.getPrototypeOf(row),'refresh_dependency','row_dependency');}
        if(f.__quick_receipt){wrap(f.__quick_receipt,'render','quick_render');wrap(f.__quick_receipt,'renderRows','quick_render_rows');}
        return true;
    })()`);
    await call('Network.emulateNetworkConditions',{offline:false,latency:Number(process.env.RETAIL_PROFILE_LATENCY||0),downloadThroughput:-1,uploadThroughput:-1});
    if(process.env.RETAIL_PROFILE_CSS_MODAL==='1') await evaluate(`(()=>{let count=0;const visit=rules=>{for(const rule of rules){if(rule.selectorText?.includes('body:has(.modal.show)')){rule.selectorText=rule.selectorText.replaceAll('body:has(.modal.show)','body.modal-open');count++}if(rule.cssRules)visit(rule.cssRules)}};for(const sheet of document.styleSheets){try{visit(sheet.cssRules)}catch{}}return count})()`);
    const cssDiagnostic=await evaluate(`(()=>{const found=[];const visit=rules=>{for(const rule of rules){if(rule.selectorText?.includes('body:has(.modal.show)'))found.push(rule.selectorText);if(rule.cssRules)visit(rule.cssRules)}};for(const sheet of document.styleSheets){try{visit(sheet.cssRules)}catch{}}return {globalModalHasRules:found.length}})()`);
    if(process.env.RETAIL_PROFILE_VERIFY_FIX==='1') assert.equal(cssDiagnostic.globalModalHasRules,0,'Stale global modal selector still loaded');
    await call('Performance.enable');
    const samples=[];
    for(let i=0;i<Number(process.env.RETAIL_PROFILE_ROWS||15);i++){
        const before=Object.fromEntries((await call('Performance.getMetrics')).metrics.map(m=>[m.name,m.value]));
        const sample=await evaluate(`(async()=>{
            profileStats={};profileLong.length=0;performance.clearResourceTimings();
            const f=cur_frm,start=performance.now(),scan={item_code:profileItems[${i}].name};
            let filled;
            if(${JSON.stringify(mode)}==='quick'){
                const e=f.__quick_receipt;await e.enqueue(()=>e.add(scan));
                if(e.failed)throw new Error('Quick Entry add failed');
            }else{
                const row=f.doc.items.find(r=>!r.item_code)||f.add_child('items');
                f.refresh_field('items');
                if(${JSON.stringify(mode)}==='native') {
                    await frappe.model.set_value(row.doctype,row.name,'item_code',scan.item_code);
                } else {
                    filled=await retail.purchaseLine.fill(f,scan,row);
                    if(!filled?.row)throw new Error('Line did not fill');
                }
                f.refresh_field('items');
            }
            const added=performance.now()-start;
            await frappe.after_ajax();
            if(${JSON.stringify(mode)}==='quick')await f.__quick_receipt.settle();
            else await retail.transaction_items.flushVatTaxRows(f);
            await frappe.after_ajax();await new Promise(r=>setTimeout(r,250));
            const last=f.doc.items.find(r=>r.item_code===scan.item_code);
            return {row:${i+1},add_ms:Math.round(added),settled_ms:Math.round(performance.now()-start),stats:profileStats,long_tasks:profileLong,values:{item:last.item_code,name:last.item_name,uom:last.uom,qty:last.qty,rate:last.rate,amount:last.amount},requests:performance.getEntriesByType('resource').filter(r=>r.name.includes('/api/')).map(r=>({method:r.name.split('/api/method/')[1]?.split('?')[0],ms:Math.round(r.duration),bytes:r.encodedBodySize}))};
        })()`);
        const after=Object.fromEntries((await call('Performance.getMetrics')).metrics.map(m=>[m.name,m.value]));
        sample.browser_ms=Object.fromEntries(['LayoutDuration','RecalcStyleDuration','ScriptDuration','TaskDuration'].map(key=>[key,Math.round((after[key]-before[key])*1000)]));
        samples.push(sample);console.log(JSON.stringify({doctype:dt,mode,...sample}));
    }
    if(mode==='quick') {
        await evaluate('cur_frm.__quick_receipt.dialog.hide();true');
        await pause(500);
        const visible=await evaluate('({rows:cur_frm.fields_dict.items.grid.grid_rows.length,items:cur_frm.doc.items.filter(r=>r.item_code).length})');
        assert.equal(visible.items,samples.length);
        assert.equal(visible.rows,samples.length);
        console.log(JSON.stringify({quick_close_full_grid:visible}));
    }
    fs.writeFileSync(process.env.RETAIL_PROFILE_OUTPUT||'/tmp/purchase-row-growth-'+mode+'.json',JSON.stringify({doctype:dt,mode,cssDiagnostic,samples,errors},null,2));
    assert.deepEqual(errors,[]);
})().catch(error => {console.error(error); process.exitCode=1;}).finally(async ()=>{
    socket?.close();
    try { process.kill(-chrome.pid, 'SIGTERM'); } catch (error) { if (error.code !== 'ESRCH') throw error; }
    if (chrome.exitCode === null) await Promise.race([new Promise(resolve=>chrome.once('exit',resolve)),pause(2000)]);
    fs.rmSync(profile,{recursive:true,force:true,maxRetries:20,retryDelay:100});
});
