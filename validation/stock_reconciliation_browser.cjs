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
    await call('Page.navigate',{url:base+'/app/stock-reconciliation/new-stock-reconciliation-check'});
    await wait('window.cur_frm?.doctype === "Stock Reconciliation" && cur_frm.doc.set_warehouse && cur_frm.fields_dict.items.grid.__retail_scroll_options');
    await evaluate('new Promise(resolve=>frappe.after_ajax(()=>setTimeout(resolve,400)))');
    const warehouse=await evaluate('cur_frm.doc.set_warehouse');
    const data=await evaluate(`(async()=>{
      const frm=cur_frm;
      const {message}=await frappe.call({method:'erpnext.stock.doctype.stock_reconciliation.stock_reconciliation.get_items',args:{warehouse:frm.doc.set_warehouse,company:frm.doc.company,posting_date:frm.doc.posting_date,posting_time:frm.doc.posting_time}});
      frm.clear_table('items');
      for(const row of message.slice(0,5)) Object.assign(frm.add_child('items'),row);
      frm.refresh_field('items');
      return message.length;
    })()`);
    assert.ok(data>0);
    await pause(1500);
    const result=await evaluate(`(async()=>{
      const frm=cur_frm;
      const rows=frm.doc.items;
      const {message}=await frappe.call({method:'retail.transaction_barcodes.get_barcodes',args:{rows:rows.map(r=>({name:r.name,item_code:r.item_code}))}});
      return {warehouse:frm.doc.set_warehouse,expected:message,rows:rows.map(r=>({name:r.name,code:r.item_code,barcode:r.custom_item_barcode,qty:r.qty,rate:r.valuation_rate})),columns:frm.fields_dict.items.grid.visible_columns.map(([df])=>df.fieldname)};
    })()`);
    for(const row of result.rows) assert.equal(row.barcode,result.expected[row.name]);
    assert.ok(result.rows.some(row=>row.barcode));
    for(const name of ['batch_no','serial_no','use_serial_batch_fields','add_serial_batch_bundle','serial_and_batch_bundle'])assert.ok(result.columns.includes(name),name);
    assert.equal(result.columns[result.columns.indexOf('item_name')+1],'custom_item_barcode');
    await evaluate(`(async()=>{
      const row=cur_frm.doc.items[0];
      await cur_frm.script_manager.trigger('add_serial_batch_bundle',row.doctype,row.name);
    })()`);
    await wait('window.cur_dialog?.fields_dict?.entries');
    const picker=await evaluate('({title:cur_dialog.title,warehouse:cur_dialog.get_value("warehouse")})');
    await evaluate('cur_dialog.hide()');
    result.picker=picker;
    assert.equal(picker.warehouse,warehouse);
    assert.equal(errors.length,0,JSON.stringify(errors));
    console.log(JSON.stringify({result,browserErrors:errors,businessDocumentsSaved:false}));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
    socket?.close();try{process.kill(-chrome.pid,'SIGTERM');}catch{}
    await pause(600);try{fs.rmSync(profile,{recursive:true,force:true,maxRetries:10,retryDelay:100});}catch{}
});
