const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function fixture(doctype = 'Purchase Receipt') {
 const handlers = {}, properties = {};let render;
 const masters = new Map([
  ['normal', {name:'normal',has_serial_no:0,has_batch_no:0}],
  ['serial', {name:'serial',has_serial_no:1,has_batch_no:0}],
  ['batch', {name:'batch',has_serial_no:0,has_batch_no:1}],
 ]);
 const frappe = {ui:{form:{on:(dt, events)=>handlers[dt]=events}},db:{
  get_list:async (_dt,args)=>args.filters.name[1].map(code=>masters.get(code)).filter(Boolean),
 }};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../public/js/forms/purchase_stock_identity.js'),'utf8'), {frappe,$:()=>({on:(_name,fn)=>render=fn})});
 const grid={fields_map:{},update_docfield_property:(field,key,value)=>(properties[field]||={})[key]=value, refresh(){}};
 const frm={doctype,doc:{items:[],update_stock:1},fields_dict:{items:{grid}}};
 const sharedColumns={serial_no:{fieldname:'serial_no'},batch_no:{fieldname:'batch_no'}};
 const gridRow=doc=>{
  const row={doc,grid,docfields:[{fieldname:'serial_no'},{fieldname:'batch_no'}],columns:{},row:{hasClass:()=>true},toggle_editable_row(){}};
  for(const field of ['serial_no','batch_no'])row.columns[field]={df:sharedColumns[field],field:{df:sharedColumns[field],refresh(){}},field_area:{toggle(){}},static_area:{toggle(){}}};
  render(null,row);return row;
 };
 const rowMetadata=doc=>Object.fromEntries(gridRow(doc).docfields.map(df=>[df.fieldname,df]));
 return {handlers,properties,masters,frappe,frm,rowMetadata,gridRow,sharedColumns};
}

test('empty and ordinary purchases hide both identity columns',async()=>{
 const f=fixture(); await f.handlers['Purchase Receipt'].refresh(f.frm);
 assert.equal(f.properties.serial_no.hidden,true);assert.equal(f.properties.batch_no.hidden,true);
 f.frm.doc.items=[{item_code:'normal'}];await f.handlers['Purchase Receipt Item'].item_code(f.frm);
 assert.equal(f.properties.serial_no.hidden,true);assert.equal(f.properties.batch_no.hidden,true);
});

test('mixed rows show shared headers but only applicable row inputs',async()=>{
 const f=fixture();f.frm.doc.items=['normal','serial','batch'].map(item_code=>({item_code}));
 await f.handlers['Purchase Receipt'].refresh(f.frm);
 assert.equal(f.properties.serial_no.hidden,false);assert.equal(f.properties.batch_no.hidden,false);
 for(const row of f.frm.doc.items){
  assert.equal(!f.rowMetadata(row).serial_no.hidden,row.item_code==='serial');
  assert.equal(!f.rowMetadata(row).batch_no.hidden,row.item_code==='batch');
 }
 f.frm.doc.items=f.frm.doc.items.filter(r=>r.item_code!=='serial');
 await f.handlers['Purchase Receipt Item'].items_remove(f.frm);
 assert.equal(f.properties.serial_no.hidden,true);assert.equal(f.properties.batch_no.hidden,false);
 assert.equal(f.rowMetadata({...f.frm.doc.items[1],serial_and_batch_bundle:'BUNDLE'}).batch_no.read_only,true);
});

test('PI requires stock updating and excludes fixed assets',async()=>{
 const f=fixture('Purchase Invoice');f.frm.doc.items=[{item_code:'serial'},{item_code:'batch',is_fixed_asset:1}];
 await f.handlers['Purchase Invoice'].refresh(f.frm);
 assert.equal(f.properties.serial_no.hidden,false);assert.equal(f.properties.batch_no.hidden,true);
 f.frm.doc.update_stock=0;await f.handlers['Purchase Invoice'].update_stock(f.frm);
 assert.equal(f.properties.serial_no.hidden,true);assert.equal(f.rowMetadata(f.frm.doc.items[0]).serial_no.hidden,true);
});

test('refresh rereads master flags without changing transaction values',async()=>{
 const f=fixture();f.frm.doc.items=[{item_code:'normal',serial_no:'KEEP',batch_no:'KEEP-BATCH'}];
 await f.handlers['Purchase Receipt'].refresh(f.frm);
 f.masters.get('normal').has_serial_no=1;
 await f.handlers['Purchase Receipt'].refresh(f.frm);
 assert.equal(f.properties.serial_no.hidden,false);
 assert.equal(f.frm.doc.items[0].serial_no,'KEEP');assert.equal(f.frm.doc.items[0].batch_no,'KEEP-BATCH');
});

test('late master lookup cannot restore columns for a previously selected item',async()=>{
 const f=fixture();let resolve;
 f.frappe.db.get_list=()=>new Promise(r=>resolve=r);
 f.frm.doc.items=[{item_code:'serial'}];const pending=f.handlers['Purchase Receipt'].refresh(f.frm);
 f.frm.doc.items=[];await f.handlers['Purchase Receipt Item'].items_remove(f.frm);
 resolve([{name:'serial',has_serial_no:1,has_batch_no:0}]);await pending;
 assert.equal(f.properties.serial_no.hidden,true);assert.equal(f.properties.batch_no.hidden,true);
});

test('saved-column metadata and controls are isolated between mixed rows',async()=>{
 const f=fixture();f.frm.doc.items=[{item_code:'serial'},{item_code:'batch'}];
 await f.handlers['Purchase Receipt'].refresh(f.frm);
 const serial=f.gridRow(f.frm.doc.items[0]);const batch=f.gridRow(f.frm.doc.items[1]);
 serial.toggle_editable_row(true);
 assert.equal(serial.columns.serial_no.field.df.hidden,false);
 assert.equal(serial.columns.batch_no.field.df.hidden,true);
 assert.equal(batch.columns.serial_no.field.df.hidden,true);
 assert.equal(batch.columns.batch_no.field.df.hidden,false);
 assert.notEqual(serial.columns.serial_no.df,batch.columns.serial_no.df);
 assert.equal(f.sharedColumns.serial_no.hidden,undefined);
});
