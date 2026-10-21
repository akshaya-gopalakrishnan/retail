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
    await call('Page.navigate', { url: process.env.RETAIL_URL + '/app/user/Administrator' });
    await wait('window.cur_frm?.doc?.name === "Administrator" && !!document.querySelector(".retail-sidebar-permissions-grid")');
    if (process.env.RETAIL_MENU_AUDIT === '1') {
        for (const route of JSON.parse(process.env.RETAIL_AUDIT_ROUTES || '["business-home","item","customer","sales-invoice","purchase-invoice","stock-entry"]')) {
            const offset = failedRequests.length;
            const errorOffset = errors.length;
            await evaluate('frappe.set_route(' + JSON.stringify(route) + ')');
            await wait('!!window.frappe?.boot && !!window.frappe?.get_route');
            await sleep(2500);
            const denied = failedRequests.slice(offset).filter(r => r.status === 403);
            const popup = await evaluate('Array.from(document.querySelectorAll(".modal.show .modal-body, .modal.in .modal-body")).some(node => node.innerText.includes("You do not have permission"))');
            console.log(JSON.stringify({ route, denied_requests: denied, permission_popup: popup, runtime_errors: errors.slice(errorOffset) }));
            assert.equal(denied.length, 0, 'Allowed menu requests: ' + route);
            assert.equal(popup, false, 'Allowed menu permission popup: ' + route);
        }
        return;
    }
    await evaluate('cur_frm.layout.tabs.find(tab => tab.df.fieldname === "roles_permissions_tab").set_active()');
    await evaluate('(() => { frappe.boot.can_manage_access = false; return cur_frm.refresh(); })()');
    assert.equal(await evaluate('document.querySelector(".retail-sidebar-permissions-grid input").disabled'), false);
    await evaluate('frappe.boot.can_manage_access = true');
    await evaluate('document.querySelector(".retail-sidebar-permissions-editor .deselect-all").click()');
    assert.deepEqual(await evaluate('JSON.parse(cur_frm.doc.retail_sidebar_permissions).allowed'), []);
    // Verify editability without persisting a change to the real Administrator.
    await evaluate('cur_frm.reload_doc()');
    console.log(JSON.stringify({administrator_editor: 'editable', server: process.env.RETAIL_URL,
        identity: await evaluate('frappe.session.user'),
        can_manage_access: await evaluate('frappe.boot.can_manage_access')}));
    if (process.env.RETAIL_ADMIN_ONLY === '1') {
        assert(Array.isArray(await evaluate('frappe.boot.retail_sidebar_selection')));
        await wait('!!document.querySelector(".retail-persistent-sidebar") && !document.querySelector(".retail-persistent-sidebar").innerText.includes("Customers")');
        assert.equal(await evaluate('fetch("/api/method/frappe.client.get_list?doctype=Quotation").then(response => response.status)'), 403);
        assert.equal(await evaluate('fetch("/app/quotation").then(response => response.status)'), 403);
        // Persist the unchanged saved choices through the real recovery editor.
        await evaluate('cur_frm.dirty()');
        await evaluate('cur_frm.save()');
        await evaluate('cur_frm.reload_doc()');
        console.log(JSON.stringify({ administrator_saved_selection: 'enforced',
            denied_customer_sidebar: 'hidden', denied_quotation_api: 403,
            denied_quotation_url: 403, own_permission_editor_save_reload: 'passed' }));
        return;
    }
    await call('Page.navigate', { url: process.env.RETAIL_URL + '/app/user/' + process.env.RETAIL_USER });
    await wait('window.cur_frm?.doc?.name === ' + JSON.stringify(process.env.RETAIL_USER) + ' && !!document.querySelector(".retail-sidebar-permissions-grid")');
    await evaluate('cur_frm.layout.tabs.find(tab => tab.df.fieldname === "roles_permissions_tab").set_active()');
    await sleep(300);
    const measurements = [];
    for (const width of [1600, 1024, 600, 390]) {
        await call('Emulation.setDeviceMetricsOverride', { width, height: 1100, deviceScaleFactor: 1, mobile: width < 768 });
        await sleep(150);
        const result = await evaluate(`(() => {
            const grid = document.querySelector('.retail-sidebar-permissions-grid');
            const wrapper = document.querySelector('[data-fieldname="retail_sidebar_permissions_html"]');
            return { columns: getComputedStyle(grid).gridTemplateColumns.split(' ').length,
                width: grid.getBoundingClientRect().width, available: wrapper.getBoundingClientRect().width,
                scrollWidth: grid.scrollWidth, groups: grid.children.length,
                checked: [...grid.querySelectorAll('input')].filter(input => input.checked).length };
        })()`);
        assert.equal(result.columns, width >= 1200 ? 5 : width >= 768 ? 3 : width >= 480 ? 2 : 1);
        assert(Math.abs(result.width - result.available) < 2, JSON.stringify(result));
        assert(result.scrollWidth <= result.width + 1, JSON.stringify(result));
        assert.equal(result.groups, 12);
        measurements.push({ viewport: width, ...result });
        if (width === 1600 || width === 390) {
            await evaluate('document.querySelector(".retail-sidebar-permissions-grid").scrollIntoView()');
            const screenshot = await call('Page.captureScreenshot', { format: 'png' });
            fs.writeFileSync(path.join(__dirname, 'sidebar_permissions_' + width + '.png'), Buffer.from(screenshot.data, 'base64'));
        }
    }
    await evaluate('document.querySelector(".retail-sidebar-permissions-editor .deselect-all").click()');
    assert.deepEqual(await evaluate('JSON.parse(cur_frm.doc.retail_sidebar_permissions).allowed'), []);
    await evaluate(`document.querySelector('input[data-unit="workspace:sales_invoices"]').click()`);
    assert.deepEqual(await evaluate('JSON.parse(cur_frm.doc.retail_sidebar_permissions).allowed'), ['workspace:sales', 'workspace:sales_invoices']);
    await evaluate('cur_frm.save()');
    await evaluate('cur_frm.reload_doc()');
    assert.deepEqual(await evaluate('JSON.parse(cur_frm.doc.retail_sidebar_permissions).allowed'), ['workspace:sales', 'workspace:sales_invoices']);
    await evaluate(`document.querySelector('input[data-unit="workspace:sales"]').click()`);
    assert.deepEqual(await evaluate('JSON.parse(cur_frm.doc.retail_sidebar_permissions).allowed'), []);
    await evaluate(`document.querySelector('input[data-unit="workspace:sales"]').click()`);
    assert.equal((await evaluate('JSON.parse(cur_frm.doc.retail_sidebar_permissions).allowed')).length, 7);
    await evaluate('document.querySelector(".retail-sidebar-permissions-editor .select-all").click()');
    assert.equal(await evaluate('JSON.parse(cur_frm.doc.retail_sidebar_permissions).allowed.length'), await evaluate('frappe.boot.retail_sidebar_registry.flatMap(group => [group,...group.children]).length'));
    await call('Page.navigate', { url: 'about:blank' });
    await wait('location.href === "about:blank"');
    await call('Network.clearBrowserCookies');
    await call('Network.setCookie', { name: 'sid', value: process.env.RETAIL_OPERATOR_SID, url: process.env.RETAIL_URL });
    await call('Emulation.setDeviceMetricsOverride', { width: 1600, height: 1100, deviceScaleFactor: 1, mobile: false });
    await call('Page.navigate', { url: process.env.RETAIL_URL + '/app/sales-invoice' });
    await wait('window.frappe?.session?.user === ' + JSON.stringify(process.env.RETAIL_USER) + ' && window.cur_list?.doctype === "Sales Invoice" && !!document.querySelector(".retail-persistent-sidebar")');
    await wait('!document.querySelector(".retail-persistent-sidebar").innerText.includes("Customers") && !document.querySelector(".retail-persistent-sidebar").innerText.includes("Business Home")');
    const sidebarText = await evaluate('document.querySelector(".retail-persistent-sidebar").innerText');
    assert(sidebarText.includes('Sales Invoices'), sidebarText);
    assert(!sidebarText.includes('Customers') && !sidebarText.includes('Business Home'), sidebarText);
    const requestOffset = failedRequests.length;
    await evaluate('frappe.new_doc("Sales Invoice")');
    await wait('window.cur_frm?.doctype === "Sales Invoice" && cur_frm.doc.__islocal');
    await sleep(1000);
    const formFailures = failedRequests.slice(requestOffset).filter(request => request.status === 403);
    assert.deepEqual(formFailures, [], JSON.stringify(formFailures));
    const deniedApi = await evaluate('fetch("/api/method/frappe.client.get_list?doctype=Customer").then(response => response.status)');
    assert.equal(deniedApi, 403);
    const deniedUrl = await evaluate('fetch("/app/customer").then(response => response.status)');
    assert.equal(deniedUrl, 403);
    const result = { measurements, checkbox_and_save_checks: 'passed', restricted_invoice_form: 'passed', restricted_sidebar: sidebarText,
        restricted_api_status: deniedApi, restricted_url_status: deniedUrl, runtime_errors: errors };
    fs.writeFileSync(path.join(__dirname, 'sidebar_permissions_browser_results.json'), JSON.stringify(result, null, 2) + '\n');
    console.log(JSON.stringify(result));
})().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => {
    socket?.close();
    const exited = new Promise(resolve => chrome.once('exit', resolve));
    chrome.kill('SIGTERM');
    await exited;
    await fs.promises.rm(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 });
});
