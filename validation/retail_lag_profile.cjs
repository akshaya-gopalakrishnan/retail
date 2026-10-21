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
    const requests = new Map();
    const blocked = [];
    const failedRequests = [];
    socket.on('message', bytes => {
        const message = JSON.parse(bytes);
        if (message.id) {
            const callback = pending.get(message.id);
            pending.delete(message.id);
            if (message.error) callback.reject(new Error(JSON.stringify(message.error)));
            else callback.resolve(message.result);
        }
        if (message.method === 'Network.requestWillBeSent') {
            const p = message.params;
            requests.set(p.requestId, {url:p.request.url,start:p.timestamp,type:p.type});
        }
        if (message.method === 'Network.loadingFinished') {
            const p=message.params, row=requests.get(p.requestId);
            if(row) Object.assign(row,{ms:Math.round((p.timestamp-row.start)*1000),bytes:p.encodedDataLength});
        }
        if (message.method === 'Fetch.requestPaused') {
            const p=message.params, url=new URL(p.request.url), endpoint=url.pathname.split('/').pop().split('.').pop();
            const reads=new Set(['get_customer_credit_balances','get_stock_margin_cost','get_item_tax_rate','get_dimensions','get_round_off_applicable_accounts','get_rounding_tax_settings','get_enable_stock_uom_editing','get_transaction_item_vat_rate','doc_has_references','get_comparisons','get_list_settings','get_sales_trend_7_days','get_top_selling_products','get_sales_by_counter','get_config','get_workspace_sidebar_items','get_desktop_page','getdoctype','getdoc','get_list','get_count','get','get_value','get_values','get_events','get_open_count','get_unread_notifications','get_notifications','get_sidebar_stats','get_data','get_chart_data','get_dashboard_chart','get_number_card','get_business_home_profit_cards','get_low_stock_items_count','get_out_of_stock_items_count','get_damage_amount_today','get_cash_in_hand_today','get_today_sales','get_profit_number_card','get_invoice_count_today','get_return_amount_today','get_user_info','get_user_theme','get_notification_logs','get_bootinfo','can_subscribe_doc','run','get_report_doc','get_script','getpage','get_linked_doctypes','get_permission_query_conditions','get_filter_dashboard_data','get_global_search_settings','get_user_permissions']);
            if(reads.has(endpoint)) call('Fetch.continueRequest',{requestId:p.requestId}).catch(()=>{});
            else {blocked.push(endpoint);call('Fetch.fulfillRequest',{requestId:p.requestId,responseCode:200,responseHeaders:[{name:'Content-Type',value:'application/json'}],body:Buffer.from('{"message":null}').toString('base64')}).catch(()=>{});}
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
        for (let i = 0; i < 60; i++) {
            if (await evaluate(expression)) return;
            await sleep(250);
        }
        const state = await evaluate('({ route: window.frappe?.get_route?.(), user: window.frappe?.session?.user, selection: window.frappe?.boot?.retail_sidebar_selection, allowed: window.frappe?.boot?.allowed_workspaces?.map(page => page.name), list: window.cur_list?.doctype })');
        fs.writeFileSync('/tmp/retail-lag-diagnostic.json',JSON.stringify({blocked:[...new Set(blocked)],requests:[...requests.values()].filter(r=>r.url.startsWith("http")),dom:await evaluate('({cards:document.querySelectorAll(".number-widget-box .number").length,charts:document.querySelectorAll(".chart-container svg").length,html:document.querySelector(".layout-main-section")?.innerText})')},null,2));
        throw new Error('Timed out waiting for ' + expression + ' ' + JSON.stringify({ state, failedRequests, errors }));
    };
    await call('Runtime.enable');
    await call('Page.enable');
    await call('Network.enable');
    await call('Network.setCacheDisabled', { cacheDisabled: true });
    await call('Network.setCookie', { name: 'sid', value: process.env.RETAIL_SID, url: process.env.RETAIL_URL });
    await call('Emulation.setDeviceMetricsOverride', { width: 1600, height: 1100, deviceScaleFactor: 1, mobile: false });
    await call('Fetch.enable', {patterns:[{urlPattern:'*/api/*',requestStage:'Request'}]});
    await call('Page.addScriptToEvaluateOnNewDocument', {source:`window.__lag={long:[],lcp:[]};new MutationObserver(()=>{if(!window.__lag.cards && document.querySelectorAll('.number-widget-box .number').length>=8)window.__lag.cards=performance.now();if(!window.__lag.charts && document.querySelectorAll('.chart-container svg').length>=3)window.__lag.charts=performance.now()}).observe(document,{childList:true,subtree:true}); new PerformanceObserver(l=>window.__lag.long.push(...l.getEntries().map(e=>({start:e.startTime,duration:e.duration})))).observe({type:'longtask',buffered:true});new PerformanceObserver(l=>window.__lag.lcp.push(...l.getEntries().map(e=>({start:e.startTime,element:e.element?.id})))).observe({type:'largest-contentful-paint',buffered:true});`});
    if(process.env.RETAIL_LAG_BASELINE==='1') await call('Page.addScriptToEvaluateOnNewDocument',{source:`document.addEventListener('DOMContentLoaded',()=>{if(!window.frappe)return;delete frappe.boot?.retail_workspace_sidebar_access;const original=frappe.call;frappe.call=function(...args){return original.apply(this,args).then(r=>{if((typeof args[0]==='string'?args[0]:args[0]?.method)==='frappe.desk.desktop.get_desktop_page'&&r?.message)delete r.message.retail_chart_source_configs;return r})}})`});
    const results=[];
    for(let round=0;round<2;round++) {
        requests.clear();errors.length=0;
        await call('Page.navigate',{url:process.env.RETAIL_URL+'/app/business-home'});
        await wait('window.frappe?.workspace?.editor && document.querySelectorAll(".number-widget-box .number").length >= 8 && document.querySelectorAll(".chart-container svg").length >= 3');
        await sleep(700);
        results.push({route:'business-home',round,metrics:await evaluate('({now:performance.now(),lag:window.__lag,bootSidebar:!!frappe.boot.retail_workspace_sidebar_access,numbers:Array.from(document.querySelectorAll(".number-widget-box .number")).map(n=>n.textContent),nav:performance.getEntriesByType("navigation").map(e=>({ttfb:e.responseStart,dom:e.domContentLoadedEventEnd}))})'),requests:[...requests.values()].filter(r=>r.url.startsWith("http")).sort((a,b)=>(b.ms||0)-(a.ms||0)),errors:[...errors],blocked:[...new Set(blocked)]});
        console.log(JSON.stringify({route:'business-home',round,metrics:results.at(-1).metrics,apis:results.at(-1).requests.filter(r=>r.url.includes('/api/')).map(r=>({url:r.url.split('?')[0],ms:r.ms})),errors:[...errors]}));
    }
    for(const route of ['item','customer','sales-invoice','purchase-invoice','stock-entry']) {
        requests.clear();errors.length=0;const start=await evaluate('performance.now()');
        await evaluate('frappe.set_route('+JSON.stringify(route)+')');
        await wait('window.cur_list?.doctype === '+JSON.stringify({'item':'Item','customer':'Customer','sales-invoice':'Sales Invoice','purchase-invoice':'Purchase Invoice','stock-entry':'Stock Entry'}[route])+' && !!document.querySelector(".list-row-container")');
        await sleep(250);
        const row={route,ready_ms:Math.round(await evaluate('performance.now()')-start),requests:[...requests.values()].filter(r=>r.url.startsWith("http")),errors:[...errors]};results.push(row);console.log(JSON.stringify({route,ready_ms:row.ready_ms,errors:row.errors}));
    }
    if(process.env.RETAIL_LAG_BASELINE!=='1') for(const [doctype,name] of JSON.parse(process.env.RETAIL_LAG_FORMS||'[]')) {
        requests.clear();errors.length=0;const start=await evaluate('performance.now()');
        await evaluate('frappe.set_route("Form",'+JSON.stringify(doctype)+','+JSON.stringify(name)+')');
        await wait('window.cur_frm?.doc?.name === '+JSON.stringify(name)+' && window.cur_frm?.doc?.doctype === '+JSON.stringify(doctype)+' && !window.cur_frm?.__isloading');
        await sleep(500);
        const row={route:'Form '+doctype,ready_ms:Math.round(await evaluate('performance.now()')-start),requests:[...requests.values()].filter(r=>r.url.startsWith('http')),errors:[...errors],blocked:[...new Set(blocked)]};results.push(row);console.log(JSON.stringify({route:row.route,ready_ms:row.ready_ms,errors:row.errors,blocked:row.blocked}));
    }
    for(const row of results) for(const request of row.requests){const u=new URL(request.url);if(u.searchParams.has('sid'))u.searchParams.set('sid','REDACTED');request.url=u.toString()}
    fs.writeFileSync(process.env.RETAIL_LAG_OUTPUT||'/tmp/retail-lag-before.json',JSON.stringify(results,null,2));
})().catch(error=>{console.error(error);process.exitCode=1}).finally(()=>{socket?.close();chrome.kill();try{fs.rmSync(profile,{recursive:true,force:true,maxRetries:5,retryDelay:100})}catch{};});
