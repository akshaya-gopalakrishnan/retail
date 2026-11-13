const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
let handlers, reply;
const frappe = {ui:{form:{on:(dt,h)=>{if(dt === "Item") handlers=h},RetailQuickEntryForm:class{}}},call:()=>reply};
const ctx = {frappe,window:{frappe},__:v=>v};
vm.createContext(ctx);
for(const file of ['item.js','item_quick_entry.js']) vm.runInContext(fs.readFileSync(path.join(__dirname,'../public/js/forms',file),'utf8'),ctx);
(async()=>{
 for(const quick of [false,true]) {
  const values={custom_tax:'',custom_purchase_tax_template:'',custom_purchase_rate_includes_vat:0,custom_sales_rate_includes_vat:0,__islocal:1};
  const target=quick ? new frappe.ui.form.ItemQuickEntryForm() : {doc:values,is_new:()=>true,set_value:async(k,v)=>values[k]=v};
  if(quick) target.dialog={doc:values,fields_dict:{custom_tax:{},custom_purchase_tax_template:{},custom_purchase_rate_includes_vat:{},custom_sales_rate_includes_vat:{}},get_value:k=>values[k],set_value:async(k,v)=>values[k]=v};
  const run=()=>quick?target.apply_company_vat_defaults():handlers.onload(target);
  let resolve;reply=new Promise(r=>resolve=r);
  const pending=run(); values.custom_tax='Manually selected';
  resolve({message:{custom_tax:'Sales default',custom_purchase_tax_template:'',custom_purchase_rate_includes_vat:0,custom_sales_rate_includes_vat:1}});await pending;
  assert.equal(values.custom_purchase_rate_includes_vat,0);assert.equal(values.custom_sales_rate_includes_vat,1);
  values.custom_sales_rate_includes_vat=0;await run();assert.equal(values.custom_sales_rate_includes_vat,0);
  assert.equal(values.custom_tax,'Manually selected');assert.equal(values.custom_purchase_tax_template,'');
  reply=Promise.resolve({message:{custom_tax:'Replacement',custom_purchase_tax_template:'Replacement'}});await run();
  assert.equal(values.custom_purchase_tax_template,'');
  delete values.__retail_vat_defaults_applied;values.custom_tax='';await run();assert.equal(values.custom_tax,'Replacement');
 }
 const saved={doc:{custom_tax:'',custom_purchase_tax_template:''},is_new:()=>false};await handlers.onload(saved);assert.equal(saved.doc.custom_tax,'');
 console.log('PASS: full form and Quick Entry company defaults, blank purchase VAT, manual selection during fetch, no reapplication, existing Item unchanged');
})().catch(e=>{console.error(e);process.exitCode=1});
