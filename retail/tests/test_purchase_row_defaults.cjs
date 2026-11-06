const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function fixture(parent = 'Purchase Receipt') {
 const handlers = {}, calls = [], events = {};
 const row = {doctype: parent + ' Item', name: 'new-row', item_code: 'I-66', qty: 1, uom: 'Nos', rate: 10};
 const fields = ['custom_total_stock_qty','custom_cur_sell_rate','custom_new_sell_rate','custom_new_sell_incl',
  'custom_upd_sell_price','custom_sell_margin','custom_sell_margin_pct'];
 const frm = {doctype:parent,wrapper:{},doc:{docstatus:0,items:[row],custom_allow_selling_price:1},
  fields_dict:{items:{grid:{fields_map:Object.fromEntries(fields.map(field => [field, {fieldname:field}])),update_docfield_property(){}}}},
  refresh_field(){},add_custom_button(){}};
 const locals = {[row.doctype]:{[row.name]:row}};
 const frappe = {ui:{form:{on(dt,events){
  handlers[dt] ||= {};
  for(const [name,handler] of Object.entries(events)){
   const previous=handlers[dt][name];
   handlers[dt][name]=async(...args)=>{await previous?.(...args);return handler(...args);};
  }
 }}},
  meta:{has_field:(_dt,field)=>fields.includes(field)},
  async call(args){calls.push(args);return {message:args.method.endsWith('get_standard_selling_rate') ? (args.args.uom==='Box-10'?190.5:19.05) : 5};},
  model:{async set_value(dt,name,field,value){
   const values=typeof field==='string'?{[field]:value}:field;
   for(const [key,next] of Object.entries(values)) {
    if(locals[dt][name][key]===next)continue;
    locals[dt][name][key]=next;
    await handlers[dt]?.[key]?.(frm,dt,name);
   }
  }}};
 const context={frappe,locals,$:()=>({on:(name,handler)=>events[name]=handler}),flt:(v,p)=>p===undefined?(Number(v)||0):Number((Number(v)||0).toFixed(p)),__:(s)=>s};
 context.window=context;
 for(const name of ['foc_qty','purchase_selling_price'])vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../public/js/forms/'+name+'.js'),'utf8'),context);
 return {row,frm,frappe,handlers,calls,locals,events,trigger:key=>handlers[row.doctype][key](frm,row.doctype,row.name)};
}

for(const parent of ['Purchase Receipt','Purchase Invoice']) {
 test(parent+': new rows calculate Accepted Qty + FOC before any save',async()=>{
  const f=fixture(parent);
  assert.equal(f.row.custom_total_stock_qty,undefined);
  await f.trigger('item_code');
  // Both independently registered item-code handlers run in Desk.
  await f.handlers[parent].refresh(f.frm);
  assert.equal(f.row.custom_total_stock_qty,1);
  f.row.custom_foc_qty=2;await f.trigger('custom_foc_qty');
  assert.equal(f.row.custom_total_stock_qty,3);
  f.row.conversion_factor=10;await f.trigger('conversion_factor');
  assert.equal(f.row.custom_total_stock_qty,3);
  f.row.qty=4;await f.trigger('qty');assert.equal(f.row.custom_total_stock_qty,6);
 });
 test(parent+': fresh selling fields fetch the master price and VAT-inclusive value',async()=>{
  const f=fixture(parent);await f.trigger('item_code');
  assert.equal(f.row.custom_cur_sell_rate,19.05);
  assert.equal(f.row.custom_new_sell_incl,20);
  assert.equal(f.row.custom_sell_margin,9.05);
  assert.ok(!f.row.custom_upd_sell_price,'displaying the current price must not select a price update');
  f.row.uom='Box-10';await f.trigger('uom');
  assert.equal(f.row.custom_cur_sell_rate,190.5);
  assert.equal(f.row.custom_new_sell_incl,200.03);
 });
}

test('a stale selling lookup cannot overwrite a newer UOM lookup',async()=>{
 const f=fixture();let resolve,started;
 Object.assign(f.row,{custom_cur_sell_rate:0,custom_new_sell_rate:0,custom_new_sell_incl:0});
 const ready=new Promise(r=>started=r);
 f.frappe.call=async args=>args.method.endsWith('get_standard_selling_rate')&&args.args.uom==='Nos'
  ? new Promise(r=>{resolve=r;started();}) : {message:args.method.endsWith('get_standard_selling_rate')?190.5:5};
 const pending=f.trigger('item_code');await ready;f.row.uom='Box-10';await f.trigger('uom');
 resolve({message:19.05});await pending;await new Promise(setImmediate);
 assert.equal(f.row.custom_cur_sell_rate,190.5);assert.equal(f.row.custom_new_sell_incl,200.03);
});

test('submitted receipts retain their stored quantities and selling fields',async()=>{
 const f=fixture();f.frm.doc.docstatus=1;
 await f.trigger('qty');await f.trigger('item_code');
 assert.equal(f.row.custom_total_stock_qty,undefined);assert.equal(f.row.custom_cur_sell_rate,undefined);
 assert.equal(f.calls.length,0);
});

test('Item details assigning a default qty without a qty event still updates the displayed total',async()=>{
 const f=fixture();await f.handlers['Purchase Receipt'].refresh(f.frm);
 f.row.qty=0;f.row.custom_total_stock_qty=0;
 // Frappe synchronizes the child response directly, then renders the grid row.
 f.row.qty=1;
 f.events['grid-row-render.retailFocQty'](null,{doc:f.row,grid:f.frm.fields_dict.items.grid});
 await new Promise(setImmediate);
 assert.equal(f.row.custom_total_stock_qty,1);
});
