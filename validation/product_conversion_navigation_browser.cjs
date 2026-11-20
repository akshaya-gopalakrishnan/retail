// Real Chromium validation; credentials come only from the temporary Python harness.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const WebSocket = require('../../frappe/node_modules/ws');
const assert = require('node:assert/strict');
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'product-conversion-chrome-'));
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
        const result = await call('Runtime.evaluate', {expression, awaitPromise: true, returnByValue: true}).catch(error=>{throw new Error(expression + ': ' + error.message)});
        if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
        return result.result.value;
    };
    const wait = async expression => {
        for (let i = 0; i < 100; i++) { if (await evaluate('Boolean(' + expression + ')')) return; await pause(300); }
        throw new Error('Timeout: ' + expression + '; ' + JSON.stringify(errors));
    };




    const base=process.env.RETAIL_URL;
    await call('Network.enable');await call('Runtime.enable');await call('Page.enable');
    await call('Network.setCookie',{name:'sid',value:process.env.RETAIL_SID,url:base});
    await call('Page.navigate',{url:base+'/app/product-conversion'});
    await wait('document.querySelector(\'.retail-persistent-sidebar [item-workspace-name="Product Conversion Link"] .fa-exchange\')');
    const placement = await evaluate(`(()=>{
        const entry=document.querySelector('.retail-persistent-sidebar [item-workspace-name="Product Conversion Link"]');
        return {previous:entry.previousElementSibling?.getAttribute('item-workspace-name')};
    })()`);
    assert.equal(placement.previous,'Stock Status');
    await call('Page.navigate',{url:base+'/app/user/Administrator'});
    await wait('window.cur_frm?.doctype === "User" && cur_frm.doc.name === "Administrator" && cur_frm.fields_dict.retail_sidebar_permissions_html?.$wrapper?.text().includes("Product Conversion")');
    const permission=await evaluate(`(()=>{
        const field=cur_frm.fields_dict.retail_sidebar_permissions_html;
        field.section.collapse(false);
        const label=field.$wrapper.find('label').filter(function(){return $(this).text().trim()==='Product Conversion';}).first();
        return {found:label.length===1,group:label.closest('.retail-sidebar-permissions-group').find('.retail-sidebar-permissions-heading').text().trim(),disabled:label.find('input').prop('disabled')};
    })()`);
    assert.equal(permission.found,true);assert.equal(permission.group,'Stocks');assert.equal(permission.disabled,false);
    console.log(JSON.stringify({icon:'fa-exchange',permission,browserErrors:errors}));
    assert.equal(errors.length,0);
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
    socket?.close();try{process.kill(-chrome.pid,'SIGTERM');}catch{}
    await pause(600);try{fs.rmSync(profile,{recursive:true,force:true,maxRetries:10,retryDelay:100});}catch{}
});
