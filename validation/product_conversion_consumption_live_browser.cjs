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
    await call('Page.navigate',{url:base+'/app/product-conversion/PC-2'});
    await wait('window.cur_frm?.doc?.doctype === "Product Conversion" && cur_frm.doc.source_warehouse && cur_frm.fields_dict.items.grid.__retail_scroll_options');
    await evaluate('new Promise(resolve=>frappe.after_ajax(()=>setTimeout(resolve,400)))');
    await evaluate(`cur_frm.custom_buttons[__('Consumption Details')].trigger('click')`);
    await wait('window.cur_dialog?.fields_dict.lines?.grid');
    const expected=await evaluate(`(async()=>{
        const grid=cur_dialog.fields_dict.lines.grid;
        grid.grid_rows[0].toggle_editable_row(true);
        grid.grid_rows[0].toggle_editable_row(false);
        grid.grid_rows.forEach(row=>row.select(true));
        grid.delete_rows();
        for(let i=0;i<40 && grid.get_data().length;i++)await new Promise(resolve=>setTimeout(resolve,25));
        grid.add_new_row();
        const gridRow=grid.grid_rows[0];
        const material=gridRow.doc;
        const code=cur_frm.doc.materials[1].item_code;
        gridRow.toggle_editable_row(true);
        const {message}=await frappe.call({method:'retail.product_conversion.get_stock_details',args:{item_code:code,warehouse:material.warehouse,company:cur_frm.doc.company}});
        material.batch_no='STALE-BATCH';material.serial_no='STALE-SERIAL';
        await gridRow.columns.item_code.field.set_value(code);
        return {code,...message};
    })()`);
    await wait('cur_dialog.fields_dict.lines.grid.get_data()[0].current_stock!=null');
    const result=await evaluate(`(()=>{
        const grid=cur_dialog.fields_dict.lines.grid;
        const material=grid.get_data()[0];
        return {code:material.item_code,stock:material.current_stock,cost:material.unit_cost,
            batch:material.batch_no,serial:material.serial_no,
            query:grid.docfields.find(field=>field.fieldname==='batch_no').get_query(material),
            formDirty:!!cur_frm.is_dirty(),originalCode:cur_frm.doc.materials[0].item_code};
    })()`);
    assert.equal(result.code,expected.code);assert.equal(result.stock,expected.current_stock);assert.equal(result.cost,expected.stock_cost);
    assert.equal(result.batch,null);assert.equal(result.serial,null);
    assert.equal(result.query.filters.item_code,expected.code);assert.ok(result.query.filters.warehouse);
    assert.notEqual(result.originalCode,result.code);assert.equal(result.formDirty,false);
    assert.equal(errors.length,0,JSON.stringify(errors));
    console.log(JSON.stringify({result,expected,browserErrors:errors,applyClicked:false,businessDocumentsSaved:false}));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
    socket?.close();try{process.kill(-chrome.pid,'SIGTERM');}catch{}
    await pause(600);try{fs.rmSync(profile,{recursive:true,force:true,maxRetries:10,retryDelay:100});}catch{}
});
