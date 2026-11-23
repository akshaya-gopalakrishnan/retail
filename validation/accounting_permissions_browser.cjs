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

    await call('Page.navigate', {url: process.env.RETAIL_URL + '/app/user/' + process.env.RETAIL_USER});
    await wait('window.frappe?.search?.utils?.__retail_module_filters_installed && window.frappe?.boot?.retail_sidebar_registry');
    const identity = await evaluate('frappe.session.user');
    assert.equal(identity, process.env.RETAIL_USER);
    const results = await evaluate(`(() => {
        const output={};
        for (const word of ['Account','Cost Center','GL Entry','Journal Entry','Sales Invoice','POS Invoice']) {
            output[word]=frappe.search.utils.get_doctypes(word).map(x => ({match:x.match,route:x.route,type:x.type}));
        }
        return output;
    })()`);
    for (const name of ['Account','Cost Center','GL Entry','Journal Entry']) {
        assert(!results[name].some(x => x.match===name), JSON.stringify({name,results:results[name]}));
    }
    assert(results['Sales Invoice'].some(x=>x.match==='Sales Invoice'));
    assert(results['POS Invoice'].some(x=>x.match==='POS Invoice'));
    const dashboardCheck=await evaluate(`(() => {
        const original=frappe.boot.dashboards;
        const filteredNames=original.map(row=>row.name);
        frappe.boot.dashboards=[...original,{name:'Accounts'}];
        const suggestions=frappe.search.utils.get_dashboards('Accounts').map(row=>row.route);
        frappe.boot.dashboards=original;
        return {filteredNames,suggestions};
    })()`);
    assert(!dashboardCheck.filteredNames.includes('Accounts'));
    assert(!dashboardCheck.suggestions.some(route=>route[0]==='dashboard-view' && route[1]==='Accounts'));
    const statuses={};
    for (const endpoint of ['/app/dashboard-view/Accounts', '/api/method/frappe.desk.form.load.getdoc?doctype=Dashboard&name=Accounts', '/api/method/frappe.desk.doctype.dashboard.dashboard.get_permitted_charts?dashboard_name=Accounts', '/api/method/frappe.client.get_list?doctype=Account', '/app/account', '/app/cost-center',
        '/api/method/frappe.desk.treeview.get_children?doctype=Account&parent=All%20Accounts&is_root=true',
        '/api/method/frappe.desk.query_report.get_script?report_name=General%20Ledger']) {
        statuses[endpoint]=await evaluate('fetch('+JSON.stringify(endpoint)+').then(r=>r.status)');
        assert.equal(statuses[endpoint],403,endpoint);
    }
    const positive={};
    for (const doctype of ['Sales Invoice','Purchase Invoice','POS Invoice']) {
        positive[doctype]=await evaluate('fetch("/api/method/frappe.client.get_list?doctype="+encodeURIComponent('+JSON.stringify(doctype)+')+"&limit_page_length=1").then(r=>r.status)');
        assert.equal(positive[doctype],200,doctype);
    }
    const search=await evaluate('fetch("/api/method/frappe.utils.global_search.search?text=cash").then(r=>r.json()).then(data=>data.message)');
    assert(Array.isArray(search));
    assert(!search.some(row=>['Account','GL Entry','Cost Center'].includes(row.doctype)));
    const result={identity,mode:'existing local user; in-memory sidebar overlay; saved roles/settings unchanged',
        accounting_suggestions:'hidden, including New',accounting_dashboard:dashboardCheck,sales_and_pos_suggestions:'present',denied_requests:statuses,
        permitted_invoice_lists:positive,global_search:'no denied accounting records',runtime_errors:errors};
    fs.writeFileSync(path.join(__dirname,'accounting_permissions_browser_results.json'),JSON.stringify(result,null,2)+'\n');
    console.log(JSON.stringify(result));
})().catch(error=>{console.error(error);process.exitCode=1}).finally(async()=>{
    socket?.close();
    const exited=new Promise(resolve=>chrome.once('exit',resolve));chrome.kill('SIGTERM');await exited;
    await fs.promises.rm(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});
});
