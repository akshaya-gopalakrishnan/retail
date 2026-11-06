const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../public/js/forms/purchase_receipt_quick_entry.js'), 'utf8');
function fixture() {
 const handlers={}, messages=[], changes=[], created=[];
 const element=()=>new Proxy({0:{listeners:{},scrollIntoView(){},addEventListener(name,handler){this.listeners[name]=handler;}}}, {get:(obj,key)=>key in obj ? obj[key] : key==='is' ? ()=>false : ()=>element()});
 const $=()=>element();
 class Dialog {
  constructor(opts){this.opts=opts;this.values={};this.fields_dict={};this.$wrapper=element();
   for(const df of opts.fields)if(df.fieldname){
    this.values[df.fieldname]=df.default;
    const input=element(),events={};let value='';
    input.on=(name,fn)=>{events[name]=fn;return input;};input.off=()=>input;
    input.val=(next)=>{if(next===undefined)return value;value=next;return input;};
    this.fields_dict[df.fieldname]={df,events,$input:input,$wrapper:element(),set_input(v){value=v;},set_focus(){}};
   }}
  get_value(field){return this.values[field];} get_field(field){return this.fields_dict[field];}
  async set_value(field,value){this.values[field]=value;this.fields_dict[field]?.set_input(value);this.fields_dict[field]?.df.onchange?.();} show(){} hide(){this.hidden=true;}
 }
 const frm={doc:{doctype:'Purchase Receipt',docstatus:0,supplier:'Supplier',company:'Company',set_warehouse:'Stores',items:[],currency:'AED'},
  perm:[{write:1}],is_new:()=>false,is_dirty:()=>false,refresh_field(){},
  add_child(){const row={doctype:'Purchase Receipt Item',name:'row-'+this.doc.items.length,qty:0};this.doc.items.push(row);return row;},
  async set_value(field,value){this.doc[field]=value;},async save(){this.saved=true;},savesubmit(){this.submitting=true;}};
 const frappe={flags:{},utils:{escape_html:String},ui:{Dialog,form:{on:(dt,h)=>handlers[dt]=h,
  make_control:({df})=>({df,$wrapper:element(),$input:element(),set_input(v){this.value=v;},get_value(){return this.value;},refresh(){}})}},
  db:{get_doc:async (_dt,name)=>({name,stock_uom:'Nos'})},after_ajax:fn=>fn(),msgprint:msg=>messages.push(msg),
  throw:msg=>{throw Error(msg);},new_doc:async (dt,defaults)=>created.push({dt,defaults}),
  model:{can_create:()=>true,async set_value(dt,name,field,value){const values=typeof field==='string'?{[field]:value}:field;
   changes.push({name,values});Object.assign(frm.doc.items.find(r=>r.name===name),values);}},
 };
 const context={frappe,$,console:{error(){}},setTimeout,clearTimeout,format_currency:v=>String(v||0),flt:v=>Number(v)||0,__:(s,args)=>s.replace(/\{(\d+)\}/g,(_,i)=>args?.[i]??'')};
 context.window=context;
 vm.runInNewContext(source.replace(/\}\)\(\);\s*$/, 'globalThis.QuickReceipt = QuickReceipt;})();'),context);
 const entry=new context.QuickReceipt(frm);entry.settle=async()=>{};entry.scheduleSync=()=>{};entry.render=()=>{entry.rows=new Map();};
 entry.rows=new Map();frm.__quick_receipt=entry;
 return {entry,frm,frappe,handlers,messages,changes,created,context};
}
test('packing aliases increment one item/UOM while other UOMs remain separate',async()=>{
 const {entry,frm}=fixture();
 await entry.add({item_code:'A',uom:'Box-10',barcode:'one'});
 await entry.add({item_code:'A',uom:'Box-10',barcode:'two'});
 await entry.add({item_code:'A',uom:'Nos'});
 assert.equal(frm.doc.items.length,2);assert.equal(frm.doc.items[0].qty,2);assert.equal(frm.doc.items[1].qty,1);
});
test('100 distinct items stay in one receipt and scanning does not increment generated FOC rows',async()=>{
 const {entry,frm}=fixture();
 for(let i=0;i<105;i++)await entry.add({item_code:'Item-'+i,uom:'Nos'});
 frm.doc.items.unshift({name:'free',item_code:'Item-0',uom:'Nos',qty:5,warehouse:'Stores',custom_foc_parent:'paid'});
 await entry.add({item_code:'Item-0',uom:'Nos'});
 assert.equal(frm.doc.items.length,106);assert.equal(frm.doc.items[0].qty,5);assert.equal(frm.doc.items[1].qty,2);
});
test('tracked items use native inline fields and accept serial and batch inputs',async()=>{
 const {entry,frm,frappe,context}=fixture();
 frappe.db.get_doc=async(_dt,name)=>({name,stock_uom:'Nos',custom_barcode:'B-'+name,has_batch_no:name==='Batch'?1:0,has_serial_no:name==='Serial'?1:0});
 await entry.add({item_code:'Batch',batch_no:'BATCH-ONE'});
 await entry.add({item_code:'Serial',serial_no:'SN-ONE'});
 context.QuickReceipt.prototype.render.call(entry);
 assert.equal(frm.doc.items[0].use_serial_batch_fields,1);
 assert.equal(frm.doc.items[0].batch_no,'BATCH-ONE');
 assert.equal(frm.doc.items[1].serial_no,'SN-ONE');
 assert.equal(frm.doc.items[1].custom_item_barcode,'B-Serial');
 assert.ok(entry.rows.get(frm.doc.items[0].name).controls.batch_no);
 assert.equal(entry.rows.get(frm.doc.items[0].name).controls.serial_no,undefined);
 assert.ok(entry.rows.get(frm.doc.items[1].name).controls.serial_no);
 assert.equal(entry.rows.get(frm.doc.items[1].name).controls.batch_no,undefined);
 await assert.rejects(entry.add({item_code:'Serial',serial_no:'SN-ONE'}),/already in/);
 assert.equal(frm.doc.items[1].qty,1);
});
test('Save waits for edits and persists through the normal form',async()=>{
 const {entry,frm}=fixture();await entry.add({item_code:'A'});
 frm.is_dirty=()=>!frm.saved;
 entry.enqueue(async()=>{await new Promise(r=>setTimeout(r,10));frm.doc.items[0].custom_foc_qty=3;});
 frm.save=async()=>{assert.equal(frm.doc.items[0].custom_foc_qty,3);frm.saved=true;};
 await entry.save(false);assert.equal(frm.saved,true);assert.equal(frm.submitting,undefined);
});
test('save failure preserves rows and never starts submission or a new receipt',async()=>{
 const {entry,frm,created}=fixture();await entry.add({item_code:'A'});frm.is_dirty=()=>true;
 frm.save=async()=>{throw Error('mandatory field');};
 await assert.rejects(entry.save(true),/mandatory field/);
 assert.equal(frm.doc.items.length,1);assert.equal(frm.submitting,undefined);assert.equal(created.length,0);assert.equal(entry.saving,false);
});
test('Submit + New opens a fresh receipt only after on_submit, retaining safe defaults',async()=>{
 const {entry,frm,handlers,created}=fixture();await entry.add({item_code:'A'});
 await entry.save(true);assert.equal(frm.submitting,true);assert.equal(created.length,0);
 frm.doc.docstatus=1;await handlers['Purchase Receipt'].on_submit(frm);
 assert.equal(created.length,1);assert.equal(created[0].defaults.set_warehouse,'Stores');assert.equal(created[0].defaults.supplier,undefined);
});
test('cancelled submission clears the new receipt intent',async()=>{
 const {entry,frm,handlers,created}=fixture();await entry.add({item_code:'A'});
 frm.savesubmit=(_btn,_callback,onError)=>onError();
 await entry.save(true);await handlers['Purchase Receipt'].on_submit(frm);assert.equal(created.length,0);
});
test('dialog edits delegate quantities, rates and amounts to real PR fields; UOM and VAT stay read-only',async()=>{
 const {entry,frm,context,changes}=fixture();await entry.add({item_code:'A'});
 context.QuickReceipt.prototype.render.call(entry);
 const fields={qty:7,custom_foc_qty:2,custom_rate_including_vat:105,rate:100,custom_amount_including_vat:735,amount:700};
 for(const [field,value] of Object.entries(fields)){
  const control=entry.rows.get(frm.doc.items[0].name).controls[field];control.value=value;control.df.onchange();await entry.queue;
  assert.equal(frm.doc.items[0][field],value);
  assert.ok(changes.some(change=>change.values[field]===value));
 }
 const controls=entry.rows.get(frm.doc.items[0].name).controls;
 for(const [field,value] of [['uom','Box-12'],['custom_vat_amount',999]]){
  assert.equal(controls[field].df.read_only,true);
  controls[field].value=value;controls[field].df.onchange();await entry.queue;
  assert.equal(changes.some(change=>change.values[field]===value),false);
 }
 assert.equal(frm.doc.items[0].uom,'Nos');
 assert.equal(controls.custom_new_sell_incl,undefined);
 assert.deepEqual(Object.keys(controls).slice(-5),['custom_rate_including_vat','rate','custom_amount_including_vat','amount','custom_vat_amount']);
});
test('render hides generated free rows and keeps 105 paid rows editable',async()=>{
 const {entry,frm,context}=fixture();
 for(let i=0;i<105;i++)await entry.add({item_code:'A-'+i});
 frm.doc.items.push({name:'free',item_code:'A-0',qty:4,custom_foc_parent:'parent'});
 context.QuickReceipt.prototype.render.call(entry);
 assert.equal(entry.rows.size,105);assert.equal(entry.rows.has('free'),false);
 assert.equal(entry.rows.get('row-0').controls.custom_new_sell_incl,undefined);
 assert.equal(entry.rows.get('row-0').controls.qty.df.read_only,false);
});
test('scanner Enter reads uncommitted input and change does not add it twice',async()=>{
 const {entry,frm,frappe}=fixture();let calls=0;
 frappe.call=async args=>{calls++;assert.equal(args.args.search_value,'258');return {message:{item_code:'A',uom:'Box-10'}};};
 const field=entry.dialog.get_field('scan');field.$input.val('258');
 let prevented=false,stopped=false;
 field.events['keydown.quickReceipt']({key:'Enter',preventDefault(){prevented=true;},stopImmediatePropagation(){stopped=true;}});
 field.df.onchange();await entry.queue;
 assert.equal(calls,1);assert.equal(frm.doc.items.length,1);assert.equal(frm.doc.items[0].uom,'Box-10');
 assert.equal(prevented,true);assert.equal(stopped,true);assert.equal(field.$input.val(),'');
});
test('Tab-suffix and camera/change scans use the same lookup path',async()=>{
 const {entry,frm,frappe}=fixture();let calls=0;
 frappe.call=async()=>{calls++;return {message:{item_code:'A',uom:'Nos'}};};
 const field=entry.dialog.get_field('scan');
 field.$input.val('123');field.events['keydown.quickReceipt']({key:'Tab'});await entry.queue;
 field.$input.val('123');field.df.onchange();await entry.queue;
 assert.equal(calls,2);assert.equal(frm.doc.items[0].qty,2);assert.equal(field.df.options,'Barcode');
});
test('missing header or failed lookup retains barcode for correction',async()=>{
 const {entry,frm,frappe}=fixture();const field=entry.dialog.get_field('scan');
 frm.doc.supplier='';field.$input.val('123');await entry.scan();assert.equal(field.$input.val(),'123');
 frm.doc.supplier='Supplier';frappe.call=async()=>({message:{}});
 await entry.scan();assert.equal(field.$input.val(),'123');assert.equal(frm.doc.items.length,0);assert.equal(entry.failed,true);
});
test('Tab opens new Supplier even when a supplier is already selected',async()=>{
 const {entry,frm,frappe}=fixture();
 entry.dialog.get_field('supplier').$input.val('Supplier');
 let opened=false;
 frappe.ui.form.make_quick_entry=async(dt,after,init)=>{
  opened=true;assert.equal(dt,'Supplier');init({set_value(){throw Error('existing supplier must not prefill a new supplier');}});
 };
 await entry.supplierFromTab();assert.equal(opened,true);assert.equal(frm.doc.supplier,'Supplier');
 assert.equal(entry.dialog.hidden,undefined);
});
test('Tab on a new supplier opens standard Quick Entry and assigns the saved supplier',async()=>{
 const {entry,frm,frappe}=fixture();entry.dialog.get_field('supplier').$input.val('New Supplier');
 frappe.db.get_value=async()=>({message:{}});
 let callback,prefill;
 frappe.ui.form.make_quick_entry=async(dt,after,init,_doc,force)=>{
  assert.equal(dt,'Supplier');assert.equal(force,true);callback=after;
  init({set_value(field,value){prefill={field,value};}});
 };
 await entry.supplierFromTab();assert.equal(prefill.field,'supplier_name');assert.equal(prefill.value,'New Supplier');
 await callback({name:'SUP-NEW'});assert.equal(frm.doc.supplier,'SUP-NEW');
});

