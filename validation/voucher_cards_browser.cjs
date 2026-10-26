// Real Chromium validation; credentials come only from the temporary Python harness.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const WebSocket = require('../../frappe/node_modules/ws');
const assert = require('node:assert/strict');
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'voucher-card-chrome-'));
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
    await call('Page.navigate', {url: base + '/app/voucher-card-batch/' + encodeURIComponent(process.env.RETAIL_BATCH)});
    await wait('window.cur_frm?.doc?.doctype === "Voucher Card Batch" && cur_frm.doc.name === ' + JSON.stringify(process.env.RETAIL_BATCH));
    await wait('Array.from(document.querySelectorAll(".custom-actions button")).some(b => b.textContent.includes("Cards / Current Status"))');
    const form = await evaluate('({status:cur_frm.doc.generation_status,count:cur_frm.doc.generated_count,buttons:Array.from(document.querySelectorAll(".custom-actions button")).map(b=>b.textContent.trim()),menu:frappe.boot.retail_sidebar_registry.find(r=>r.workspace==="Promotions").children.find(r=>r.route?.[1]==="Voucher Card Batch")})');
    assert.equal(form.status, 'Complete'); assert.equal(form.count, Number(process.env.RETAIL_EXPECTED_COUNT || 10000)); assert.equal(form.menu.label, 'Voucher Cards');
    assert.ok(form.buttons.includes('Print Format'));
    assert.ok(form.buttons.includes('Print'));
    assert.ok(!form.buttons.includes('Print Cards'));
    assert.ok(await evaluate('["logo","terms","print_from","print_to","label_width","label_height"].every(field=>!cur_frm.fields_dict[field].$wrapper.is(":visible"))'));
    await evaluate('Array.from(document.querySelectorAll(".custom-actions button")).find(button=>button.textContent.trim()==="Print Format").click()');
    await wait('window.cur_dialog?.fields_dict?.design_html?.get_value()?.includes("voucher-card")');
    const printDialog = await evaluate('({fields:Object.keys(cur_dialog.fields_dict), html:!!cur_dialog.get_value("design_html"), css:!!cur_dialog.get_value("design_css")})');
    for (const field of ['logo','terms','print_from','print_to','label_width','label_height','design_html','design_css']) assert.ok(printDialog.fields.includes(field));
    if (process.env.RETAIL_PRINT_FORMAT) {
        await evaluate('cur_dialog.set_value("print_format", ' + JSON.stringify(process.env.RETAIL_PRINT_FORMAT) + ')');
        await evaluate('(async()=>{ await cur_dialog.set_value("design_html", cur_dialog.get_value("design_html") + "<!-- voucher-dialog-test -->"); await cur_dialog.set_value("design_css", cur_dialog.get_value("design_css") + " /* voucher-dialog-test */"); await cur_dialog.set_value("terms", "Temporary dialog terms"); cur_dialog.get_primary_btn().trigger("click"); })()');
        await wait('!window.cur_dialog || !cur_dialog.display');
        const savedDesign = await evaluate('(async()=>{const format=await frappe.db.get_doc("Print Format", ' + JSON.stringify(process.env.RETAIL_PRINT_FORMAT) + ');const batch=await frappe.call({method:"frappe.client.get",args:{doctype:"Voucher Card Batch",name:cur_frm.doc.name}});return {html:format.html.includes("voucher-dialog-test"),css:format.css.includes("voucher-dialog-test"),terms:batch.message.terms};})()');
        assert.deepEqual(savedDesign, {html:true,css:true,terms:'Temporary dialog terms'});
    } else await evaluate('cur_dialog.hide()');
    fs.writeFileSync('/tmp/voucher-card-form.png', Buffer.from((await call('Page.captureScreenshot', {format: 'png'})).data, 'base64'));
    await evaluate('frappe.set_route("List", "Gift Voucher Ledger", {voucher_card_batch:' + JSON.stringify(process.env.RETAIL_BATCH) + '})');
    await wait('window.cur_list?.doctype === "Gift Voucher Ledger" && cur_list.data?.length === 2');
    const currentCards = await evaluate('cur_list.data.map(row=>({name:row.name,status:row.status,balance:row.balance_amount,type:row.voucher_kind}))');
    assert.equal(new Set(currentCards.map(row=>row.name)).size, 2);
    assert.ok(currentCards.every(row=>row.balance === 40 && row.status === 'Partially Used' && row.type === 'Voucher Card'));
    for (const field of ['voucher_kind', 'voucher_amount', 'balance_amount']) {
        assert.ok(await evaluate('cur_list.columns.some(column=>column.df?.fieldname === ' + JSON.stringify(field) + ')'), 'Missing column: ' + field);
    }
    await evaluate('document.querySelector(".custom-actions .dropdown-item[data-label=Vouchers]").click()');
    await wait('cur_list.data?.length > 0 && cur_list.data.every(row=>row.voucher_kind === "Promotion Voucher")');
    await evaluate('document.querySelector(".custom-actions .dropdown-item[data-label=Cards]").click()');
    await wait('cur_list.data?.length > 0 && cur_list.data.every(row=>row.voucher_kind === "Voucher Card")');
    await evaluate('document.querySelector(".custom-actions .dropdown-item[data-label=All]").click()');
    await wait('cur_list.data?.some(row=>row.voucher_kind === "Voucher Card") && cur_list.data.some(row=>row.voucher_kind === "Promotion Voucher")');
    await call('Page.navigate', {url: base + '/printview?doctype=Voucher%20Card%20Batch&name=' + encodeURIComponent(process.env.RETAIL_BATCH) + '&format=Voucher%20Cards%20-%20A4&no_letterhead=1'});
    await wait('document.querySelectorAll(".voucher-card").length === 2');
    await wait('Array.from(document.querySelectorAll(".voucher-barcode img")).every(i=>i.complete && i.naturalWidth>0)');
    const sizes = await evaluate('Array.from(document.querySelectorAll(".voucher-card")).map(c=>({width:c.getBoundingClientRect().width,height:c.getBoundingClientRect().height,code:c.querySelector(".voucher-code").textContent.trim()}))');
    assert.equal(sizes.length, 2); assert.ok(Math.abs(sizes[0].width - 323.53)<2); assert.ok(Math.abs(sizes[0].height-204.09)<2);
    assert.notEqual(sizes[0].code, sizes[1].code);
    fs.writeFileSync('/tmp/voucher-cards-a4.png', Buffer.from((await call('Page.captureScreenshot', {format: 'png'})).data, 'base64'));
    const pdf = await call('Page.printToPDF', {printBackground: true, preferCSSPageSize: true});
    fs.writeFileSync('/tmp/voucher-cards-a4.pdf', Buffer.from(pdf.data, 'base64'));
    await call('Page.navigate', {url: base + '/printview?doctype=Voucher%20Card%20Batch&name=' + encodeURIComponent(process.env.RETAIL_BATCH) + '&format=Voucher%20Cards%20-%20Labels&no_letterhead=1'});
    await wait('document.querySelectorAll(".voucher-card").length === 2');
    const labels = await call('Page.printToPDF', {printBackground: true, preferCSSPageSize: true});
    fs.writeFileSync('/tmp/voucher-cards-labels.pdf', Buffer.from(labels.data, 'base64'));
    console.log(JSON.stringify({form, physical_card_pixels:sizes, current_status_rows:currentCards, print_format_dialog:printDialog, javascript_errors:errors, print_pdf:true}));
    assert.deepEqual(errors, []);
})().catch(error => {console.error(error); process.exitCode=1;}).finally(async ()=>{
    socket?.close();
    try { process.kill(-chrome.pid, 'SIGTERM'); } catch (error) { if (error.code !== 'ESRCH') throw error; }
    if (chrome.exitCode === null) await Promise.race([new Promise(resolve=>chrome.once('exit',resolve)),pause(2000)]);
    fs.rmSync(profile,{recursive:true,force:true,maxRetries:20,retryDelay:100});
});
