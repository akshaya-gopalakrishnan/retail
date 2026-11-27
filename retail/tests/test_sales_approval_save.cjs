const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let hooks, dialog, opened = 0, eventHandler, unapproved = true, holdLookup = false, releaseLookup;
const frm = {doc:{docstatus:0}, wrapper:{}, is_new:()=>false};
class Dialog {
    constructor(options) { Object.assign(this, options); dialog=this; }
    show() { opened++; }
    hide() { this.onhide(); }
    set_value() {}
    disable_primary_action() {}
    enable_primary_action() {}
}
const frappe = {
    ui:{Dialog, form:{on:(_dt, handlers)=>{hooks=handlers;}}},
    after_ajax:async()=>{}, show_alert:()=>{},
    call:async args => {
        if (args.method.endsWith('.authorize')) { unapproved=false; return {message:'approved-token'}; }
        if (holdLookup) { holdLookup=false; return new Promise(resolve=>{releaseLookup=resolve;}); }
        return {message:unapproved || !args.args.doc._retail_sales_approval?.length};
    },
};
vm.runInNewContext(fs.readFileSync('apps/retail/retail/public/js/forms/backend_sales_admin.js','utf8'), {
    frappe, __:s=>s, setTimeout, clearTimeout, console,
    $:()=>({off(){return this;},on(_event,_selector,handler){eventHandler=handler;return this;}}),
});
const settle=()=>new Promise(resolve=>setTimeout(resolve,200));
(async()=>{
    hooks.refresh(frm);
    eventHandler.call({dataset:{fieldname:'rate'}},{originalEvent:{}});
    await settle();
    assert.equal(opened,1);
    await dialog.primary_action({user:'manager@example.com',password:'test-only'});
    await settle();
    // Blurring the formatted rate editor on Save can emit another DOM change.
    eventHandler.call({dataset:{fieldname:'rate'}},{originalEvent:{}});
    await settle();
    assert.equal(opened,1,'An unchanged approved value must not prompt on blur');
    // Frappe replaces the document after Save; retained approvals must be restored.
    delete frm.doc._retail_sales_approval;
    unapproved=true; // Save must not run a second whole-document approval lookup.
    await hooks.before_save(frm);
    await hooks.before_submit(frm);
    assert.equal(opened,1,'Save and Submit must reuse completed approval');
    unapproved=true;
    eventHandler.call({dataset:{fieldname:'rate'},value:'1'},{originalEvent:{}});
    frm.doc.rate=1; // Native model update can happen after the DOM event bubbles.
    await settle();
    dialog.hide();
    await settle();
    const save=hooks.before_save(frm);
    await settle();
    assert.equal(opened,3,'Save must ask when the changed price was not approved');
    await dialog.primary_action({user:'manager@example.com',password:'test-only'});
    await save;
    assert.equal(opened,3);
    const secondForm={doc:{docstatus:0,rate:0},wrapper:{},is_new:()=>false};
    hooks.refresh(secondForm);
    holdLookup=true;
    unapproved=true;
    const olderSaveCheck=hooks.before_save(secondForm);
    await settle();
    secondForm.doc.rate=2;
    eventHandler.call({dataset:{fieldname:'rate'}},{originalEvent:{}});
    await settle();
    const beforeApproval=opened;
    await dialog.primary_action({user:'manager@example.com',password:'test-only'});
    releaseLookup({message:true});
    await olderSaveCheck;
    assert.equal(opened,beforeApproval,'An older response must not reopen a completed approval');
    console.log('PASS approved Save/Submit reuse approval; cancelled edits ask; late responses do not reopen popup');
})().catch(error=>{console.error(error);process.exitCode=1;});