test('Supplier Tab opens creation even with a highlighted autocomplete suggestion; Shift+Tab stays native',async()=>{
 const {entry,frappe}=fixture();let count=0;
 frappe.ui.form.make_quick_entry=async()=>{count++;};
 const field=entry.dialog.get_field('supplier');field.awesomplete={opened:true,index:0,close(){}};
 const press=shiftKey=>field.$input[0].listeners.keydown({key:'Tab',shiftKey,preventDefault(){},stopImmediatePropagation(){}});
 press(true);assert.equal(count,0);press(false);assert.equal(count,1);
});

test('deleting selected paid rows removes their FOC rows and preserves unselected items',async()=>{
 const {entry,frm,frappe}=fixture();await entry.add({item_code:'A'});await entry.add({item_code:'B'});await entry.add({item_code:'C'});
 const paid=frm.doc.items[0];paid.custom_foc_key='key';
 const other=frm.doc.items[2];other.custom_foc_key='other-key';
 frm.doc.items.push({name:'free',doctype:'Purchase Receipt Item',item_code:'A',custom_foc_parent:'key'});
 frm.doc.items.push({name:'other-free',doctype:'Purchase Receipt Item',item_code:'C',custom_foc_parent:'other-key'});
 const events=[];frm.script_manager={trigger:async(event,_dt,name)=>events.push([event,name])};frm.dirty=()=>{frm.dirtied=true;};
 frappe.model.clear_doc=(_dt,name)=>{frm.doc.items=frm.doc.items.filter(row=>row.name!==name);};
 entry.selectedRows.add(paid.name);entry.selectedRows.add(other.name);
 await entry.removeRows([paid,other]);
 assert.equal(frm.doc.items.length,1);assert.equal(frm.doc.items[0].item_code,'B');assert.equal(frm.dirtied,true);
 assert.equal(entry.selectedRows.size,0);
 assert.equal(events.filter(([event])=>event==='calculate_taxes_and_totals').length,1);
 assert.equal(events.filter(([event])=>event==='before_items_remove').length,4);
 assert.ok(events.slice(0,4).every(([event])=>event==='before_items_remove'));
});
test('a removal hook can reject bulk deletion before any selected row is changed',async()=>{
 const {entry,frm,frappe}=fixture();await entry.add({item_code:'A'});await entry.add({item_code:'B'});
 const rows=[...frm.doc.items];
 frm.script_manager={trigger:async(_event,_dt,name)=>{if(name===rows[1].name)throw Error('Cannot remove this item');}};
 frappe.model.clear_doc=()=>{throw Error('Must not remove any rows');};
 await assert.rejects(entry.removeRows(rows),/Cannot remove this item/);
 assert.deepEqual(frm.doc.items,rows);
});
test('FOC tracking rows expose separate allocations and keep maintained quantities read-only',async()=>{
 const {entry,frm,frappe,context}=fixture();
 frappe.db.get_doc=async()=>({stock_uom:'Nos',has_serial_no:1});await entry.add({item_code:'Serial'});
 frm.doc.items.push({name:'free',item_code:'Serial',custom_foc_parent:'paid',qty:1});
 context.QuickReceipt.prototype.render.call(entry);
 const fields=entry.rows.get('free').controls;
 assert.equal(fields.qty.df.read_only,true);assert.equal(fields.serial_no.df.read_only,false);
 fields.serial_no.value='FREE-SERIAL';fields.serial_no.df.onchange();await entry.queue;
 assert.equal(frm.doc.items[1].serial_no,'FREE-SERIAL');
});
test('read-only serial and FOC controls may lack inputs without breaking the table',async()=>{
 const {entry,frm,frappe,context}=fixture();
 frappe.db.get_doc=async()=>({stock_uom:'Nos',has_serial_no:1});await entry.add({item_code:'I-42'});
 frm.doc.items[0].serial_and_batch_bundle='DRAFT-BUNDLE';
 frm.doc.items.push({name:'free',item_code:'I-42',custom_foc_parent:'paid',qty:1});
 const make=frappe.ui.form.make_control;
 frappe.ui.form.make_control=opts=>{
  const control=make(opts);
  if(opts.df.read_only){delete control.$input;control.set_input=()=>{throw Error('read-only control has no input');};}
  return control;
 };
 context.QuickReceipt.prototype.render.call(entry);
 assert.equal(entry.rows.size,2);assert.equal(entry.rows.get(frm.doc.items[0].name).controls.serial_no.df.read_only,true);
});
test('failed table reconstruction retains the previous rows and visible table',async()=>{
 const {entry,frm,frappe,context}=fixture();await entry.add({item_code:'I-42'});
 context.QuickReceipt.prototype.render.call(entry);const previous=entry.rows;
 frm.doc.items.push({doctype:'Purchase Receipt Item',name:'new-row',item_code:'Other'});
 let replaced=false;const target=entry.dialog.get_field('items_html').$wrapper;
 target.empty=()=>{replaced=true;return target;};
 frappe.ui.form.make_control=()=>{throw Error('render error');};
 assert.throws(()=>context.QuickReceipt.prototype.render.call(entry),/render error/);
 assert.equal(entry.rows,previous);assert.equal(replaced,false);assert.equal(frm.doc.items.length,2);
});

