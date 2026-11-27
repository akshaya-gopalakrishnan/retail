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


    const measurements = [];
    const traffic = [];
    let changedAt = Date.now();
    socket.on('message', bytes => {
        const m = JSON.parse(bytes);
        if (m.sessionId !== session) return;
        if (m.method === 'Network.requestWillBeSent') {
            if (m.params.request.url.includes('/api/')) changedAt = Date.now();
        }
        if (m.method === 'Network.responseReceived') {
            const r = m.params.response;
            if (r.url.includes('/api/')) {
                changedAt = Date.now();
                traffic.push({url:r.url, status:r.status, ttfb: r.timing ? Math.round(r.timing.receiveHeadersStart-r.timing.sendEnd):null});
            }
        }
    });
    await call('Page.navigate', {url:process.env.RETAIL_URL+'/app/business-home'});
    await wait('window.frappe?.boot && window.frappe?.get_route?.()[1] === "Business Home"');
    await wait('frappe.after_ajax && window.$ && $.active === 0');
    await sleep(1200);
    const boot = await evaluate('({bytes:JSON.stringify(frappe.boot).length,sidebars:frappe.boot.allowed_workspaces.map(w=>w.name),editor:frappe.boot.retail_sidebar_editor_registry})');
    const initial=traffic.splice(0);
    console.log(JSON.stringify({boot,initial}));
    for (const [name, route] of [
        ['Items',['Workspaces','Items']], ['Sales',['Workspaces','Sales']],
        ['Stocks',['Workspaces','Stocks']], ['POS',['Workspaces','POS']],
        ['Accounts',['Workspaces','Accounts']], ['Reports',['Workspaces','Reports']],
        ['Business Home',['Workspaces','Business Home']],
        ['Item',['List','Item']], ['Customer',['List','Customer']],
        ['Purchase Invoice',['List','Purchase Invoice']], ['POS Invoice',['List','POS Invoice']],
    ]) {
        traffic.length=0; const began=Date.now();changedAt=began;
        await evaluate('frappe.set_route('+JSON.stringify(route)+')');
        await wait('frappe.get_route()[0] === '+JSON.stringify(route[0])+' && frappe.get_route()[1] === '+JSON.stringify(route[1]));
        await wait('$.active === 0');
        for(let i=0;i<120;i++) {await sleep(100);if(Date.now()-changedAt>800 && await evaluate('$.active === 0'))break;}
        const state=await evaluate(`({route:frappe.get_route(), cards:[...document.querySelectorAll('.layout-main-section .number')].filter(e=>e.getBoundingClientRect().width).map(e=>e.textContent.trim()), loading:[...document.querySelectorAll('.number-card-loading')].filter(e=>e.getBoundingClientRect().width).length})`);
        const row={name,quiet_ms:Math.max(0,Date.now()-began-800),getdoctype:traffic.filter(r=>r.url.includes('getdoctype')),getdoc:traffic.filter(r=>r.url.includes('load.getdoc?')),requests:traffic,state};
        measurements.push(row); console.log(JSON.stringify(row));
        if(route[0]==='Workspaces') assert.equal(state.loading,0,JSON.stringify(row));
        if(name==='Purchase Invoice') assert.ok(!row.getdoctype.some(r=>decodeURIComponent(r.url).includes('doctype=Purchase Receipt')),JSON.stringify(row));
    }
    // Native chart filters still load real metadata when explicitly opened.
    await evaluate('frappe.set_route("Workspaces", "Reports")');
    await wait('frappe.get_route()[1] === "Reports" && $.active === 0');
    await sleep(400);
    await evaluate(`document.querySelectorAll('.filter-chart').forEach(e=>{if(e.getBoundingClientRect().width && !window.__speedClickedFilter){window.__speedClickedFilter=true;e.click();}})`);
    await wait('$(".filter-popover:visible").length > 0');
    await evaluate('void $(".filter-chart").popover("hide")');
    // The User permission editor must lazy-load its full authorized checklist.
    await evaluate('frappe.set_route("Form", "User", "Administrator")');
    await wait('window.cur_frm?.doctype === "User" && cur_frm.doc.name === "Administrator"');
    await wait('document.querySelectorAll(".retail-sidebar-permissions-editor input[type=checkbox]").length > 20');
    const editorChecks=await evaluate('document.querySelectorAll(".retail-sidebar-permissions-editor input[type=checkbox]").length');
    assert.ok(editorChecks>20);
    const endpointTimings=[];
    for(let i=0;i<2;i++) endpointTimings.push(await evaluate(`(async()=>{const start=performance.now();const r=await frappe.xcall('frappe.desk.desktop.get_desktop_page',{page:JSON.stringify({name:'Business Home'})});return {ms:Math.round(performance.now()-start),widgets:r.retail_widget_definitions.length}})()`));
    assert.ok(endpointTimings.every(r=>r.widgets>0));
    // Concurrent API callers must share a single metadata request and all receive metadata.
    const dedupe=await evaluate(`(async()=>{const dt='Payment Entry';delete locals.DocType[dt];performance.clearResourceTimings();await Promise.all([1,2,3].map(()=>frappe.model.with_doctype(dt)));return {loaded:!!locals.DocType[dt],requests:performance.getEntriesByType('resource').filter(r=>r.name.includes('getdoctype')&&decodeURIComponent(r.name).includes('doctype=Payment Entry')).length}})()`);
    assert.deepEqual(dedupe,{loaded:true,requests:1});
    fs.writeFileSync(require('node:path').join(__dirname,'desk_speed_browser_results.json'),JSON.stringify({boot,measurements,dedupe,errors,failedRequests},null,2));
    console.log(JSON.stringify({dedupe,editorChecks,endpointTimings,errors,failedRequests}));
    assert.equal(errors.length,0,JSON.stringify(errors));
    assert.equal(failedRequests.filter(r=>r.url.includes('/api/')).length,0,JSON.stringify(failedRequests));
    assert.ok(measurements.filter(r=>r.state.route[0]==='Workspaces').every(r=>r.getdoctype.length===0), 'Workspaces must not download transaction metadata');

})().catch(error=>{console.error(error);process.exitCode=1}).finally(async()=>{
    socket?.close();
    const exited=new Promise(resolve=>chrome.once('exit',resolve));chrome.kill('SIGTERM');await exited;
    await fs.promises.rm(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});
});
