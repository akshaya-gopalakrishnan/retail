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
    await call('Emulation.setDeviceMetricsOverride',{width:1600,height:1200,deviceScaleFactor:1,mobile:false});
    await call('Page.navigate',{url:base+'/app/product-conversion/new-product-conversion-layout'});
    await wait('window.cur_frm?.doc?.doctype === "Product Conversion" && cur_frm.doc.source_warehouse && cur_frm.fields_dict.items.grid.__retail_scroll_options');
    await evaluate('new Promise(resolve=>frappe.after_ajax(()=>setTimeout(resolve,400)))');
    const sections=await evaluate(`(()=>{
        const result={};for(const name of ['staff_section','costs_section']){
            const section=cur_frm.layout.sections_dict[name];
            const initial=section.is_collapsed();section.head.trigger('click');
            const opened=!section.is_collapsed();cur_frm.refresh_fields();
            const retained=!section.is_collapsed();section.head.trigger('click');
            result[name]={initial,opened,retained,closed:section.is_collapsed()};
        }return result;
    })()`);
    for(const state of Object.values(sections))assert.deepEqual(state,{initial:true,opened:true,retained:true,closed:true});
    const notes=await evaluate(`(()=>{
        const input=cur_frm.fields_dict.remarks.$input[0];
        input.scrollIntoView({block:'center'});
        const initial=input.getBoundingClientRect().height;
        input.value=Array.from({length:12},(_,i)=>'Remark line '+(i+1)).join('\\n');
        input.dispatchEvent(new Event('input',{bubbles:true}));
        const grown=input.getBoundingClientRect().height;
        input.value='';input.dispatchEvent(new Event('input',{bubbles:true}));
        return {initial,grown,cleared:input.getBoundingClientRect().height,resize:input.style.resize};
    })()`);
    assert.ok(notes.initial<=50,JSON.stringify(notes));assert.ok(notes.grown>notes.initial+100,JSON.stringify(notes));assert.ok(notes.cleared<=50);assert.equal(notes.resize,'vertical');
    // Capture the existing save API payload without changing the user's real layout.
    await evaluate(`(()=>{
        window.__pcLayoutSaves=[];
        frappe.model.user_settings.save=async(doctype,key,value)=>{
            window.__pcLayoutSaves.push({doctype,key,value:JSON.parse(JSON.stringify(value))});
            const settings=frappe.model.user_settings[doctype]||{};
            settings[key]={...(settings[key]||{}),...value};
            return {message:settings};
        };
        const grid=cur_frm.fields_dict.items.grid;
        grid.wrapper[0].scrollIntoView({block:'center'});
        window.__pcOriginalColumns=grid.visible_columns.map(([df])=>df.fieldname);
    })()`);
    const first=await evaluate(`(()=>{
        const grid=cur_frm.fields_dict.items.grid;const name=window.__pcOriginalColumns[0];
        const cell=Array.from(grid.header_row.row[0].children).find(n=>n.dataset.fieldname===name);
        const rect=cell.querySelector('.retail-grid-resize-handle').getBoundingClientRect();
        return {name,width:cell.getBoundingClientRect().width,x:rect.x+rect.width/2,y:rect.y+rect.height/2};
    })()`);
    await call('Input.dispatchMouseEvent',{type:'mouseMoved',x:first.x,y:first.y});
    await call('Input.dispatchMouseEvent',{type:'mousePressed',x:first.x,y:first.y,button:'left',buttons:1,clickCount:1});
    await call('Input.dispatchMouseEvent',{type:'mouseMoved',x:first.x+48,y:first.y,button:'left',buttons:1});
    await call('Input.dispatchMouseEvent',{type:'mouseReleased',x:first.x+48,y:first.y,button:'left',buttons:0,clickCount:1});
    await wait('window.__pcLayoutSaves.length===1');
    const resized=await evaluate(`window.__pcLayoutSaves[0].value.items.find(r=>r.fieldname===window.__pcOriginalColumns[0]).width_px`);
    assert.ok(resized>=first.width+40,JSON.stringify({first,resized}));
    await evaluate(`(()=>{
        const grid=cur_frm.fields_dict.items.grid;const cells=Array.from(grid.header_row.row[0].children).filter(n=>n.dataset.fieldname);
        const from=cells.find(n=>n.dataset.fieldname===window.__pcOriginalColumns[0]);
        const to=cells.find(n=>n.dataset.fieldname===window.__pcOriginalColumns[1]);
        const dataTransfer=new DataTransfer();
        from.dispatchEvent(new DragEvent('dragstart',{bubbles:true,cancelable:true,dataTransfer}));
        to.dispatchEvent(new DragEvent('dragover',{bubbles:true,cancelable:true,dataTransfer}));
        to.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer}));
    })()`);
    await wait('window.__pcLayoutSaves.length===2 && cur_frm.fields_dict.items.grid.visible_columns[0][0].fieldname===window.__pcOriginalColumns[1]');
    const layout=await evaluate(`(()=>{
        const grid=cur_frm.fields_dict.items.grid;grid.refresh();
        return {order:grid.visible_columns.map(([df])=>df.fieldname),saved:frappe.get_user_settings('Product Conversion','RetailScrollableGrid').items,
            resizeHandles:grid.header_row.row[0].querySelectorAll('.retail-grid-resize-handle').length,
            titleMode:grid.__retail_scroll_options.item_code_as_title};
    })()`);
    assert.equal(layout.order[1],first.name);assert.equal(layout.saved.find(r=>r.fieldname===first.name).width_px,resized);assert.equal(layout.titleMode,true);
    assert.equal(errors.length,0,JSON.stringify(errors));
    fs.writeFileSync('/tmp/product-conversion-layout.png',Buffer.from((await call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    console.log(JSON.stringify({sections,notes,columnResize:{field:first.name,before:first.width,after:resized},columnOrder:layout.order,resizeHandles:layout.resizeHandles,realUserPreferencesChanged:false,browserErrors:errors.length}));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
    socket?.close();try{process.kill(-chrome.pid,'SIGTERM');}catch{}
    await pause(600);try{fs.rmSync(profile,{recursive:true,force:true,maxRetries:10,retryDelay:100});}catch{}
});