test('repeat scans reuse the item master and table controls while retaining quantities and selection',async()=>{
 const {entry,frm,frappe,context}=fixture();let fetched=0,made=0;
 const get=frappe.db.get_doc,make=frappe.ui.form.make_control;
 frappe.db.get_doc=async(...args)=>{fetched++;return get(...args);};
 frappe.ui.form.make_control=opts=>{made++;return make(opts);};
 entry.render=()=>context.QuickReceipt.prototype.render.call(entry);
 await entry.add({item_code:'A'});const first=entry.rows.get(frm.doc.items[0].name),initial=made;
 entry.selectedRows.add(first.row.name);
 await entry.add({item_code:'A'});
 assert.equal(fetched,1);assert.equal(made,initial);assert.equal(entry.rows.get(first.row.name),first);
 assert.equal(first.controls.qty.get_value(),2);assert.equal(entry.selectedRows.has(first.row.name),true);
 await entry.add({item_code:'B'});
 assert.equal(made,initial*2);assert.equal(entry.rows.get(first.row.name),first);
});

test('queued edits proceed before delayed calculations and Save waits for the final debounce',async()=>{
 const {entry,frm,context}=fixture();let now=10000,next=0;
 const timers=new Map();
 context.Date={now:()=>now};
 context.setTimeout=(fn,delay)=>{timers.set(++next,{fn,at:now+delay});return next;};
 context.clearTimeout=id=>timers.delete(id);
 entry.scheduleSync=context.QuickReceipt.prototype.scheduleSync.bind(entry);
 entry.settle=context.QuickReceipt.prototype.settle.bind(entry);
 const scheduled=[];const schedule=entry.scheduleSync;
 entry.scheduleSync=delay=>{scheduled.push(delay);schedule(delay);};
 await entry.enqueue(()=>entry.add({item_code:'A'}));
 await entry.enqueue(()=>entry.add({item_code:'A'}));
 assert.equal(frm.doc.items[0].qty,2);assert.equal(now,10000);assert.equal(entry.pending,0);
 assert.equal(timers.size,1);
 const row=frm.doc.items[0];
 now+=500;entry.scheduleSync(3200);now+=100;entry.scheduleSync();
 assert.equal(entry.settleAt,13700,'ordinary edits must preserve an outstanding serial calculation');
 frm.is_dirty=()=>!frm.saved;
 frm.save=async()=>{assert.equal(row.custom_total_stock_qty,9);frm.saved=true;};
 const saving=entry.save(false);
 await Promise.resolve();assert.equal(frm.saved,undefined);
 row.custom_total_stock_qty=9;now=13700;
 for(const {fn} of [...timers.values()])fn();
 await saving;
 assert.equal(frm.saved,true);assert.equal(entry.saving,false);
});

