const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

test('purchase reads share pending identical inputs, refresh after completion, and retry failures', async () => {
 const handlers = {}, calls = [];
 const frappe = {ui:{form:{on(dt, events){handlers[dt]=events;}}},
  call(request){return new Promise((resolve,reject)=>calls.push({request,resolve,reject}));}};
 const window = {frappe};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../public/js/forms/transaction_items.js'),'utf8'),
  {window,frappe,locals:{},cint:Number,flt:Number,setTimeout,clearTimeout,__:s=>s});
 const read=window.retail.transaction_items.purchaseRead;
 const frm={doc:{doctype:'Purchase Invoice'}};
 const request={method:'vat',args:{item_code:'A',item_tax_template:'VAT5'}};
 const first=read(frm,request), duplicate=read(frm,{method:'vat',args:{item_tax_template:'VAT5',item_code:'A'}});
 assert.equal(first,duplicate);
 const different=read(frm,{method:'vat',args:{item_code:'A',item_tax_template:'VAT0'}});
 await Promise.resolve();
 assert.equal(calls.length,2,'Different tax contexts must never share reads');
 calls[0].resolve({message:5});calls[1].resolve({message:0});
 assert.equal((await first).message,5);assert.equal((await different).message,0);
 const failed=read(frm,request);await Promise.resolve();
 assert.equal(calls.length,3,'Settled responses must not become stale caches');
 const rejection=assert.rejects(failed,/offline/);calls[2].reject(new Error('offline'));await rejection;
 const retry=read(frm,request);await Promise.resolve();calls[3].resolve({message:7});
 assert.equal((await retry).message,7);
});

for (const doctype of ['Purchase Receipt', 'Purchase Invoice']) {
 test(doctype + ': VAT summary waits for native actions and Quick Entry, while explicit flush still works', async () => {
  const handlers={}, timers=[], calls=[];
  const frappe={ui:{form:{on(dt,events){handlers[dt]={...handlers[dt],...events};}}},after_ajax:async()=>{},
   async call(request){calls.push(request);return {message:{tax_rows:[],item_tax_rates:{}}};}};
  const window={frappe};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../public/js/forms/transaction_items.js'),'utf8'),
   {window,frappe,locals:{},cint:Number,flt:Number,setTimeout:fn=>{timers.push(fn);return fn;},clearTimeout(){},__:s=>s});
  const frm={doc:{doctype,docstatus:0,items:[],taxes:[]},fields_dict:{taxes:{}},refresh_field(){},
   cscript:{async calculate_taxes_and_totals(){}},__retail_purchase_action:{active:1}};
  handlers[doctype+' Item'].rate(frm,doctype+' Item','missing');
  await timers.pop()();assert.equal(calls.length,0,'No intermediate VAT request inside native handlers');
  delete frm.__retail_purchase_action;frm.__quick_receipt={pending:1};
  await timers.pop()();assert.equal(calls.length,0,'No intermediate VAT request inside Quick Entry queue');
  await window.retail.transaction_items.flushVatTaxRows(frm);
  assert.equal(calls.length,1,'Save/settle flush is allowed even while its queue action is pending');
  frm.__quick_receipt.pending=0;
  await timers.pop()();assert.equal(calls.length,1,'Flushing invalidates the deferred summary');
 });
 test(doctype + ': native action reuses bundled reads and releases them after nested handlers and errors', async () => {
  const handlers={}, calls=[], row={item_code:'A',uom:'Box',item_tax_template:'VAT5'};
  const request={method:'retail.domains.transactions.vat.get_transaction_item_vat_rate',
   args:{item_code:'A',child_doctype:doctype+' Item',parent_doctype:doctype,item_tax_template:'VAT5'}};
  const frappe={ui:{form:{on(dt,events){handlers[dt]={...handlers[dt],...events};}}},
   async call(options){calls.push(options);return {message:{item:{name:'A',has_serial_no:1,has_batch_no:0},lookups:[{...request,message:5}]}};}};
  const window={frappe}, locals={[doctype+' Item']:{row}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../public/js/forms/transaction_items.js'),'utf8'),
   {window,frappe,locals,cint:Number,flt:Number,setTimeout,clearTimeout,__:s=>s});
  let fail=false, reads=0;
  const frm={doc:{doctype},script_manager:{async trigger(event,cdt,cdn){
   assert.equal(this,frm.script_manager,'Preserve native receiver');
   assert.equal((await window.retail.transaction_items.preparedPurchaseItem(frm,'A')).name,'A');
   assert.equal((await window.retail.transaction_items.purchaseRead(frm,request)).message,5);reads++;
   if(event==='item_code') await this.trigger('rate',cdt,cdn);
   if(fail) throw new Error('native failure');
   return 'native result';
  }}};
  handlers[doctype].refresh(frm);
  const wrapped=frm.script_manager.trigger;handlers[doctype].refresh(frm);
  assert.equal(frm.script_manager.trigger,wrapped,'Install once');
  assert.equal(await wrapped.call(frm.script_manager,'item_code',doctype+' Item','row'),'native result');
  assert.equal(reads,2);assert.equal(calls.length,1,'One bundle serves sequential and nested reads');
  assert.equal(frm.__retail_purchase_action,undefined);
  assert.equal(await window.retail.transaction_items.preparedPurchaseItem(frm,'A'),null,'No metadata survives the action');
  await wrapped.call(frm.script_manager,'item_code',doctype+' Item','row');
  assert.equal(calls.length,2,'Next action gets a fresh bundle');
  fail=true;
  await assert.rejects(wrapped.call(frm.script_manager,'item_code',doctype+' Item','row'),/native failure/);
  assert.equal(frm.__retail_purchase_action,undefined,'Failure releases action state');
 });
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
