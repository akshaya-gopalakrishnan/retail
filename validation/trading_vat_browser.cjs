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


    await call('Page.navigate',{url:process.env.RETAIL_URL+'/app/company/'+encodeURIComponent(process.env.VAT_COMPANY)});
    await wait('window.cur_frm?.doctype === "Company" && !cur_frm.is_new()');
    await evaluate('cur_frm.fields_dict.custom_enable_trading_sales_vat.tab.set_active()');
    await sleep(400);
    const setting = await evaluate(`(() => {
      const field = cur_frm.fields_dict.custom_enable_trading_sales_vat;
      return {label:field.df.label,value:cur_frm.doc.custom_enable_trading_sales_vat,
        section:field.df.insert_after,tab:field.tab.df.fieldname,exists:!!field.$wrapper.length,visible:field.$wrapper.is(":visible")};
    })()`);
    assert.equal(setting.label,'Enable VAT on Trading Sales Invoices');
    assert.equal(setting.tab,'buying_and_selling_tab');
    assert.ok(setting.exists);
    assert.ok(setting.visible,JSON.stringify(setting));
    await evaluate('frappe.new_doc("Sales Invoice")');
    await wait('window.cur_frm?.doctype === "Sales Invoice" && cur_frm.is_new()');
    await evaluate(`(async()=>{
      await cur_frm.set_value('company',${JSON.stringify(process.env.VAT_COMPANY)});
      await cur_frm.set_value('customer',${JSON.stringify(process.env.VAT_CUSTOMER)});
      const row=cur_frm.doc.items.find(row=>!row.item_code) || cur_frm.add_child('items');
      await frappe.model.set_value(row.doctype,row.name,'item_code',${JSON.stringify(process.env.VAT_ITEM)});
      await frappe.after_ajax();
      cur_frm.refresh_field('items');
    })()`);
    await sleep(3000);
    const values=await evaluate(`(() => {
      const row=cur_frm.doc.items.find(row=>row.item_code);
      return {rate:row.rate,inclusive:row.custom_rate_including_vat,amount:row.amount,
       vat:row.custom_vat_amount,total:cur_frm.doc.total,grand:cur_frm.doc.grand_total,
       taxes:cur_frm.doc.total_taxes_and_charges,policy:cur_frm.doc.custom_trading_vat_disabled,
       template:row.item_tax_template,grid:cur_frm.fields_dict.items.grid.wrapper.text()};
    })()`);
    assert.equal(values.rate,4,JSON.stringify(values));
    assert.equal(values.inclusive,4,JSON.stringify(values));
    assert.equal(values.amount,4,JSON.stringify(values));
    assert.equal(values.vat,0,JSON.stringify(values));
    assert.equal(values.grand,4,JSON.stringify(values));
    assert.equal(values.taxes,0,JSON.stringify(values));
    if (process.env.VAT_BILL_NUMBERS === '1') {
        const billState=await evaluate(`(async()=>{
            await cur_frm.save();
            return {name:cur_frm.doc.name,bill:cur_frm.doc.custom_bill_number,title:cur_frm.doc.title};
        })()`);
        assert.ok(billState.bill);
        assert.equal(billState.title,billState.bill);
        await call('Page.navigate',{url:process.env.RETAIL_URL+'/printview?doctype=Sales%20Invoice&name='+encodeURIComponent(billState.name)+'&format=Sales%20Invoice%20-%20A4&no_letterhead=1'});
        await wait('!!document.querySelector(".invoice-container")');
        const print=await evaluate(`({title:document.title,invoice:document.querySelector('.invoice-details .detail-value').textContent.trim(),customer:document.querySelector('.customer-name').textContent.trim()})`);
        assert.ok(print.title.includes(billState.bill),JSON.stringify(print));
        assert.equal(print.invoice,billState.bill);
        console.log(JSON.stringify({billState,print}));
    }
    const shot=await call('Page.captureScreenshot',{format:'png'});
    fs.writeFileSync('/tmp/trading-vat-browser.png',Buffer.from(shot.data,'base64'));
    console.log(JSON.stringify({setting,values,errors}));

})().catch(error=>{console.error(error);process.exitCode=1}).finally(async()=>{
    socket?.close();
    const exited=new Promise(resolve=>chrome.once('exit',resolve));chrome.kill('SIGTERM');await exited;
    await fs.promises.rm(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});
});
