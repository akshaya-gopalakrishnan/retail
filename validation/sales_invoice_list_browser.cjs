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


    await call('Page.navigate',{url:process.env.RETAIL_URL+'/app/sales-invoice'});
    await wait('window.cur_list?.doctype === "Sales Invoice" && !!cur_list.$result?.find(".list-row-head").length');
    await wait('cur_list.data?.length > 0');
    assert.equal(await evaluate('cur_list.page.fields_dict.title.$input.attr("placeholder")'), "Bill Number");
    const state=await evaluate(`(() => {
        const columns=cur_list.columns.map(c=>({field:c.df?.fieldname,label:c.df?.label,type:c.type,identity:c.identity_field}));
        const rows=cur_list.data.slice(0,5).map(r=>({name:r.name,bill:r.custom_bill_number,customer:r.customer_name,due:r.due_date}));
        return {columns,rows,header:cur_list.$result.find('.list-row-head').text(),
            rendered:cur_list.$result.find('.list-row-container').first().text()};
    })()`);
    for (const field of ['custom_bill_number','customer_name','due_date','posting_date','grand_total']) {
        assert.ok(state.columns.some(c=>c.field===field),JSON.stringify(state));
    }
    assert.ok(!state.columns.some(c=>c.field==='title'),JSON.stringify(state));
    assert.ok(state.header.includes('Bill Number') && state.header.includes('Customer') && state.header.includes('Due Date'),JSON.stringify(state));
    assert.equal(state.columns.filter(c=>c.field==='custom_bill_number').length,1);
    assert.equal(state.columns.at(-1).type,'Status');
    assert.deepEqual(state.columns.map(c=>c.field || (c.type==='Status'?'status':c.type)),['name','custom_bill_number','customer_name','posting_date','due_date','grand_total','status']);
    const billRow=state.rows.find(r=>r.bill);
    if (billRow) {
        assert.ok(billRow.customer);
        assert.ok(billRow.due);
        assert.ok(state.rendered.includes(billRow.bill),JSON.stringify(state));
        assert.ok(state.rendered.includes(billRow.customer),JSON.stringify(state));
    }
    for (const width of [1819,1600,1366]) {
        await call('Emulation.setDeviceMetricsOverride',{width,height:1100,deviceScaleFactor:1,mobile:false});
        await sleep(600);
        const fit=await evaluate(`(() => {
            const root=cur_list.$result[0];
            const cells=[...root.querySelectorAll('.list-row-head .list-row-col')].filter(c=>getComputedStyle(c).display!=='none');
            return {width:root.clientWidth,scroll:root.scrollWidth,
                order:cells.sort((a,b)=>a.getBoundingClientRect().left-b.getBoundingClientRect().left).map(c=>c.textContent.trim())};
        })()`);
        assert.ok(fit.scroll<=fit.width+2,JSON.stringify({viewport:width,fit}));
        assert.ok(fit.order.at(-1).includes('Status'),JSON.stringify(fit));
        console.log(JSON.stringify({viewport:width,fit}));
    }
    const shot=await call('Page.captureScreenshot',{format:'png'});
    fs.writeFileSync('/tmp/sales-invoice-list-bill-columns.png',Buffer.from(shot.data,'base64'));
    console.log(JSON.stringify({state,errors}));

})().catch(error=>{console.error(error);process.exitCode=1}).finally(async()=>{
    socket?.close();
    const exited=new Promise(resolve=>chrome.once('exit',resolve));chrome.kill('SIGTERM');await exited;
    await fs.promises.rm(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});
});
