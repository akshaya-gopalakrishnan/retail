// Real Chromium validation; credentials come only from the temporary Python harness.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const WebSocket = require('../../frappe/node_modules/ws');
const assert = require('node:assert/strict');
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'product-conversion-chrome-'));
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
        const result = await call('Runtime.evaluate', {expression, awaitPromise: true, returnByValue: true}).catch(error=>{throw new Error(expression + ': ' + error.message)});
        if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
        return result.result.value;
    };
    const wait = async expression => {
        for (let i = 0; i < 100; i++) { if (await evaluate('Boolean(' + expression + ')')) return; await pause(300); }
        throw new Error('Timeout: ' + expression + '; ' + JSON.stringify(errors));
    };



    const base=process.env.RETAIL_URL;
    await call('Network.enable');await call('Runtime.enable');await call('Page.enable');
    await call('Network.setCookie',{name:'sid',value:process.env.RETAIL_SID,url:base});
    await call('Emulation.setDeviceMetricsOverride',{width:1600,height:1200,deviceScaleFactor:1,mobile:false});
    await call('Page.navigate',{url:base+'/app/product-conversion/new-product-conversion-layout'});
    await wait('window.cur_frm?.doc?.doctype === "Product Conversion" && cur_frm.doc.source_warehouse && cur_frm.fields_dict.items.grid.__retail_scroll_options');
    await evaluate('new Promise(resolve=>frappe.after_ajax(()=>setTimeout(resolve,400)))');
    const bom=await evaluate(`(async()=>{
        const rows=await frappe.db.get_list('BOM',{fields:['name'],limit:1});
        return rows[0]?.name;
    })()`);
    assert.ok(bom,'An existing BOM is needed for the read-only check');
    await call('Page.navigate',{url:base+'/app/bom/'+encodeURIComponent(bom)});
    await wait('window.cur_frm?.doctype === "BOM" && cur_frm.doc.name === '+JSON.stringify(bom)+' && cur_frm.fields_dict.items.grid.__retail_scroll_options');
    await evaluate('new Promise(resolve=>frappe.after_ajax(()=>setTimeout(resolve,400)))');
    const result=await evaluate(`(async()=>{
        const frm=cur_frm;
        const codes=[frm.doc.item,...frm.doc.items.map(row=>row.item_code)];
        const {message}=await frappe.call({method:'retail.bom_item_identity.get_item_identities',args:{items:codes}});
        return {name:frm.doc.name,dirty:!!frm.is_dirty(),headerBarcode:frm.doc.custom_item_barcode,
            item:frm.doc.item,identities:message,
            fields:frm.meta.fields.map(field=>field.fieldname),
            columns:frm.fields_dict.items.grid.visible_columns.map(([field])=>field.fieldname),
            rows:frm.doc.items.map(row=>({item:row.item_code,barcode:row.custom_item_barcode})),
            childFields:frappe.get_meta('BOM Item').fields.map(field=>field.fieldname)};
    })()`);
    const main=result.identities.find(item=>item.name===result.item);
    assert.equal(result.headerBarcode,main.custom_barcode||'');
    assert.equal(result.fields[result.fields.indexOf('item_name')+1],'custom_item_barcode');
    assert.equal(result.childFields[result.childFields.indexOf('item_name')+1],'custom_item_barcode');
    const position=result.columns.indexOf('item_name');
    assert.ok(position>=0);assert.equal(result.columns[position+1],'custom_item_barcode');
    for(const row of result.rows)assert.equal(row.barcode,result.identities.find(item=>item.name===row.item).custom_barcode||'');
    assert.equal(result.dirty,false);assert.equal(errors.length,0,JSON.stringify(errors));
    console.log(JSON.stringify({result,browserErrors:errors,businessDocumentsSaved:false}));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
    socket?.close();try{process.kill(-chrome.pid,'SIGTERM');}catch{}
    await pause(600);try{fs.rmSync(profile,{recursive:true,force:true,maxRetries:10,retryDelay:100});}catch{}
});
