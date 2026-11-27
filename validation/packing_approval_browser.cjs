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
let socket;
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



    await call('Page.navigate', {url:process.env.RETAIL_URL+'/app/sales-invoice/SI-88'});
    await wait('window.cur_frm?.doc?.name === "SI-88"');
    await sleep(1500);

    const choices=JSON.parse(fs.readFileSync('/tmp/packing-approval-choices.json','utf8'));
    const results=[];
    for (const choice of choices.filter(c => ['I-81','I-22','I-57','I-56'].includes(c.parent)).slice(0,10)) {
        const result=await evaluate(`(async () => {
            const choice=${JSON.stringify(choice)};
            const frm=cur_frm;
            frm.doc.items=[];
            const row=frm.add_child('items');
            await frappe.model.set_value(row.doctype,row.name,'item_code',choice.parent);
            await frappe.after_ajax();
            await frappe.model.set_value(row.doctype,row.name,'uom',choice.uom);
            await frappe.after_ajax();
            await new Promise(r=>setTimeout(r,400));
            await frappe.after_ajax();
            const response=await frappe.call({method:'retail.backend_sales_admin.requires_approval',args:{doc:frm.doc}});
            if (response.message) console.log('Unexpected approval',choice.parent);
            if (!response.message) await frm.script_manager.trigger('before_save');
            if (window.cur_dialog?.fields_dict?.password) throw new Error('Save prompted for unchanged packing');
            return {approval:response.message,doc:frm.doc};
        })()`);
        assert.equal(result.approval, false, 'Unchanged packing must not require approval');
        results.push(result);
        console.log(JSON.stringify({choice,approval:result.approval,rate:result.doc.items[0].rate}));
        fs.writeFileSync('/tmp/packing-approval-browser.json',JSON.stringify(results));
    }

    await evaluate(`(() => {
        const row=cur_frm.fields_dict.items.grid.grid_rows_by_docname[cur_frm.doc.items[0].name];
        cur_frm.refresh_field('items');
        const gridRow=cur_frm.fields_dict.items.grid.grid_rows_by_docname[cur_frm.doc.items[0].name];
        gridRow.toggle_view(true);
        const input=gridRow.grid_form.fields_dict.rate.$input[0];
        input.value=String(Number(gridRow.doc.rate)+1);
        input.dispatchEvent(new Event('change',{bubbles:true}));
        return true;
    })()`);
    await wait('!!window.cur_dialog?.fields_dict?.password');
    console.log('PASS: unchanged packing Save has no popup; manual grid price edit opens Admin approval');
})().catch(error=>{console.error(error);process.exitCode=1}).finally(async()=>{
    socket?.close();
    const exited=new Promise(resolve=>chrome.once('exit',resolve));chrome.kill('SIGTERM');await exited;
    await fs.promises.rm(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});
});
