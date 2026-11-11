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
    for (const dt of ['Purchase Receipt', 'Purchase Invoice']) {
        await evaluate(`if(window.cur_frm)cur_frm.doc.__unsaved=0;frappe.new_doc(${JSON.stringify(dt)});true`);
        await wait(`window.cur_frm?.doc?.doctype === ${JSON.stringify(dt)} && cur_frm.is_new()`);
        await wait('Array.from(document.querySelectorAll(".custom-actions button")).some(b=>b.textContent.trim()==="Quick Entry" && b.getClientRects().length)');
        await evaluate('Array.from(document.querySelectorAll(".custom-actions button")).find(b=>b.textContent.trim()==="Quick Entry" && b.getClientRects().length).click()');
        await wait('cur_frm.__quick_receipt?.dialog.$wrapper.is(":visible")');
        await pause(700);
        await evaluate('window.testEntry=cur_frm.__quick_receipt;testEntry.dialog.get_field("item").$input.focus().val("").trigger("input");true');
        await wait('testEntry.dialog.get_field("item").awesomplete._list.some(r=>r.packing)');
        const recent=await evaluate('testEntry.dialog.get_field("item").awesomplete._list.filter(r=>r.packing).map(r=>r.packing)');
        assert.ok(recent.length>0 && recent.length<=5);
        assert.ok(recent.every(r=>!r.packing_id));
        console.log(JSON.stringify({doctype:dt,recent_items:recent.length}));
        await evaluate('testEntry.dialog.get_field("item").$input.val("a").trigger("input");true');
        await wait('testEntry.dialog.get_field("item").awesomplete._list.filter(r=>r.packing).length>5');
        const broadCount=await evaluate('(()=>{const a=testEntry.dialog.get_field("item").awesomplete;return {rows:a._list.length,visible:a.suggestions.length}})()');
        assert.equal(broadCount.rows,broadCount.visible);
        const initialPage=await evaluate('testEntry.dialog.get_field("item").awesomplete._list.filter(r=>r.packing).length');
        assert.ok(initialPage<=20);
        const hasMore=await evaluate('testEntry.dialog.get_field("item").awesomplete._list.some(r=>r.value==="load_more__retail_packing")');
        if(hasMore){
            await evaluate('(()=>{const a=testEntry.dialog.get_field("item").awesomplete;a.goto(a._list.findIndex(r=>r.value==="load_more__retail_packing"));a.select();return true})()');
            await wait('testEntry.dialog.get_field("item").awesomplete._list.filter(r=>r.packing).length>20');
        }
        console.log(JSON.stringify({doctype:dt,paged_results:{initial:initialPage,load_more:hasMore,
            loaded:await evaluate('testEntry.dialog.get_field("item").awesomplete._list.filter(r=>r.packing).length')}}));
        for (const [text,count] of [['Apple Juice',4],['Apple Juice - B',2],['Apple Juice - Box x10',1]]) {
            await evaluate(`testEntry.dialog.get_field("item").$input.val(${JSON.stringify(text)}).trigger("input");true`);
            await wait(`testEntry.dialog.get_field("item").awesomplete._list.filter(r=>r.packing).length===${count}`);
        }
        console.log(JSON.stringify({doctype:dt,incremental_filtering:true}));
        await evaluate('testEntry.dialog.get_field("item").$input.val("Apple Juice").trigger("input");true');
        await pause(1000);
        await wait('testEntry.dialog.get_field("item").awesomplete._list.some(r=>r.packing?.barcode==="AJB123")');
        fs.writeFileSync('/tmp/' + (dt === 'Purchase Receipt' ? 'pr' : 'pi') + '-packing-grid.png',Buffer.from((await call('Page.captureScreenshot',{format:'png'})).data,'base64'));
        const dimensions=await evaluate('(()=>{const list=testEntry.dialog.get_field("item").awesomplete.ul;return {width:list.getBoundingClientRect().width,scroll:list.scrollWidth,client:list.clientWidth,headings:list.querySelector(".retail-packing-heading").textContent}})()');
        assert.ok(dimensions.width>=540 && dimensions.width<=580,JSON.stringify(dimensions));
        assert.ok(dimensions.scroll<=dimensions.client+2,JSON.stringify(dimensions));
        const options=await evaluate('testEntry.dialog.get_field("item").awesomplete._list.filter(r=>!r.packing).map(r=>({value:r.value,label:r.label}))');
        assert.ok(options.some(r=>r.value==='create_new__link_option'));
        assert.ok(options.some(r=>r.value==='advanced_search__link_option'));
        assert.ok(options.some(r=>r.value==='filters__link_option'));
        console.log(JSON.stringify({doctype:dt,standard_options:options}));
        const choices=await evaluate('testEntry.dialog.get_field("item").awesomplete._list.filter(r=>r.packing).map(r=>r.packing)');
        assert.ok(choices.some(r=>r.uom==='Box-10' && r.conversion_factor===10));
        console.log(JSON.stringify({doctype:dt,quick_grid:true,choices}));
        await evaluate(`(async()=>{
            const suppliers = await frappe.db.get_list('Supplier', {fields:['name'],limit:1});
            const warehouses = await frappe.db.get_list('Warehouse', {fields:['name'],filters:{company:cur_frm.doc.company,is_group:0},limit:1});
            await testEntry.dialog.set_value('supplier',suppliers[0].name);
            await testEntry.dialog.set_value('set_warehouse',warehouses[0].name);
            await testEntry.queue;
            const a=testEntry.dialog.get_field('item').awesomplete;
            a.goto(a._list.findIndex(r=>r.packing?.barcode==='AJB123'));a.select();
            return true;
        })()`);
		await wait('testEntry.packingChoice?.barcode === "AJB123"');
		await evaluate('(async()=>{testEntry.dialog.get_field("item").$input.trigger("change");await new Promise(resolve=>frappe.after_ajax(resolve));return true;})()');
		await evaluate('testEntry.dialog.get_field("add").$input.click();true');
        await wait('cur_frm.doc.items.some(r=>r.item_code==="I-54" && r.uom==="Box-10" && r.conversion_factor===10) && testEntry.pending===0');
        console.log(JSON.stringify({doctype:dt,quick_selection:await evaluate('cur_frm.doc.items.map(r=>({item:r.item_code,uom:r.uom,factor:r.conversion_factor,qty:r.qty,barcode:r.barcode}))')}));
        await evaluate('testEntry.dialog.hide();true');
        await evaluate('window.testRow=cur_frm.add_child("items");cur_frm.refresh_field("items");cur_frm.fields_dict.items.grid.grid_rows_by_docname[testRow.name].toggle_view(true);true');
        await wait('cur_frm.fields_dict.items.grid.grid_rows_by_docname[testRow.name].grid_form?.fields_dict.item_code?.$input?.length === 1');
        await evaluate('window.testControl=cur_frm.fields_dict.items.grid.grid_rows_by_docname[testRow.name].grid_form.fields_dict.item_code; testControl.$input.focus().val("AJB123").trigger("input");true');
        await wait('testControl.__retail_packing_search && testControl.awesomplete._list.some(r=>r.packing?.barcode==="AJB123")');
        console.log(JSON.stringify({doctype:dt,full_grid:true}));
        await evaluate('testControl.awesomplete.goto(testControl.awesomplete._list.findIndex(r=>r.packing?.barcode==="AJB123"));testControl.awesomplete.select();true');
        await wait('testRow.item_code==="I-54" && testRow.uom==="Box-10" && testRow.conversion_factor===10 && !testControl.__retail_packing_busy');
        console.log(JSON.stringify({doctype:dt,full_selection:await evaluate('({item:testRow.item_code,uom:testRow.uom,factor:testRow.conversion_factor,barcode:testRow.barcode})')}));
        await evaluate('cur_frm.fields_dict.items.grid.grid_rows_by_docname[testRow.name].toggle_view(false);cur_frm.fields_dict.items.grid.grid_rows_by_docname[testRow.name].toggle_editable_row(true);true');
        await wait('!!cur_frm.fields_dict.items.grid.grid_rows_by_docname[testRow.name].on_grid_fields_dict.item_name?.$input?.length');
        await evaluate('window.inlineControl=cur_frm.fields_dict.items.grid.grid_rows_by_docname[testRow.name].on_grid_fields_dict.item_name;inlineControl.$input.focus().val("AJP698").trigger("input");true');
        await wait('inlineControl.__retail_packing_search && inlineControl.awesomplete._list.some(r=>r.packing?.barcode==="AJP698")');
        const inlineDimensions=await evaluate('(()=>{const r=inlineControl.awesomplete.ul.getBoundingClientRect();return {width:r.width,left:r.left,right:r.right,viewport:innerWidth}})()');
        assert.ok(inlineDimensions.width>=540 && inlineDimensions.width<=580,JSON.stringify(inlineDimensions));
        assert.ok(inlineDimensions.left>=0 && inlineDimensions.right<=inlineDimensions.viewport,JSON.stringify(inlineDimensions));
        await evaluate('inlineControl.awesomplete.goto(0);true');
        await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
        await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
        await wait('testRow.uom==="Pair-20" && testRow.conversion_factor===20 && !inlineControl.__retail_packing_busy');
        console.log(JSON.stringify({doctype:dt,inline_item_name_selection:true}));
        await evaluate('inlineControl.$input.focus().val("Apple Juice").trigger("input");true');
        await wait('inlineControl.awesomplete.opened && inlineControl.awesomplete._list.some(r=>r.value==="advanced_search__link_option")');
        await evaluate('inlineControl.awesomplete.goto(inlineControl.awesomplete._list.findIndex(r=>r.value==="advanced_search__link_option"));inlineControl.awesomplete.select();true');
        await wait('window.cur_dialog?.title==="Select Item" && cur_dialog.$wrapper.is(":visible")');
        await evaluate('cur_dialog.hide();true');
        await pause(400);
        await evaluate('inlineControl.$input.focus().val("Apple Juice").trigger("input");true');
        await wait('inlineControl.awesomplete.opened && inlineControl.awesomplete._list.some(r=>r.value==="create_new__link_option")');
        await evaluate('inlineControl.awesomplete.goto(inlineControl.awesomplete._list.findIndex(r=>r.value==="create_new__link_option"));inlineControl.awesomplete.select();true');
        await wait('window.cur_dialog?.title==="New Item" && cur_dialog.$wrapper.is(":visible")');
        await evaluate('cur_dialog.hide();true');
        console.log(JSON.stringify({doctype:dt,native_advanced_search_opened:true,native_create_opened:true}));
    }
    console.log(JSON.stringify({javascript_errors:errors}));
    assert.deepEqual(errors,[]);
})().catch(error => {console.error(error); process.exitCode=1;}).finally(async ()=>{
    socket?.close();
    try { process.kill(-chrome.pid, 'SIGTERM'); } catch (error) { if (error.code !== 'ESRCH') throw error; }
    if (chrome.exitCode === null) await Promise.race([new Promise(resolve=>chrome.once('exit',resolve)),pause(2000)]);
    fs.rmSync(profile,{recursive:true,force:true,maxRetries:20,retryDelay:100});
});
