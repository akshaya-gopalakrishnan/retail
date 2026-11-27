const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const handlers = {}, locals = {};
const flt = (v,p) => p === undefined ? Number(v)||0 : Number((Number(v)||0).toFixed(p));
const frappe = {ui:{form:{on(dt, events) { handlers[dt] ||= {}; for (const [key, fn] of Object.entries(events)) (handlers[dt][key] ||= []).push(fn); }}},
 meta:{get_docfield:()=>({precision:2}),has_field:()=>true},
 call:async ({args})=>({message:args.company==='NO-VAT' && !args.is_pos && args.parent_doctype==='Sales Invoice' ? 0 : 5}),
 model:{set_value:async (dt,name,key,value)=>{locals[dt][name][key]=value;}}};
const window = {frappe};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../public/js/forms/transaction_items.js'),'utf8'),
 {window,frappe,locals,flt,cint:flt,setTimeout:()=>1,clearTimeout(){},__:s=>s});
(async()=>{
 for (const [dt,company,pos,expected] of [['Sales Invoice','NO-VAT',0,4],['Sales Invoice','VAT',0,4.2],['Sales Invoice','NO-VAT',1,4.2],['Purchase Invoice','NO-VAT',0,4.2]]) {
  const child=dt+' Item';
  const row={doctype:child,name:'ROW',item_code:'ITEM',rate:4,qty:1,amount:4,custom_rate_including_vat:4,custom_vat_amount:0,item_tax_template:'5%',tax_rate:5};
  locals[child]={ROW:row};
  const frm={doc:{doctype:dt,company,is_pos:pos,docstatus:0,items:[row]},fields_dict:{}};
  await window.retail.transaction_items.refreshVatDisplays(frm);
  assert.equal(row.custom_rate_including_vat,expected,dt+company+pos);
  assert.equal(row.custom_vat_amount,flt(expected-4,2));
  if (dt==='Sales Invoice' && company==='NO-VAT' && !pos) {
   row.custom_rate_including_vat=8;
   for (const fn of handlers[child].custom_rate_including_vat) await fn(frm,child,'ROW');
   for(let i=0;i<40;i++) await Promise.resolve();
   assert.equal(row.rate,8); assert.equal(row.custom_vat_amount,0);
   row.qty=3;
   for (const fn of handlers[child].qty) await fn(frm,child,'ROW');
   for(let i=0;i<40;i++) await Promise.resolve();
   assert.equal(row.custom_amount_including_vat,24);
  }
 }
 console.log('Trading VAT client: company override, inclusive edits, quantities, POS and purchase exclusions passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