test('rapid quantity and inclusive-price edits await active VAT writes before applying the next value',async()=>{
 const {entry,frm,frappe,context}=fixture();await entry.add({item_code:'A'});
 context.QuickReceipt.prototype.render.call(entry);
 const row=frm.doc.items[0],set=frappe.model.set_value;
 frappe.model.set_value=async(dt,name,field,value)=>{
  assert.equal(Boolean(row.__retail_vat_syncing),false);
  await set(dt,name,field,value);
  row.__retail_vat_syncing=true;
  setTimeout(()=>{
   if(field==='custom_rate_including_vat')row.rate=value/1.05;
   row.__retail_vat_syncing=false;
  },10);
 };
 const fields=entry.rows.get(row.name).controls;
 fields.qty.value=4;fields.qty.df.onchange();
 fields.custom_rate_including_vat.value=10.5;fields.custom_rate_including_vat.df.onchange();
 await entry.queue;
 assert.equal(row.qty,4);assert.equal(row.custom_rate_including_vat,10.5);assert.equal(row.rate,10);
});

test('Quick Entry registration leaves full-form Supplier keyboard behaviour unchanged',()=>{
 const {frm,handlers}=fixture();frm.add_custom_button=()=>{};
 const supplier={};frm.fields_dict={supplier};
 handlers['Purchase Receipt'].refresh(frm);
 assert.equal(supplier.__retail_supplier_tab_action,undefined);
 assert.equal(frm.__retail_supplier_popup,undefined);
});

