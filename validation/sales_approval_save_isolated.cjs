// Real Chromium/CDP check; the Python harness supplies a temporary session.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const WebSocket = require('../../frappe/node_modules/ws');
const assert = require('node:assert/strict');
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'retail-sidebar-chrome-'));
const chrome = spawn('/home/adler/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome', [
    '--headless=new', '--no-sandbox', '--disable-dev-shm-usage', '--remote-debugging-port=0',
    '--autoplay-policy=no-user-gesture-required',
    '--host-resolver-rules=MAP retail-test.localhost 127.0.0.1', '--no-proxy-server',
    '--user-data-dir=' + profile,
], { stdio: 'ignore' });
let socket, lastSaveRequest;
(async () => {
    const portFile = path.join(profile, 'DevToolsActivePort');
    for (let i = 0; i < 100 && !fs.existsSync(portFile); i++) await sleep(100);
    const [port, endpoint] = fs.readFileSync(portFile, 'utf8').trim().split('\n');
    socket = new WebSocket('ws://127.0.0.1:' + port + endpoint);
    await new Promise(resolve => socket.once('open', resolve));
    let id = 0;
    const pending = new Map();
    const errors = [];
    const failedRequests = [];
    socket.on('message', bytes => {
        const message = JSON.parse(bytes);
        if (message.id) {
            const callback = pending.get(message.id);
            pending.delete(message.id);
            if (message.error) callback.reject(new Error(JSON.stringify(message.error)));
            else callback.resolve(message.result);
        }
        if (message.method === 'Runtime.exceptionThrown') {
            const detail = message.params.exceptionDetails;
            errors.push({ text: detail.exception?.description || detail.text, url: detail.url, line: detail.lineNumber });
        }
        if (message.method === 'Page.javascriptDialogOpening') {
            send('Page.handleJavaScriptDialog', { accept: true }, message.sessionId).catch(error => console.error(error));
        }
        if (message.method === 'Network.responseReceived' && message.params.response.status >= 400) {
            failedRequests.push({ url: message.params.response.url, status: message.params.response.status });
            if (message.params.response.url.endsWith('/frappe.desk.form.save.savedocs')) lastSaveRequest = message.params.requestId;
        }
    });
    const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
        const next = ++id;
        pending.set(next, { resolve, reject });
        socket.send(JSON.stringify({ id: next, method, params, sessionId }));
    });
    const target = await send('Target.createTarget', { url: 'about:blank' });
    const session = (await send('Target.attachToTarget', { targetId: target.targetId, flatten: true })).sessionId;
    const call = (method, params) => send(method, params, session);
    const evaluate = async expression => {
        const result = await call('Runtime.evaluate', { expression: 'globalThis.__retailCdpValue = (' + expression + ')', awaitPromise: true, returnByValue: true });
        if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
        return result.result.value;
    };
    const wait = async expression => {
        for (let i = 0; i < 120; i++) {
            if (await evaluate(expression)) return;
            await sleep(500);
        }
        const state = await evaluate('({ route: window.frappe?.get_route?.(), user: window.frappe?.session?.user, selection: window.frappe?.boot?.retail_sidebar_selection, allowed: window.frappe?.boot?.allowed_workspaces?.map(page => page.name), list: window.cur_list?.doctype })');
        throw new Error('Timed out waiting for ' + expression + ' ' + JSON.stringify({ state, failedRequests, errors }));
    };
    await call('Runtime.enable');
    await call('Page.enable');
    await call('Network.enable');
    await call('Network.setCacheDisabled', { cacheDisabled: true });
    await call('Network.setCookie', { name: 'sid', value: process.env.RETAIL_SID, url: process.env.RETAIL_URL });
    await call('Emulation.setDeviceMetricsOverride', { width: 1600, height: 1100, deviceScaleFactor: 1, mobile: false });


    await call('Page.navigate', {url:process.env.RETAIL_URL+'/app/sales-invoice/SI-81'});
    await wait('!!(window.cur_frm?.doc?.name === "SI-81" && cur_frm.fields_dict.items?.grid?.grid_rows?.length)');
    await sleep(2500);
    await evaluate(`(() => {
        window.approvalPopupCount = 0;
        const show = frappe.ui.Dialog.prototype.show;
        frappe.ui.Dialog.prototype.show = function(...args) {
            if (this.title === 'Approve Price, Discount or Return') window.approvalPopupCount++;
            return show.apply(this, args);
        };
        return true;
    })()`);
    async function approve() {
        await wait('!!(window.cur_dialog && cur_dialog.fields_dict?.password)');
        await evaluate(`(async () => {
            const d=cur_dialog;
            await d.set_value('user','cashier@gmail.com');
            await d.set_value('password',${JSON.stringify(process.env.APPROVAL_TEST_PASSWORD)});
            await d.primary_action(d.get_values());
            return true;
        })()`);
        await sleep(600);
    }
    await evaluate(`(() => {
        const row=cur_frm.fields_dict.items.grid.grid_rows[0]; row.toggle_view(true);
        const input=row.grid_form.fields_dict.custom_rate_including_vat.$input[0];
        input.value=String(Number(row.doc.custom_rate_including_vat)+1);
        input.dispatchEvent(new Event('change',{bubbles:true}));
        return true;
    })()`);
    await approve();
    await evaluate(`(async () => {
        cur_frm.fields_dict.items.grid.grid_rows[0].toggle_view(false);
        await cur_frm.set_value('discount_amount',1);
        cur_frm.fields_dict.discount_amount.$input[0].dispatchEvent(new Event('change',{bubbles:true}));
        return true;
    })()`);
    await approve();
    console.log('before save', await evaluate(`(async () => {
        const response=await frappe.call({method:'retail.backend_sales_admin.requires_approval',args:{doc:cur_frm.doc}});
        return {needsApproval:response.message, count:window.approvalPopupCount, tokens:cur_frm.__retailSalesApprovals?.length, docTokens:cur_frm.doc._retail_sales_approval?.length};
    })()`));
    await evaluate(`(() => {
        window.saveComplete=false; window.saveError=null;
        cur_frm.save().then(()=>window.saveComplete=true).catch(e=>window.saveError=String(e));
        return true;
    })()`);
    await sleep(2500);
    const result=await evaluate(`({saved:window.saveComplete,error:window.saveError,count:window.approvalPopupCount,dialog:window.cur_dialog?.title})`);
    console.log(JSON.stringify({result,failedRequests,errors}));
    if (lastSaveRequest) {
        const body=JSON.parse((await call('Network.getResponseBody',{requestId:lastSaveRequest})).body);
        console.log(JSON.stringify({type:body.exc_type,exception:body.exception,messages:body._server_messages}));
    }
    assert.equal(result.count,2,'Save must not reopen approval after row and discount approval');
    assert.equal(result.saved,true,'Actual Save must complete');
    await evaluate(`(async () => {
        const copied=frappe.model.copy_doc(cur_frm.doc);
        window.newApprovalInvoice=copied.name;
        await frappe.set_route('Form','Sales Invoice',copied.name);
        return true;
    })()`);
    await wait('!!(window.cur_frm?.doc?.name === window.newApprovalInvoice && cur_frm.fields_dict.items?.grid?.grid_rows?.length)');
    await sleep(1800);
    await evaluate(`(() => {
        const row=cur_frm.fields_dict.items.grid.grid_rows[0]; row.toggle_view(true);
        const input=row.grid_form.fields_dict.custom_rate_including_vat.$input[0];
        input.value=String(Number(row.doc.custom_rate_including_vat)+1);
        input.dispatchEvent(new Event('change',{bubbles:true}));
        return true;
    })()`);
    await approve();
    const beforeNewSave=await evaluate('window.approvalPopupCount');
    await evaluate(`(() => {
        cur_frm.fields_dict.items.grid.grid_rows[0].toggle_view(false);
        window.saveComplete=false; window.saveError=null;
        cur_frm.save().then(()=>window.saveComplete=true).catch(e=>window.saveError=String(e));
        return true;
    })()`);
    await sleep(3500);
    const newResult=await evaluate(`({saved:window.saveComplete,error:window.saveError,count:window.approvalPopupCount,name:cur_frm.doc.name,dialog:window.cur_dialog?.title})`);
    console.log(JSON.stringify({newInvoice:newResult}));
    assert.equal(newResult.count,beforeNewSave,'New invoice Save must reuse row and discount approval');
    assert.equal(newResult.saved,true,'Actual new invoice Save must complete');
    assert.ok(newResult.name.startsWith('SI-'));
    // A cancelled approval must still be requested when Save is clicked.
    await evaluate(`(() => {
        const row=cur_frm.fields_dict.items.grid.grid_rows[0]; row.toggle_view(true);
        const input=row.grid_form.fields_dict.custom_rate_including_vat.$input[0];
        input.value=String(Number(row.doc.custom_rate_including_vat)+1);
        input.dispatchEvent(new Event('change',{bubbles:true}));
        return true;
    })()`);
    await wait('!!(window.cur_dialog && cur_dialog.fields_dict?.password)');
    await evaluate('cur_dialog.hide()');
    await sleep(400);
    const beforeUnapprovedSave=await evaluate('window.approvalPopupCount');
    await evaluate(`(() => {
        window.saveComplete=false;
        cur_frm.save().then(()=>window.saveComplete=true).catch(e=>window.saveError=String(e));
        return true;
    })()`);
    await approve();
    await sleep(3500);
    assert.equal(await evaluate('window.approvalPopupCount'),beforeUnapprovedSave+1);
    assert.equal(await evaluate('window.saveComplete'),true);
    console.log('PASS existing and new actual Saves reuse approvals; cancelled new price asks at Save');


})().catch(error=>{console.error(error);process.exitCode=1}).finally(async()=>{
    socket?.close();
    const exited=new Promise(resolve=>chrome.once('exit',resolve));chrome.kill('SIGTERM');await exited;
    await fs.promises.rm(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});
});
