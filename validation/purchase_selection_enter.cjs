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



    for (const dt of (process.env.RETAIL_ENTER_DOCTYPE ? [process.env.RETAIL_ENTER_DOCTYPE] : ['Purchase Invoice', 'Purchase Receipt'])) for (const surface of (process.env.RETAIL_ENTER_SURFACE ? [process.env.RETAIL_ENTER_SURFACE] : ['inline', 'quick'])) {
        await evaluate(`(async()=>{if(window.cur_frm)cur_frm.doc.__unsaved=0;await frappe.new_doc(${JSON.stringify(dt)});return true})()`);
        await wait(`cur_frm?.doc?.doctype===${JSON.stringify(dt)} && cur_frm.is_new()`);
        await evaluate(`(async()=>{
            const s=await frappe.db.get_list('Supplier',{fields:['name'],limit:1});
            const w=await frappe.db.get_list('Warehouse',{fields:['name'],filters:{company:cur_frm.doc.company,is_group:0},limit:1});
            await cur_frm.set_value({supplier:s[0].name,set_warehouse:w[0].name});
            await frappe.after_ajax();
            await new Promise(resolve=>setTimeout(resolve,1500));
            await retail.transaction_items.flushVatTaxRows(cur_frm);
            return true;
        })()`);
        if(surface==='inline') {
            await evaluate(`window.testRow=cur_frm.doc.items.find(r=>!r.item_code)||cur_frm.add_child('items');cur_frm.refresh_field('items');cur_frm.fields_dict.items.grid.grid_rows_by_docname[testRow.name].activate();true`);
            await wait('cur_frm.fields_dict.items.grid.grid_rows_by_docname[testRow.name].on_grid_fields_dict?.item_code?.$input?.length===1');
            await evaluate(`window.testControl=cur_frm.fields_dict.items.grid.grid_rows_by_docname[testRow.name].on_grid_fields_dict.item_code;testControl.$input.focus().val('Apple Juice - Box x10').trigger('input');true`);
        } else {
            await wait('Array.from(document.querySelectorAll(".custom-actions button")).some(b=>b.textContent.trim()==="Quick Entry" && b.getClientRects().length)');
            await evaluate('Array.from(document.querySelectorAll(".custom-actions button")).find(b=>b.textContent.trim()==="Quick Entry" && b.getClientRects().length).click();true');
            await wait('cur_frm.__quick_receipt?.dialog.$wrapper.is(":visible")');
            await pause(1000);
            await evaluate('(async()=>{await cur_frm.__quick_receipt.queue;await cur_frm.__quick_receipt.settle();return true})()');
            await evaluate(`frappe.msgprint({title:'Local dialog validation',message:'Checking nested dialog stacking.'});true`);
            await wait('frappe.msg_dialog?.$wrapper.is(":visible")');
            await pause(350);
            assert.equal(await evaluate('document.body.classList.contains("retail-modal-open")'),true);
            await evaluate('frappe.msg_dialog.hide();true');await pause(400);
            assert.equal(await evaluate('cur_frm.__quick_receipt.dialog.$wrapper.is(":visible") && document.body.classList.contains("retail-modal-open")'),true);
            await evaluate(`window.testControl=cur_frm.__quick_receipt.dialog.get_field('item');testControl.$input.focus().val('Apple Juice - Box x10').trigger('input');true`);
        }
        await wait('testControl.awesomplete._list.some(r=>r.packing?.barcode==="AJB123")');
        console.log(JSON.stringify({doctype:dt,surface,binder:await evaluate("!!testControl.__retail_select_packing"),opened:await evaluate('testControl.awesomplete.opened')}));
        // Real Enter key, without manually preselecting an autocomplete result.
        await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
        await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
        await pause(2500);
        const row=await evaluate(`(()=>{const r=cur_frm.doc.items.find(r=>r.item_code==='I-54');return r?{item_code:r.item_code,item_name:r.item_name,uom:r.uom,factor:r.conversion_factor,rate:r.rate,barcode:r.custom_item_barcode}:null})()`);
        console.log(JSON.stringify({doctype:dt,surface,row,errors}));
        assert.ok(row?.item_name, 'Enter must fill Item Name');
        assert.equal(row.uom,'Box-10'); assert.equal(row.factor,10); assert.equal(row.rate,285.71);
        if (surface === 'inline') {
            const visible=await evaluate(`(()=>{const r=cur_frm.doc.items.find(r=>r.item_code==='I-54');const g=cur_frm.fields_dict.items.grid.grid_rows_by_docname[r.name];const shown=name=>{const f=g.on_grid_fields_dict[name];return f?.$input?.is(':visible')?f.$input.val():g.columns[name]?.find('.static-area').text().trim()};return {item_name:shown('item_name'),uom:shown('uom'),rows:cur_frm.doc.items.filter(r=>r.item_code).length}})()`);
            console.log(JSON.stringify({doctype:dt,surface,visible_without_add_row:visible}));
            assert.ok(visible.item_name?.includes('Apple Juice'));
            assert.equal(visible.uom,'Box-10');
            assert.equal(visible.rows,1);
        }

        if (surface === 'inline') {
            await evaluate(`window.testRow=cur_frm.doc.items.find(r=>r.item_code==='I-54');testRow.item_name='';testRow.uom='';cur_frm.refresh_field('items');cur_frm.fields_dict.items.grid.grid_rows_by_docname[testRow.name].activate();true`);
            await evaluate(`window.testControl=cur_frm.fields_dict.items.grid.grid_rows_by_docname[testRow.name].on_grid_fields_dict.item_code;testControl.$input.focus();testControl.awesomplete.close();true`);
            await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
            await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
            await wait('!!testRow.item_name && !!testRow.uom');
            console.log(JSON.stringify({doctype:dt,surface,incomplete_row_enter_recovery:true}));
        }
        await evaluate('cur_frm.__quick_receipt?.dialog.hide();cur_frm.doc.__unsaved=0;true');
    }
    assert.deepEqual(errors,[]);
})().catch(error => {console.error(error); process.exitCode=1;}).finally(async ()=>{
    socket?.close();
    try { process.kill(-chrome.pid, 'SIGTERM'); } catch (error) { if (error.code !== 'ESRCH') throw error; }
    if (chrome.exitCode === null) await Promise.race([new Promise(resolve=>chrome.once('exit',resolve)),pause(2000)]);
    fs.rmSync(profile,{recursive:true,force:true,maxRetries:20,retryDelay:100});
});