test('date sits right of the update options and enables native posting-date editing before applying the date',async()=>{
 const {entry,frm}=fixture();
 const fields=entry.dialog.opts.fields;
 const date=fields.findIndex(field=>field.fieldname==='posting_date');
 assert.equal(fields[date-1].fieldtype,'Column Break');
 assert.equal(fields[date-2].fieldname,'custom_update_item_master_rates');
 assert.equal(fields[date+1].fieldtype,'Section Break');
 assert.equal(fields[date].fieldtype,'Date');assert.equal(fields[date].reqd,1);
 const changes=[];
 frm.set_value=async(field,value)=>{changes.push([field,value]);frm.doc[field]=value;};
 await entry.dialog.set_value('posting_date','2026-11-04');await entry.queue;
 assert.deepEqual(changes,[['set_posting_time',1],['posting_date','2026-11-04']]);
 assert.equal(frm.doc.posting_date,'2026-11-04');
});

test('packing scans retain the exact scanned alias instead of the master barcode, including after display refresh',async()=>{
 const {entry,frm,frappe}=fixture();
 frappe.db.get_doc=async()=>({name:'A',stock_uom:'Nos',custom_barcode:'MASTER',purchase_uom:'Box-10',
  custom_retail_packing_detail:[{uom:'Box-10',conversion_factor:10,barcode:'PACK-ONE'},{uom:'Box-10',conversion_factor:10,barcode:'PACK-TWO'}]});
 await entry.add({item_code:'A',uom:'Box-10',barcode:'PACK-TWO'});
 const row=frm.doc.items[0];
 assert.equal(row.barcode,'PACK-TWO');assert.equal(row.custom_item_barcode,'PACK-TWO');
 row.custom_item_barcode='MASTER';assert.equal(entry.barcode(row),'PACK-TWO');
 await entry.add({item_code:'A',uom:'Box-10',barcode:'PACK-ONE'});
 assert.equal(row.qty,2);assert.equal(row.barcode,'PACK-ONE');assert.equal(entry.barcode(row),'PACK-ONE');
 await entry.add({item_code:'A',uom:'Nos',barcode:'MASTER'});
 assert.equal(frm.doc.items[1].uom,'Nos');assert.equal(entry.barcode(frm.doc.items[1]),'MASTER');
});

