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


    const enabled=process.env.RETAIL_TEST_AWESOME_BAR!=='0';
    await call('Page.navigate',{url:process.env.RETAIL_URL+'/app/user/'+process.env.RETAIL_USER});
    await wait('window.cur_frm?.doc?.name === '+JSON.stringify(process.env.RETAIL_USER)+' && !!document.querySelector(".retail-sidebar-permissions-grid")');
    assert.equal(await evaluate('frappe.boot.retail_awesome_bar_allowed'),enabled);
    const visibility=await evaluate(`(() => {
        const input=document.getElementById('navbar-search');
        const wrapper=input.closest('.search-bar');
        return {visible:!!wrapper.getClientRects().length,disabled:input.disabled};
    })()`);
    assert.equal(visibility.visible,enabled,JSON.stringify(visibility));
    if (!enabled) assert.equal(visibility.disabled,true);
    await evaluate('document.activeElement?.blur()');
    await call('Input.dispatchKeyEvent',{type:'keyDown',key:'g',code:'KeyG',modifiers:2,windowsVirtualKeyCode:71,nativeVirtualKeyCode:71});
    await call('Input.dispatchKeyEvent',{type:'keyUp',key:'g',code:'KeyG',modifiers:2,windowsVirtualKeyCode:71,nativeVirtualKeyCode:71});
    await sleep(200);
    assert.equal(await evaluate('document.activeElement?.id === "navbar-search"'),enabled);
    if (process.env.RETAIL_USER==='Administrator') {
        await evaluate('cur_frm.layout.tabs.find(tab=>tab.df.fieldname==="roles_permissions_tab").set_active()');
        await evaluate(`(() => {
            const box=document.querySelector('.retail-sidebar-permissions-grid input[data-unit="control:awesome_bar"]');
            if (!box || box.disabled) throw new Error('Missing/edit-disabled Awesome Bar checkbox');
            if (box.checked) box.click();
            return true;
        })()`);
        assert.equal(await evaluate('JSON.parse(cur_frm.doc.retail_sidebar_permissions).allowed.includes("control:awesome_bar")'),false);
        await evaluate('document.querySelector(\'.retail-sidebar-permissions-grid input[data-unit="control:awesome_bar"]\').click()');
        assert.equal(await evaluate('JSON.parse(cur_frm.doc.retail_sidebar_permissions).allowed.includes("control:awesome_bar")'),true);
    }
    const result={user:process.env.RETAIL_USER,awesome_bar_enabled:enabled,visibility,ctrl_g:enabled?'focuses search':'cannot focus hidden search',editor_checkbox:process.env.RETAIL_USER==='Administrator'?'toggle verified without saving':'not edited',runtime_errors:errors};
    fs.writeFileSync(path.join(__dirname,'awesome_bar_browser_'+(enabled?'shown':'hidden')+'_results.json'),JSON.stringify(result,null,2)+'\n');
    console.log(JSON.stringify(result));
})().catch(error=>{console.error(error);process.exitCode=1}).finally(async()=>{
    socket?.close();
    const exited=new Promise(resolve=>chrome.once('exit',resolve));chrome.kill('SIGTERM');await exited;
    await fs.promises.rm(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});
});
