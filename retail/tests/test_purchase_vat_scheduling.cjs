const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

for (const doctype of ['Purchase Receipt', 'Purchase Invoice']) {
 test(doctype + ': coalesce VAT refreshes behind native requests and invalidate them on flush', async () => {
  const handlers = {}, timers = [], requests = [], waiting = [];
  let calculations = 0;
  const frappe = {ui:{form:{on(dt, events){handlers[dt] = {...handlers[dt], ...events};}}},
   after_ajax:()=>new Promise(resolve=>waiting.push(resolve)),
   call:async request=>{requests.push(request);return {message:{tax_rows:[],item_tax_rates:{}}};}};
  const window = {frappe};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../public/js/forms/transaction_items.js'),'utf8'),
   {window,frappe,locals:{},cint:Number,flt:Number,setTimeout:fn=>{timers.push(fn);return fn;},clearTimeout(){},__:s=>s});
  const frm = {doctype,doc:{doctype,docstatus:0,items:[],taxes:[]},fields_dict:{taxes:{}},refresh_field(){},
   cscript:{async calculate_taxes_and_totals(){calculations++;}}};
  const queue = ()=>handlers[doctype+' Item'].rate(frm,doctype+' Item','missing');
  queue();
  const stale = timers.pop()();
  assert.equal(requests.length,0,'VAT must wait while native requests run');
  queue();
  const current = timers.pop()();
  waiting.splice(0).forEach(resolve=>resolve());
  await Promise.all([stale,current]);
  assert.equal(requests.length,1,'Only the latest queued snapshot is sent');
  assert.equal(calculations,1,'Native totals still run');
  queue();
  const beforeSave = timers.pop()();
  await window.retail.transaction_items.flushVatTaxRows(frm);
  waiting.splice(0).forEach(resolve=>resolve());
  await beforeSave;
  assert.equal(requests.length,2,'Explicit flush supplies final VAT without a duplicate queued request');
  assert.equal(calculations,2);
 });
}