test('existing packing rows load the Item packing barcode once without changing receipt data',async()=>{
 const {entry,frm,frappe}=fixture();let fetched=0;
 const master={name:'A',stock_uom:'Nos',custom_barcode:'MASTER'};
 frappe.db.get_list=async()=>[master];
 frappe.db.get_doc=async()=>{fetched++;return {...master,custom_retail_packing_detail:[{uom:'Box-10',conversion_factor:10,barcode:'PACK'}]};};
 const row={name:'saved',item_code:'A',uom:'Box-10',conversion_factor:10,custom_item_barcode:'MASTER'};
 frm.doc.items.push(row);const before=JSON.stringify(row);
 await entry.loadItems();assert.equal(entry.barcode(row),'PACK');
 assert.equal(JSON.stringify(row),before);
 await entry.loadItems();assert.equal(fetched,1);
 row.uom='Box-20';assert.equal(entry.barcode(row),'','a missing packing barcode must not display the stock barcode');
});

test('new item search uses the Item purchase UOM and its packing barcode',async()=>{
 const {entry,frm,frappe}=fixture();
 frappe.db.get_doc=async()=>({stock_uom:'Nos',purchase_uom:'Box-12',custom_barcode:'MASTER',
  custom_retail_packing_detail:[{uom:'Box-12',conversion_factor:12,barcode:'PACK-12'}]});
 await entry.add({item_code:'A'});
 assert.equal(frm.doc.items[0].uom,'Box-12');assert.equal(entry.barcode(frm.doc.items[0]),'PACK-12');
});

