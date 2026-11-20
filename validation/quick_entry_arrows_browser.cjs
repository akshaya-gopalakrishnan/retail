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
    await call('Page.navigate',{url:base+'/app/product-conversion/new-product-conversion-arrows'});
    await wait('window.frappe?.ui?.form?.RetailQuickEntryForm');
    await wait('cur_frm?.doctype === "Product Conversion" && cur_frm.is_new() && cur_frm.doc.source_warehouse');
    async function arrow(from, key, to) {
      await evaluate(`(()=>{const f=cur_dialog.fields_dict[${JSON.stringify(from)}];f.awesomplete?.close();f.$input[0].focus()})()`);
      await call('Input.dispatchKeyEvent',{type:'keyDown',key,code:key,windowsVirtualKeyCode:{ArrowDown:40,ArrowUp:38,ArrowLeft:37,ArrowRight:39,Enter:13}[key]});
      await call('Input.dispatchKeyEvent',{type:'keyUp',key,code:key});
      await pause(400);

      await wait(`document.activeElement === cur_dialog.fields_dict[${JSON.stringify(to)}].$input[0]`);
    }
    for (const [trigger, first] of [['get_items_from_bom','use_multi_level_bom'],['get_items_from_main_item','main_item']]) {
      await evaluate(`cur_frm.trigger(${JSON.stringify(trigger)}); true`);
      await wait('window.cur_dialog?.__retail_navigation');
      await arrow(first,'ArrowDown',trigger==='get_items_from_bom'?'qty':'item_code');
      await evaluate('cur_dialog.set_value("qty", 4)');
      await arrow('qty','ArrowDown',trigger==='get_items_from_bom'?'labour_cost':'qty_per_unit');
      await arrow('labour_cost','ArrowDown','packing_cost');
      await arrow('packing_cost','ArrowUp','labour_cost');
      await arrow('labour_cost','ArrowRight','packing_cost');
      await arrow('packing_cost','ArrowLeft','labour_cost');
      assert.equal(await evaluate('cur_dialog.get_value("qty")'),4);
      await evaluate('cur_dialog.hide()');
      await wait('!window.cur_dialog');
    }
    await evaluate(`(()=>{
      const row=cur_frm.add_child('items',{item_code:'I-89',item_name:'Sugar 100 gm',main_item:'I-88',main_qty:0.5,qty:5,row_key:'keyboard-check'});
      cur_frm.script_manager.trigger('consumption_details',row.doctype,row.name);
    })()`);
    await wait('window.cur_dialog?.fields_dict?.lines && cur_dialog.__retail_navigation');
    await evaluate(`(()=>{const grid=cur_dialog.fields_dict.lines.grid;grid.grid_rows[0].toggle_editable_row(true);grid.grid_rows[0].on_grid_fields_dict.qty.$input[0].focus()})()`);
    await call('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});
    await call('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowRight',code:'ArrowRight'});
    await wait('document.activeElement === cur_dialog.fields_dict.lines.grid.grid_rows[0].on_grid_fields_dict.warehouse.$input[0]');
    await evaluate('cur_dialog.hide()');
    console.log(JSON.stringify({consumptionGrid:true,productConversionDialogs:['BOM','Main Item'],arrows:['up','down','left','right'],quantityPreserved:true,browserErrors:errors}));
    assert.equal(errors.length,0);
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
    socket?.close();try{process.kill(-chrome.pid,'SIGTERM');}catch{}
    await pause(600);try{fs.rmSync(profile,{recursive:true,force:true,maxRetries:10,retryDelay:100});}catch{}
});
