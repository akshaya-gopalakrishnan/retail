const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
function fixture() {
    let dialog; const events = {};
    const window = {retail:{}};
    const existing = {doctype:'Sales Invoice Item',name:'first',idx:1,item_code:'A',item_name:'Apple',qty:3,uom:'Nos',rate:5};
    const duplicate = {...existing,name:'second',idx:2,qty:1};
    const frm = {doc:{doctype:'Sales Invoice',docstatus:0,items:[existing,duplicate]},script_manager:{async trigger(){}},dirty(){},refresh_field(){}};
    const updates=[];
    const frappe={ui:{form:{on(){}},Dialog:class {
        constructor(options){this.options=options;this.$wrapper={on(event, fn){events[event]=fn;}};dialog=this;}
        show(){} hide(){this.on_hide?.();} disable_primary_action(){} enable_primary_action(){}
    }},utils:{escape_html:s=>s},msgprint(){},model:{async set_value(dt,name,field,value){updates.push([name,field,value]);existing[field]=value;},clear_doc(){}}};
    vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../public/js/forms/sales_invoice_duplicates.js'),'utf8'),{window,frappe,__:s=>s});
    return {events,api:window.retail.sales_invoice_duplicates,frm,existing,duplicate,updates,get dialog(){return dialog;}};
}
test('accept adds entered quantity to original and removes duplicate through native events',async()=>{
    const f=fixture();assert.equal(f.api.offer(f.frm,f.existing,f.duplicate),true);
    await f.dialog.options.primary_action({qty:4});
    assert.equal(f.existing.qty,7);assert.equal(f.frm.doc.items.length,1);
    assert.deepEqual(f.updates,[['first','qty',7]]);
});
test('invalid quantity and changed packing do not apply an update',async()=>{
    const f=fixture();f.api.offer(f.frm,f.existing,f.duplicate);
    await f.dialog.options.primary_action({qty:0});assert.equal(f.updates.length,0);
    f.duplicate.uom='Box';await f.dialog.options.primary_action({qty:2});
    assert.equal(f.updates.length,0);assert.equal(f.frm.doc.items.length,2);
});
test('different pricing, mapped lines, returns and submitted invoices stay separate',()=>{
    const f=fixture();
    assert.equal(f.api.same(f.existing,f.duplicate),true);
    for(const changes of [{rate:6},{custom_packing_detail:'PACK'},{delivery_note:'DN'},{serial_no:'SERIAL'}])
        assert.equal(f.api.same(f.existing,{...f.duplicate,...changes}),false);
    f.frm.doc.is_return=1;assert.equal(f.api.offer(f.frm,f.existing),false);
    f.frm.doc.is_return=0;f.frm.doc.docstatus=1;assert.equal(f.api.offer(f.frm,f.existing),false);
});

test('closing without accepting removes only the new row and keeps original quantity',async()=>{
    const f=fixture();f.api.offer(f.frm,f.existing,f.duplicate);
    f.dialog.hide();await new Promise(resolve=>setImmediate(resolve));
    assert.equal(f.existing.qty,3);assert.equal(f.frm.doc.items.length,1);
    assert.equal(f.updates.length,0);
});
test('packing preflight opens immediately for an unpriced blank row and cancel deletes it',async()=>{
    const f=fixture();Object.assign(f.duplicate,{item_code:'',item_name:'',rate:0,uom:''});
    assert.equal(f.api.preflight(f.frm,f.duplicate,{item_code:'A',uom:'Nos',packing_id:''}),true);
    assert.equal(f.updates.length,0,'No item or pricing writes before popup');
    f.dialog.hide();await new Promise(resolve=>setImmediate(resolve));
    assert.equal(f.frm.doc.items.length,1);assert.equal(f.existing.qty,3);
});
test('packing preflight acceptance adds quantity without pricing a duplicate',async()=>{
    const f=fixture();Object.assign(f.duplicate,{item_code:'',item_name:'',rate:0,uom:''});
    f.api.preflight(f.frm,f.duplicate,{item_code:'A',uom:'Nos',packing_id:''});
    await f.dialog.options.primary_action({qty:2});
    assert.equal(f.existing.qty,5);assert.equal(f.frm.doc.items.length,1);
});

test('cross-button on_hide removes duplicate even when late pricing changes its values',async()=>{
    const f=fixture();f.api.offer(f.frm,f.existing,f.duplicate);
    f.duplicate.rate=9;f.duplicate.item_tax_template='NEW VAT';
    // Frappe invokes on_hide on hide.bs.modal, including the close button.
    f.dialog.on_hide();await f.dialog.__retail_cleanup;
    assert.equal(f.frm.doc.items.length,1);assert.equal(f.existing.qty,3);
    assert.equal(f.frm.__retail_duplicate_dialog,undefined);
});
test('cross-button cancellation after blank preflight remains valid when item fields finish filling',async()=>{
    const f=fixture();Object.assign(f.duplicate,{item_code:'',item_name:'',rate:0,uom:''});
    f.api.preflight(f.frm,f.duplicate,{item_code:'A',uom:'Nos',packing_id:''});
    Object.assign(f.duplicate,{item_code:'A',rate:5,uom:'Nos'});
    f.dialog.on_hide();await f.dialog.__retail_cleanup;
    assert.equal(f.frm.doc.items.length,1);assert.equal(f.existing.qty,3);
});

test('preflight quantity update succeeds after pending Item fields finish filling',async()=>{
    const f=fixture();Object.assign(f.duplicate,{item_code:'',item_name:'',rate:0,uom:''});
    f.api.preflight(f.frm,f.duplicate,{item_code:'A',uom:'Nos',packing_id:''});
    Object.assign(f.duplicate,{item_code:'A',item_name:'Apple',rate:5,uom:'Nos'});
    await f.dialog.options.primary_action({qty:4});
    assert.equal(f.existing.qty,7);assert.equal(f.frm.doc.items.length,1);
});
test('negative change decreases existing quantity through native quantity setter',async()=>{
    const f=fixture();f.api.offer(f.frm,f.existing,f.duplicate);
    await f.dialog.options.primary_action({qty:-2});
    assert.equal(f.existing.qty,1);assert.equal(f.frm.doc.items.length,1);
    assert.deepEqual(f.updates,[['first','qty',1]]);
});
test('zero, non-finite or excessive subtraction never deletes or changes a row',async()=>{
    for (const qty of [0,NaN,Infinity,-3,-8]) {
        const f=fixture();f.api.offer(f.frm,f.existing,f.duplicate);
        await f.dialog.options.primary_action({qty});
        assert.equal(f.existing.qty,3);assert.equal(f.frm.doc.items.length,2);
    }
});
test('late pricing changes do not silently reject an otherwise matching quantity update',async()=>{
    const f=fixture();f.api.offer(f.frm,f.existing,f.duplicate);
    f.duplicate.rate=9;f.duplicate.item_tax_template='VAT';
    await f.dialog.options.primary_action({qty:2});
    assert.equal(f.existing.qty,5);assert.equal(f.frm.doc.items.length,1);
});