test('Quick Entry rate, amount and quantity edits run the full-form VAT handlers for taxable and zero-rated items',async()=>{
 const {entry,frm,frappe,context}=fixture();await entry.add({item_code:'A'});
 const row=frm.doc.items[0],cdt=row.doctype,events={};
 Object.assign(row,{qty:2,rate:100,amount:200,custom_rate_including_vat:105,custom_amount_including_vat:210,custom_vat_amount:10});
 frm.fields_dict={};
 frappe.ui.form.on=(dt,handlers)=>{
  events[dt] ||= {};
  for(const [field,handler] of Object.entries(handlers))(events[dt][field] ||= []).push(handler);
 };
 frappe.meta={get_docfield:()=>({precision:2})};
 let vat=5;frappe.call=async()=>({message:vat});
 context.cint=v=>Number(v)||0;
 context.flt=(v,p)=>p===undefined?Number(v)||0:Number((Number(v)||0).toFixed(p));
 context.locals={[cdt]:{[row.name]:row}};
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../public/js/forms/transaction_items.js'),'utf8'),context);
 frappe.model.set_value=async(dt,name,field,value)=>{
  for(const [key,next] of Object.entries(typeof field==='string'?{[field]:value}:field)){
   if(row[key]===next)continue;
   row[key]=next;
   for(const handler of events[dt]?.[key]||[])await handler(frm,dt,name);
  }
 };
 context.QuickReceipt.prototype.render.call(entry);
 const edit=async(field,value)=>{
  const control=entry.rows.get(row.name).controls[field];control.value=value;control.df.onchange();await entry.queue;
  assert.equal(entry.failed,undefined);entry.sync();
 };
 await edit('custom_rate_including_vat',210);
 assert.equal(row.rate,200);assert.equal(row.amount,400);assert.equal(row.custom_amount_including_vat,420);assert.equal(row.custom_vat_amount,20);
 await edit('rate',50);
 assert.equal(row.custom_rate_including_vat,52.5);assert.equal(row.amount,100);assert.equal(row.custom_amount_including_vat,105);assert.equal(row.custom_vat_amount,5);
 await edit('custom_amount_including_vat',630);
 assert.equal(row.rate,300);assert.equal(row.amount,600);assert.equal(row.custom_rate_including_vat,315);assert.equal(row.custom_vat_amount,30);
 await edit('amount',200);
 assert.equal(row.rate,100);assert.equal(row.custom_amount_including_vat,210);assert.equal(row.custom_vat_amount,10);
 await edit('qty',3);
 assert.equal(row.amount,300);assert.equal(row.custom_amount_including_vat,315);assert.equal(row.custom_vat_amount,15);
 vat=0;await edit('rate',75);
 assert.equal(row.custom_rate_including_vat,75);assert.equal(row.custom_amount_including_vat,225);assert.equal(row.custom_vat_amount,0);
 await edit('qty',0);
 assert.equal(row.amount,0);assert.equal(row.custom_amount_including_vat,0);assert.equal(row.custom_vat_amount,0);
 assert.equal(entry.rows.get(row.name).controls.custom_vat_amount.value,0);
});
