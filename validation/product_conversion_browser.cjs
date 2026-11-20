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
    await call('Page.navigate',{url:base+'/app/product-conversion/new-product-conversion-browser'});
    await wait('window.cur_frm?.doc?.doctype === "Product Conversion" && cur_frm.doc.source_warehouse');
    await evaluate(`new Promise(resolve=>frappe.after_ajax(()=>setTimeout(resolve,600)))`);
    const initial=await evaluate(`({source:cur_frm.doc.source_warehouse,target:cur_frm.doc.target_warehouse,currency:cur_frm.doc.currency,sidebar:frappe.boot.retail_sidebar_registry.find(r=>r.workspace==='Items').children.map(r=>({label:r.label,route:r.route}))})`);
    assert.equal(initial.source,'Stores - N');assert.equal(initial.target,'Stores - N');
    const position=initial.sidebar.findIndex(r=>r.label==='Brands');assert.equal(initial.sidebar[position+1].label,'Product Conversion');
    await wait('document.querySelector(\'.retail-persistent-sidebar [item-workspace-name="Product Conversion Link"]\')');
    const renderedNavigation=await evaluate(`(()=>{const n=document.querySelector('.retail-persistent-sidebar [item-workspace-name="Product Conversion Link"]');return {parent:n.getAttribute('item-parent'),previous:n.previousElementSibling?.getAttribute('item-workspace-name'),visible:$(n).is(':visible'),breadcrumb:document.querySelector('#navbar-breadcrumbs')?.textContent};})()`);
    assert.equal(renderedNavigation.parent,'Items');assert.equal(renderedNavigation.previous,'Brands');assert.ok(renderedNavigation.visible);
    assert.ok(renderedNavigation.breadcrumb.includes('Items'),renderedNavigation.breadcrumb);
    assert.ok(await evaluate(`cur_frm.fields_dict.get_items_from_bom.$wrapper.is(':visible')`));
    assert.ok(await evaluate(`cur_frm.fields_dict.get_items_from_main_item.$wrapper.is(':visible')`));
    await evaluate(`void cur_frm.fields_dict.get_items_from_bom.$input.trigger('click')`);
    await wait('window.cur_dialog?.fields_dict?.bom_no');
    await evaluate(`(async()=>{await cur_dialog.set_values({bom_no:'BOM-I-86-002',qty:10,use_multi_level_bom:0,labour_cost:2,packing_cost:3});cur_dialog.get_primary_btn().trigger('click');})()`);
    await wait('cur_frm.doc.items?.length===1 && cur_frm.doc.materials?.length===2 && !cur_dialog?.$wrapper?.is(":visible")');
    assert.equal(await evaluate(`cur_frm.fields_dict.materials.$wrapper.is(':visible')`),false);
    assert.equal(await evaluate(`cur_frm.fields_dict.items.grid.cannot_add_rows`),false);
    await evaluate(`void cur_frm.fields_dict.items.grid.wrapper.find('.grid-add-row').first().trigger('click')`);
    await wait('cur_frm.doc.items?.length===2');
    await evaluate(`(async()=>{
        const row=cur_frm.doc.items[1];
        await frappe.model.set_value(row.doctype,row.name,'item_code','I-23');
        await frappe.model.set_value(row.doctype,row.name,'main_item','I-21');
        await frappe.model.set_value(row.doctype,row.name,'qty',20);
        await frappe.model.set_value(row.doctype,row.name,'main_qty',4);
        await frappe.model.set_value(row.doctype,row.name,'labour_cost',4);
        await frappe.model.set_value(row.doctype,row.name,'packing_cost',5);
        cur_frm.custom_buttons['Refresh Stock and Costs'].trigger('click');
    })()`);
    await wait('cur_frm.doc.items?.length===2 && cur_frm.doc.materials?.length===3 && cur_frm.doc.items[1].total_cost===85.2');
    const stockInfo=await evaluate(`({stock:cur_frm.doc.items[1].main_stock_qty,cost:cur_frm.doc.items[1].main_unit_cost,consume:cur_frm.doc.items[1].main_qty})`);
    assert.equal(stockInfo.stock,150);assert.equal(stockInfo.consume,4);
    await evaluate(`void cur_frm.custom_buttons['Consumption Details'].trigger('click')`);
    await wait('cur_dialog?.fields_dict?.product');
    await evaluate(`(async()=>{await cur_dialog.set_value('product',cur_frm.doc.items[0].row_key);cur_dialog.get_primary_btn().trigger('click');})()`);
    await wait('cur_dialog?.fields_dict?.lines');
    assert.equal(await evaluate(`cur_dialog.fields_dict.lines.grid.get_data().length`),2);
    await evaluate(`void cur_dialog.get_primary_btn().trigger('click')`);
    await wait('!cur_dialog?.$wrapper?.is(":visible") && cur_frm.doc.materials.length===3');
    const loaded=await evaluate(`({products:cur_frm.doc.items.map(r=>({item:r.item_code,qty:r.qty,product:r.product_cost,labour:r.labour_cost,packing:r.packing_cost,total:r.total_cost,unit:r.unit_cost,master:r.update_item_master})),materials:cur_frm.doc.materials.map(r=>({item:r.item_code,qty:r.qty,stock:r.current_stock,cost:r.unit_cost,amount:r.amount})),total:cur_frm.doc.total_cost})`);
    assert.equal(loaded.products[0].total,29.77);assert.equal(loaded.products[1].total,85.2);assert.equal(loaded.total,114.97);
    assert.ok(loaded.products.every(r=>!r.master));
    await evaluate(`(async()=>{const r=cur_frm.doc.items[1];await frappe.model.set_value(r.doctype,r.name,'qty',10);cur_frm.custom_buttons['Refresh Stock and Costs'].trigger('click');})()`);
    await wait('cur_frm.doc.materials[2].qty===2 && cur_frm.doc.items[1].total_cost===47.1');
    await evaluate(`new Promise(resolve=>frappe.after_ajax(resolve))`);
    await pause(600);
    fs.writeFileSync('/tmp/product-conversion-form.png',Buffer.from((await call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    // Exercise the View routes without navigating or saving this unsaved form.
    await evaluate(`(async()=>{
        cur_frm.doc.stock_entry='SE-CONVERSION-VIEW-CHECK';cur_frm.doc.docstatus=1;
        await cur_frm.script_manager.trigger('refresh');
        window.__pcRoutes=[];window.__pcOriginalRoute=frappe.set_route;
        frappe.set_route=(...route)=>window.__pcRoutes.push({route,filters:JSON.parse(JSON.stringify(frappe.route_options))});
        for(const label of ['Stock Ledger','Accounting Ledger','Serial and Batch Summary'])cur_frm.custom_buttons[label].trigger('click');
        frappe.set_route=window.__pcOriginalRoute;
        cur_frm.doc.docstatus=0;cur_frm.doc.stock_entry=null;
    })()`);
    const routes=await evaluate('window.__pcRoutes');
    assert.deepEqual(routes.map(r=>r.route[1]),['Stock Ledger','General Ledger','Serial and Batch Summary']);
    assert.equal(routes[0].filters.voucher_no,'SE-CONVERSION-VIEW-CHECK');
    assert.deepEqual(routes[2].filters.voucher_no,['SE-CONVERSION-VIEW-CHECK']);assert.equal(routes[2].filters.voucher_type,'Stock Entry');
    assert.equal(errors.length,0,JSON.stringify(errors));
    console.log(JSON.stringify({initial,renderedNavigation,stockInfo,loaded,quantityScaling:'passed',viewRoutes:routes,browserErrors:errors.length}));
    if(process.env.RETAIL_PRINT_HTML){
        await call('Page.navigate',{url:'file://'+process.env.RETAIL_PRINT_HTML});
        await wait('document.querySelectorAll(".pc-consumption").length===2');
        fs.writeFileSync('/tmp/product-conversion-print.png',Buffer.from((await call('Page.captureScreenshot',{format:'png'})).data,'base64'));
        fs.writeFileSync('/tmp/product-conversion-print.pdf',Buffer.from((await call('Page.printToPDF',{printBackground:true,preferCSSPageSize:true})).data,'base64'));
        console.log('Print layout and PDF rendered.');
    }
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
    socket?.close();try{process.kill(-chrome.pid,'SIGTERM');}catch{}
    await pause(600);try{fs.rmSync(profile,{recursive:true,force:true,maxRetries:10,retryDelay:100});}catch{}
});
