const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function fixture() {
 const meta = JSON.parse(fs.readFileSync(path.join(__dirname,'../../../erpnext/erpnext/stock/doctype/batch/batch.json')));
 for(const df of meta.fields) if(['manufacturing_date','expiry_date','stock_uom'].includes(df.fieldname)) df.allow_in_quick_entry=1;
 const frappe={provide(){},ui:{form:{}},get_meta:()=>meta};
 const context=vm.createContext({frappe});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../../../frappe/frappe/public/js/frappe/form/quick_entry.js'),'utf8'),context);
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../public/js/forms/batch_quick_entry.js'),'utf8'),context);
 const form=new frappe.ui.form.BatchQuickEntryForm('Batch');
 return {frappe,form,meta};
}

test('native quick entry includes editable dates and read-only derived fields without changing metadata',()=>{
 const {form,meta}=fixture();
 const before=JSON.stringify(meta);
 form.set_meta_and_mandatory_fields();
 const fields=Object.fromEntries(form.mandatory.map(df=>[df.fieldname,df]));
 assert.ok(fields.manufacturing_date);assert.ok(fields.expiry_date);
 assert.ok(!fields.manufacturing_date.read_only);assert.ok(!fields.expiry_date.read_only);
 assert.equal(fields.stock_uom.read_only,1);assert.equal(fields.use_batchwise_valuation,undefined);
 assert.equal(JSON.stringify(meta),before);
});

test('derived values follow selected item and stale responses cannot replace them',async()=>{
 const {form,frappe}=fixture();let item='old';const values={};const pending={};
 form.dialog={fields_dict:{stock_uom:{}},get_value:()=>item,set_value:async(k,v)=>{values[k]=v;}};
 frappe.call=({args})=>new Promise(resolve=>{pending[args.item]=resolve;});
 const first=form.update_item_defaults();await new Promise(setImmediate);
 item='new';const second=form.update_item_defaults();await new Promise(setImmediate);
 pending.new({message:{stock_uom:'Box'}});await second;
 pending.old({message:{stock_uom:'Nos'}});await first;
 assert.deepEqual(values,{stock_uom:'Box'});
 item='';await form.update_item_defaults();
 assert.deepEqual(values,{stock_uom:null});
});
