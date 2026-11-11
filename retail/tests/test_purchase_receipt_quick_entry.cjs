const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../public/js/forms/purchase_receipt_quick_entry.js'), 'utf8');
function fixture(doctype = "Purchase Receipt", updateStock = 0) {
 const handlers={}, messages=[], changes=[], created=[];
 const element=()=>new Proxy({0:{listeners:{},querySelectorAll(){return [];},scrollIntoView(){},addEventListener(name,handler){this.listeners[name]=handler;}}}, {get:(obj,key)=>key in obj ? obj[key] : key==='is' ? ()=>false : ()=>element()});
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
  set_df_property(field,key,value){this.fields_dict[field].df[key]=value;}
  get_value(field){return this.values[field];} get_field(field){return this.fields_dict[field];}
  async set_value(field,value){this.values[field]=value;this.fields_dict[field]?.set_input(value);this.fields_dict[field]?.df.onchange?.();} show(){} hide(){this.hidden=true;}
 }
 const frm={doc:{doctype,update_stock:updateStock,docstatus:0,supplier:'Supplier',company:'Company',set_warehouse:'Stores',items:[],currency:'AED'},
  script_manager:{async trigger(){}},perm:[{write:1}],is_new:()=>false,is_dirty:()=>false,refresh_field(){},
  add_child(){const row={doctype:doctype+' Item',name:'row-'+this.doc.items.length,qty:0};this.doc.items.push(row);return row;},
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
test('Quick Entry blocks input Enter saving and routes Tab and Shift+Enter to scan',()=>{
 const {entry,frappe}=fixture();let scanned=0;
 frappe.ui.open_dialogs=[entry.dialog];
 entry.dialog.get_field('scan').set_focus=()=>scanned++;
 const listeners=entry.dialog.$wrapper[0].listeners;
 const target={matches:()=>true};
 const event=key=>({key,target,preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;}});
 const enter=event('Enter');listeners.keypress(enter);
 assert.equal(enter.prevented,true);assert.equal(enter.stopped,true);
 const tab=event('Tab');listeners.keydown(tab);assert.equal(scanned,1);assert.equal(tab.prevented,true);
 const shift=event('Enter');shift.shiftKey=true;listeners.keydown(shift);assert.equal(scanned,2);
 frappe.ui.open_dialogs=[{}];
 const nested=event('Enter');listeners.keypress(nested);assert.equal(nested.prevented,undefined);
});
test('Search Item Enter adds the selected item and Tab returns to scanner',()=>{
 const {entry}=fixture();let added=0,scanned=0,closed=0;
 const item=entry.dialog.get_field('item');
 entry.dialog.get_field('add').$input.trigger=()=>added++;
 entry.dialog.get_field('scan').set_focus=()=>scanned++;
 item.awesomplete={close(){closed++;}};
 const press=(key,extra={})=>item.$input[0].listeners.keydown({key,preventDefault(){},stopImmediatePropagation(){},...extra});
 press('Enter');assert.equal(added,1);
 press('Enter',{repeat:true});assert.equal(added,1);
 press('Tab');assert.equal(scanned,1);assert.equal(closed,1);assert.equal(added,1);
});
test('adding an item focuses its first editable table cell after Link callbacks',async()=>{
 const {entry,frm,frappe}=fixture();const order=[];
 const input={type:'text',tagName:'INPUT',tabIndex:0,getClientRects:()=>[{}],focus(){order.push('table');},select(){}};
 frappe.after_ajax=fn=>{order.push('link');fn();};
 entry.dialog.values.find='previous item';
 entry.filter=()=>{};
 entry.render=()=>{entry.rows=new Map(frm.doc.items.map(row=>[row.name,{element:{0:{querySelectorAll:()=>[input],scrollIntoView(){}},addClass(){}}}]));};
 await entry.add({item_code:'A'});
 assert.equal(entry.dialog.get_value('find'),'');
 assert.equal(order.at(-1),'table');assert.ok(order.includes('link'));
});
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
test('missing header retains barcode; unknown barcode clears and refocuses scanner',async()=>{
 const {entry,frm,frappe}=fixture();const field=entry.dialog.get_field('scan');
 let focused=0;field.set_focus=()=>focused++;
 let feedback='';
 entry.dialog.get_field('scan_feedback').$wrapper.html=value=>{feedback=value;};
 entry.dialog.get_field('scan_feedback').$wrapper.empty=()=>{feedback='';};
 frappe.show_alert=()=>{throw Error('Barcode errors must display inside Quick Entry');};
 frm.doc.supplier='';field.$input.val('123');await entry.scan();assert.equal(field.$input.val(),'123');
 frm.doc.supplier='Supplier';frappe.call=async()=>({message:{}});
 await entry.scan();assert.equal(field.$input.val(),'');assert.equal(frm.doc.items.length,0);assert.equal(entry.failed,undefined);assert.equal(focused,1);
 assert.match(feedback,/role="alert"/);assert.match(feedback,/Cannot find Item with barcode 123/);
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

test('Quick Entry shares concurrent and completed reads within an action, including zero VAT, then refreshes on the next action',async()=>{
 const {entry,frappe}=fixture();entry.dialog.$wrapper.is=()=>true;
 let calls=0,resolve;
 frappe.call=()=>{calls++;return new Promise(done=>{resolve=done;});};
 const request={method:'vat',args:{item_code:'A',item_tax_template:'ZERO'}};
 await entry.enqueue(async()=>{
  const first=entry.lookup(request),second=entry.lookup(request);
  assert.equal(first,second);assert.equal(calls,1);
  resolve({message:0});assert.equal((await first).message,0);
  assert.equal((await entry.lookup(request)).message,0);assert.equal(calls,1);
 });
 frappe.call=async()=>{calls++;return {message:5};};
 await entry.enqueue(async()=>{assert.equal((await entry.lookup(request)).message,5);});
 assert.equal(calls,2);
 await entry.enqueue(async()=>{
  await entry.lookup(request);
  await entry.lookup({...request,args:{item_code:'A',item_tax_template:'VAT5'}});
  await entry.lookup({...request,args:{item_code:'B',item_tax_template:'ZERO'}});
 });
 assert.equal(calls,5,'different item/template keys must not share VAT');
 assert.equal(entry.failed,undefined);
});

test('failed lookups can retry and closed or replaced dialogs never serve cached reads',async()=>{
 const {entry,frm,frappe}=fixture();entry.dialog.$wrapper.is=()=>true;let calls=0;
 const request={method:'vat',args:{item_code:'A'}};
 frappe.call=async()=>{if(++calls===1)throw Error('offline');return {message:calls};};
 await entry.enqueue(async()=>{
  await assert.rejects(entry.lookup(request),/offline/);
  assert.equal((await entry.lookup(request)).message,2);
  entry.dialog.$wrapper.is=()=>false;
  assert.equal((await entry.lookup(request)).message,3);
  entry.dialog.$wrapper.is=()=>true;frm.__quick_receipt={};
  assert.equal((await entry.lookup(request)).message,4);
 });
 assert.equal(entry.failed,undefined);
});

test('cached Item masters still fetch fresh VAT and selling reads together before field writes',async()=>{
 const {entry,frm,frappe}=fixture();entry.dialog.$wrapper.is=()=>true;
 frappe.meta={has_field:()=>true};
 frm.__retail_purchase_tracking={items:new Map()};
 entry.items.set('A',{name:'A',stock_uom:'Nos'});
 const requests=[],resolve=[];
 frappe.call=request=>{requests.push(request);return new Promise(done=>resolve.push(done));};
 const adding=entry.enqueue(()=>entry.add({item_code:'A'}));
 while(requests.length<3)await new Promise(setImmediate);
 assert.equal(frm.doc.items[0].item_code,undefined);
 assert.deepEqual(requests.map(r=>r.method.split('.').pop()).sort(),
  ['get_item_selling_vat_rate','get_standard_selling_rate','get_transaction_item_vat_rate']);
 for(const done of resolve)done({message:0});
 await adding;
 assert.equal(frm.doc.items[0].item_code,'A');assert.equal(frm.doc.items[0].qty,1);
 assert.equal(frm.__retail_purchase_tracking.items.get('A'),entry.items.get('A'));
 assert.equal(entry.failed,undefined);
});

test('barcode refresh uses Quick Entry masters, queries only missing items, and resumes normal reads when closed',async()=>{
 const {entry,frm,frappe,handlers,context}=fixture();entry.dialog.$wrapper.is=()=>true;
 entry.items.set('A',{name:'A',custom_barcode:'MASTER-A'});
 frm.doc.items=[{item_code:'A'},{item_code:'B'}];
 const reads=[];
 frappe.db.get_list=async(_dt,options)=>{reads.push(options.filters.name[1]);return options.filters.name[1].map(name=>({name,custom_barcode:'DB-'+name}));};
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../public/js/forms/purchase_item_barcode.js'),'utf8'),context);
 await handlers['Purchase Receipt'].refresh(frm);
 assert.deepEqual(Array.from(reads[0]),['B']);
 assert.equal(frm.doc.items[0].custom_item_barcode,'MASTER-A');assert.equal(frm.doc.items[1].custom_item_barcode,'DB-B');
 entry.dialog.$wrapper.is=()=>false;
 await handlers['Purchase Receipt'].refresh(frm);
 assert.deepEqual(Array.from(reads[1]),['A','B']);assert.equal(frm.doc.items[0].custom_item_barcode,'DB-A');
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

for (const doctype of ['Purchase Receipt', 'Purchase Invoice']) test(`${doctype} Quick Entry runs native VAT handlers for taxable and zero-rated items`,async()=>{
 const {entry,frm,frappe,context}=fixture(doctype);await entry.add({item_code:'A'});
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

for (const updateStock of [0, 1]) {
 test(`PI quick entry uses invoice rows, native edits and preserves Update Stock=${updateStock} on Submit + New`,async()=>{
  const {entry,frm,handlers,created,context,changes}=fixture('Purchase Invoice',updateStock);
  assert.equal(entry.dialog.opts.title,'Quick Purchase Invoice');
  assert.equal(entry.dialog.get_field('update_stock').df.default,updateStock);
  assert.equal(entry.dialog.get_field('set_warehouse').df.reqd,Boolean(updateStock));
  await entry.add({item_code:'A',uom:'Nos'});
  await entry.add({item_code:'A',uom:'Nos'});
  assert.equal(frm.doc.items.length,1);assert.equal(frm.doc.items[0].qty,2);
  assert.equal(frm.doc.items[0].doctype,'Purchase Invoice Item');
  context.QuickReceipt.prototype.render.call(entry);
  for(const [field,value] of Object.entries({qty:4,custom_foc_qty:2,rate:10,custom_rate_including_vat:10.5,amount:40,custom_amount_including_vat:42})){
   const control=entry.rows.get(frm.doc.items[0].name).controls[field];control.value=value;control.df.onchange();await entry.queue;
   assert.ok(changes.some(change=>change.values[field]===value));
  }
  await entry.dialog.set_value('bill_no','INV-123');await entry.dialog.set_value('bill_date','2026-11-08');await entry.queue;
  assert.equal(frm.doc.bill_no,'INV-123');assert.equal(frm.doc.bill_date,'2026-11-08');
  await entry.save(true);frm.doc.docstatus=1;await handlers['Purchase Invoice'].on_submit(frm);
  assert.equal(created[0].dt,'Purchase Invoice');assert.equal(created[0].defaults.update_stock,updateStock);
  assert.equal(created[0].defaults.bill_no,undefined);assert.equal(created[0].defaults.supplier,undefined);
  assert.equal(context.frappe.flags.retail_new_pi_quick_entry,true);
  assert.equal(context.frappe.flags.retail_new_pr_quick_entry,undefined);
 });
}
test('PI Update Stock changes warehouse requirements and tracked columns through native header handler',async()=>{
 const {entry,frm,frappe,context}=fixture('Purchase Invoice');
 frm.doc.set_warehouse='';assert.equal(entry.required(),true);
 frappe.db.get_doc=async(_dt,name)=>({name,stock_uom:'Nos',has_serial_no:1});
 await entry.add({item_code:'Serial'});context.QuickReceipt.prototype.render.call(entry);
 assert.equal(entry.rows.get(frm.doc.items[0].name).controls.serial_no,undefined);
 await entry.dialog.set_value('update_stock',1);await entry.queue;
 assert.equal(frm.doc.update_stock,1);assert.equal(entry.required(),false);
 assert.equal(entry.dialog.get_field('set_warehouse').df.reqd,true);
 context.QuickReceipt.prototype.render.call(entry);
 assert.ok(entry.rows.get(frm.doc.items[0].name).controls.serial_no);
 await entry.dialog.set_value('update_stock',0);await entry.queue;
 context.QuickReceipt.prototype.render.call(entry);
 assert.equal(entry.rows.get(frm.doc.items[0].name).controls.serial_no,undefined);
 assert.equal(entry.required(),true);
});

test('Quick Entry settlement waits for the shared document VAT totals pipeline',async()=>{
 const {entry,context,frm}=fixture('Purchase Invoice');
 let finished=false;
 context.window.retail={transaction_items:{flushVatTaxRows:async target=>{
  assert.equal(target,frm);
  await new Promise(resolve=>setTimeout(resolve,10));
  frm.doc.total_taxes_and_charges=2;frm.doc.grand_total=42;finished=true;
 }}};
 await context.QuickReceipt.prototype.settle.call(entry);
 assert.equal(finished,true);assert.equal(frm.doc.grand_total,42);
});

test('PI without Update Stock merges repeated additions even when the header warehouse is unset',async()=>{
 const {entry,frm}=fixture('Purchase Invoice');delete frm.doc.set_warehouse;
 await entry.add({item_code:'A'});frm.doc.items[0].warehouse='';
 await entry.add({item_code:'A'});
 assert.equal(frm.doc.items.length,1);assert.equal(frm.doc.items[0].qty,2);
});

for (const updateStock of [0,1]) test(`PI scanner delegates packing identity and merges repeated scans with Update Stock=${updateStock}`,async()=>{
 const {entry,frm,frappe}=fixture('Purchase Invoice',updateStock);
 frappe.call=async request=>{assert.equal(request.method,'retail.domains.item.packing_scan.scan_barcode');return {message:{item_code:'A',uom:'Box-10',barcode:'PACK-10'}};};
 const scan=entry.dialog.get_field('scan');
 scan.$input.val('PACK-10');await entry.scan();scan.$input.val('PACK-10');await entry.scan();
 assert.equal(frm.doc.items.length,1);assert.equal(frm.doc.items[0].doctype,'Purchase Invoice Item');
 assert.equal(frm.doc.items[0].qty,2);assert.equal(frm.doc.items[0].uom,'Box-10');assert.equal(frm.doc.items[0].barcode,'PACK-10');
});

test('first Item bundles authorized master and zero-rate lookups into one request without changing row writes',async()=>{
 const {entry,frm,frappe,changes}=fixture();entry.dialog.$wrapper.is=()=>true;
 frappe.meta={has_field:()=>true};let synced;
 frappe.model.sync=doc=>{synced=doc;};
 const calls=[];
 frappe.call=async request=>{
  calls.push(request);
  assert.equal(request.method,'retail.domains.purchase.quick_entry.item_data');
  return {message:{item:{name:'A',stock_uom:'Nos',has_batch_no:1},lookups:[
   {method:'retail.domains.transactions.vat.get_transaction_item_vat_rate',args:{item_code:'A',child_doctype:'Purchase Receipt Item',parent_doctype:'Purchase Receipt',transaction_type:null,item_tax_template:null},message:0},
   {method:'retail.domains.purchase.selling_price.get_standard_selling_rate',args:{item_code:'A',uom:null},message:0},
   {method:'retail.domains.purchase.selling_price.get_standard_selling_rate',args:{item_code:'A',uom:'Box-10'},message:0},
   {method:'retail.domains.purchase.selling_price.get_item_selling_vat_rate',args:{item_code:'A'},message:0},
  ]}};
 };
 await entry.enqueue(()=>entry.add({item_code:'A',uom:'Box-10',barcode:'PACK'}));
 assert.equal(entry.failed,undefined);assert.equal(calls.length,1);
 assert.equal(synced.name,'A');
 const row=frm.doc.items[0];
 assert.equal(row.item_code,'A');assert.equal(row.uom,'Box-10');assert.equal(row.qty,1);
 assert.equal(row.barcode,'PACK');assert.equal(row.use_serial_batch_fields,1);
 assert.deepEqual(changes.map(c=>Object.keys(c.values)),[['item_code'],['uom'],['qty','warehouse']]);
 frappe.call=async()=>({message:5});
 await entry.enqueue(async()=>assert.equal((await entry.lookup({method:'retail.domains.transactions.vat.get_transaction_item_vat_rate',args:{item_code:'A',child_doctype:'Purchase Receipt Item',parent_doctype:'Purchase Receipt'}})).message,5));
});

test('denied bundled Item reads fail before a child row or field mutation is created',async()=>{
 const {entry,frm,frappe,changes}=fixture();entry.dialog.$wrapper.is=()=>true;
 frappe.call=async()=>{throw Error('Not permitted');};
 await entry.enqueue(()=>entry.add({item_code:'A'}));
 assert.equal(entry.failed,true);assert.equal(frm.doc.items.length,0);assert.equal(changes.length,0);
});

test('cached reads cannot let UOM writes finish ahead of native pricing callbacks',async()=>{
 const {entry,frm,frappe}=fixture();
 const row=frm.add_child('items');let nativeDone,finished=false;
 frappe.after_ajax=callback=>{nativeDone=callback;};
 const change=entry.setRowValue(row,'uom','Box-10').then(()=>{finished=true;});
 await new Promise(setImmediate);
 assert.equal(row.uom,'Box-10');assert.equal(finished,false);
 row.conversion_factor=10;row.rate=380;nativeDone();await change;
 assert.equal(finished,true);assert.equal(row.rate,380);assert.equal(row.conversion_factor,10);
});

for (const doctype of ['Purchase Receipt','Purchase Invoice']) {
 test(doctype+': packing inputs reach the native item handler on the first load',async()=>{
  const {entry,frm,frappe}=fixture(doctype);
  const original=frappe.model.set_value;
  let initialized;
  frappe.model.set_value=async(dt,name,field,value)=>{
   if(field==='item_code') {
    const row=frm.doc.items.find(row=>row.name===name);
    initialized={uom:row.uom,barcode:row.barcode};
    // The native item handler retains UOM for barcode entry and clears the barcode.
    if(!row.barcode)row.uom=null;
    row.barcode=null;
   }
   return original(dt,name,field,value);
  };
  await entry.add({item_code:'A',uom:'Box-10',barcode:'PACK-ALIAS'});
  assert.deepEqual(initialized,{uom:'Box-10',barcode:'PACK-ALIAS'});
  assert.equal(frm.doc.items[0].barcode,'PACK-ALIAS');
  assert.equal(frm.doc.items[0].uom,'Box-10');
  assert.equal(frm.doc.items[0].qty,1);
 });
}
