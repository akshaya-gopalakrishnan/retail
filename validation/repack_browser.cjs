// Real Chromium validation; credentials come only from the temporary Python harness.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const WebSocket = require('../../frappe/node_modules/ws');
const assert = require('node:assert/strict');
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'repack-chrome-'));
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

    const base = process.env.RETAIL_URL;
    await call('Network.enable'); await call('Runtime.enable'); await call('Page.enable');
    await call('Network.setCookie', {name:'sid',value:process.env.RETAIL_SID,url:base});
    await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
    await call('Page.navigate',{url:base+'/app/stock-entry/new-stock-entry-repack-check'});
    await wait('window.cur_frm?.doc?.doctype === "Stock Entry" && cur_frm.fields_dict.custom_multiple_boms');
    await evaluate(`new Promise(resolve=>frappe.after_ajax(()=>setTimeout(resolve,800)))`);
    await evaluate(`if(window.cur_dialog?.$wrapper?.text().includes('Recover unsaved local draft')) void cur_dialog.get_secondary_btn().trigger('click');`);
    await evaluate(`(async()=>{
        await cur_frm.set_value('company','nesto');
        await cur_frm.set_value('stock_entry_type','Repack');
    })()`);
    await wait('cur_frm.doc.purpose === "Repack"');
    await evaluate(`(async()=>{
        await cur_frm.set_value('from_warehouse','Raw Material Store - N');
        await cur_frm.set_value('to_warehouse','Finished Goods - N');
        await cur_frm.set_value('custom_multiple_boms',1);
        const section=cur_frm.fields_dict.bom_info_section;
        section.collapse(false);
        cur_frm.refresh_fields();
    })()`);
    const controls=await evaluate(`({section:cur_frm.fields_dict.custom_repack_boms.$wrapper.closest('.form-section').find('.section-head').first().text().trim(),
        table:cur_frm.fields_dict.custom_repack_boms.$wrapper.is(':visible'),
        button:cur_frm.fields_dict.custom_get_repack_items.$wrapper.is(':visible'),
        single:cur_frm.fields_dict.bom_no.$wrapper.is(':visible'),
        multiple:cur_frm.doc.custom_multiple_boms})`);
    assert.equal(controls.section,'BOM Info'); assert.ok(controls.table); assert.ok(controls.button); assert.equal(controls.single,false);
    await evaluate(`(async()=>{
        await cur_frm.set_value('custom_repack_cost_account','Expenses Included In Valuation - N');
        for(const [bom,qty,cost] of [['BOM-I-86-002',10,2.5],['BOM-RTL-ITEM-2026-00031-002',20,5]]){
            const row=cur_frm.add_child('custom_repack_boms');
            await frappe.model.set_value(row.doctype,row.name,{bom_no:bom,qty,packing_cost:cost,use_multi_level_bom:0});
        }
        cur_frm.refresh_field('custom_repack_boms');
        cur_frm.fields_dict.custom_get_repack_items.$input.trigger('click');
    })()`);
    await wait('cur_frm.doc.items?.length === 6 && cur_frm.doc.total_additional_costs === 7.5');
    const result=await evaluate(`({items:cur_frm.doc.items.map(r=>({item:r.item_code,qty:r.qty,group:r.custom_repack_group,basic:r.basic_amount,extra:r.additional_cost,rate:r.valuation_rate})), incoming:cur_frm.doc.total_incoming_value,outgoing:cur_frm.doc.total_outgoing_value,costs:cur_frm.doc.additional_costs.length})`);
    assert.equal(result.incoming-result.outgoing,7.5); assert.equal(result.costs,2);
    assert.equal(result.items[2].extra,2.5); assert.equal(result.items[5].extra,5);
    await evaluate(`void cur_frm.fields_dict.custom_get_repack_items.$input.trigger('click')`);
    await wait('window.cur_dialog?.$wrapper?.is(":visible") && cur_dialog.$wrapper.text().includes("Rebuild the BOM-generated items")');
    await evaluate(`void cur_dialog.get_primary_btn().trigger('click')`);
    await wait('!frappe.dom.freeze_count && cur_frm.doc.items?.length === 6 && cur_frm.doc.additional_costs?.length === 2');
    await evaluate(`new Promise(resolve=>frappe.after_ajax(resolve))`);
    fs.writeFileSync('/tmp/repack-bom-info.png',Buffer.from((await call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    // Returning to single-BOM mode restores the original controls.
    await evaluate(`(async()=>{
        cur_frm.clear_table('items');cur_frm.clear_table('additional_costs');
        await cur_frm.set_value('custom_multiple_boms',0);
        await cur_frm.set_value('from_bom',1);
        cur_frm.refresh_fields();cur_frm.fields_dict.bom_info_section.collapse(false);
    })()`);
    fs.writeFileSync('/tmp/repack-single-mode.png',Buffer.from((await call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    assert.ok(await evaluate(`cur_frm.fields_dict.bom_no.$wrapper.is(':visible')`), await evaluate(`JSON.stringify({multi:cur_frm.doc.custom_multiple_boms,from:cur_frm.doc.from_bom,condition:cur_frm.fields_dict.bom_no.df.depends_on,original:cur_frm.fields_dict.bom_no.df.retail_repack_depends_on,hidden:cur_frm.fields_dict.bom_no.df.hidden,dependency:cur_frm.fields_dict.bom_no.df.hidden_due_to_dependency,section:cur_frm.fields_dict.bom_info_section.wrapper.is(':visible'),form:cur_frm.fields_dict.bom_no.$wrapper.attr('class')})`));
    assert.equal(errors.length,0,JSON.stringify(errors));
    console.log(JSON.stringify({controls,result,duplicateReload:'passed',ordinarySingleBOM:'passed',browserErrors:errors.length}));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
    socket?.close();try{process.kill(-chrome.pid,'SIGTERM');}catch{}
    await pause(600);
    try{fs.rmSync(profile,{recursive:true,force:true,maxRetries:10,retryDelay:100});}catch{}
});
