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


    await call('Page.navigate',{url:process.env.RETAIL_URL+'/app/user/Administrator'});
    await wait('window.cur_frm?.doc?.name === "Administrator" && !!document.querySelector(".retail-sidebar-permissions-grid")');
    await evaluate('cur_frm.layout.tabs.find(tab=>tab.df.fieldname==="roles_permissions_tab").set_active()');
    const capabilities=await evaluate(`(() => {
        const config=[['POS Sync Logs','POS'],['Van Sales Sync Logs','Van Sales'],['Sales Order API Logs','Sales']];
        const groups=frappe.boot.retail_sidebar_registry;
        const original=[...JSON.parse(cur_frm.doc.retail_sidebar_permissions || '{}').allowed || []].sort();
        return config.map(([name,parent])=>{
            const group=groups.find(g=>g.workspace===parent);
            const entry=group.children.find(c=>c.workspace===name);
            if (!entry) throw new Error('Missing registry capability '+name);
            const box=document.querySelector('.retail-sidebar-permissions-grid input[data-unit="'+entry.id+'"]');
            if (!box || box.disabled) throw new Error('Missing/edit-disabled checkbox '+name);
            const heading=box.closest('.retail-sidebar-permissions-group').querySelector('.retail-sidebar-permissions-heading').textContent.trim();
            if (heading!==parent) throw new Error('Wrong permission category '+name+': '+heading);
            const before=box.checked;
            box.click();
            if (JSON.parse(cur_frm.doc.retail_sidebar_permissions).allowed.includes(entry.id)===before) throw new Error('Checkbox did not toggle '+name);
            document.querySelector('.retail-sidebar-permissions-grid input[data-unit="'+entry.id+'"]').click();
            return {label:name,parent:heading,permission_key:entry.id,toggle_verified:true};
        });
    })()`);
    await evaluate('cur_frm.reload_doc()');
    const definitions=[['Van Sales Sync Log','Van Sales Sync Logs','Van Sales'],['POS Sync Log','POS Sync Logs','POS'],['Sales Order API Log','Sales Order API Logs','Sales']];
    const verified=[];
    for (const [doctype,label,parent] of definitions) {
        await evaluate('frappe.set_route("List",'+JSON.stringify(doctype)+')');
        await wait('window.cur_list?.doctype === '+JSON.stringify(doctype)+' && !!document.querySelector(\'.retail-sidebar-item[item-workspace-name="Van Sales Sync Logs"]\')');
        const state=await evaluate(`(() => {
            const side=document.querySelector('.retail-sidebar-item[item-workspace-name="${label}"]');
            const anchor=side?.querySelector(':scope > .desk-sidebar-item > a');
            const vanChildren=[...document.querySelectorAll('.retail-sidebar-item[item-parent="Van Sales"]')].map(e=>e.getAttribute('item-workspace-name'));
            return {parent:side?.getAttribute('item-parent'),href:anchor?.getAttribute('href'),vanChildren,doctype:cur_list.doctype};
        })()`);
        assert.equal(state.parent,parent,JSON.stringify(state));
        assert.equal(state.href,'/app/'+doctype.toLowerCase().replaceAll(' ','-'));
        assert.equal(state.vanChildren[state.vanChildren.indexOf('Van Sales Reports')+1],'Van Sales Sync Logs',JSON.stringify(state));
        verified.push({doctype,label,parent:state.parent,href:state.href});
    }
    await evaluate('frappe.set_route("List","Van Sales Sync Log")');
    await wait('window.cur_list?.doctype === "Van Sales Sync Log"');
    await evaluate(`(() => {
        const root=document.querySelector('.retail-sidebar-item[item-workspace-name="Van Sales"]');
        const children=root?.querySelector(':scope > .sidebar-child-item');
        if (children?.classList.contains('hidden')) root.querySelector(':scope > .desk-sidebar-item .retail-drop-icon')?.click();
        document.querySelector('.retail-sidebar-item[item-workspace-name="Van Sales Sync Logs"]')?.scrollIntoView({block:'nearest'});
        return true;
    })()`);
    await sleep(500);
    const shot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});
    fs.writeFileSync('/tmp/sync-log-sidebar.png',Buffer.from(shot.data,'base64'));
    assert.equal(errors.length,0,JSON.stringify(errors));
    const result={capabilities,sidebar:verified,van_log_immediately_after_reports:true,forms_saved:false,runtime_errors:errors};
    fs.writeFileSync(path.join(__dirname,'sync_log_sidebar_browser_results.json'),JSON.stringify(result,null,2)+'\n');
    console.log(JSON.stringify(result));
})().catch(error=>{console.error(error);process.exitCode=1}).finally(async()=>{
    socket?.close();
    const exited=new Promise(resolve=>chrome.once('exit',resolve));chrome.kill('SIGTERM');await exited;
    await fs.promises.rm(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});
});
