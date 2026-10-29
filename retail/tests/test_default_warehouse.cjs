const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
function fixture(doctype='Purchase Invoice') {
 const handlers={},events={};
 const input={off(){return this;},on(name,fn){events[name]=fn;return this;}};
 const frappe={ui:{form:{on:(dt,h)=>handlers[dt]=h}},db:{
  get_single_value:async()=> 'Stores - CSSL',
  get_value:async()=>({message:{company:'CSSL',is_group:0,disabled:0}}),
 }};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../public/js/forms/default_warehouse.js'),'utf8'),{frappe});
 const frm={doctype,doc:{company:'CSSL',docstatus:0,update_stock:1},fields_dict:{set_warehouse:{$input:input}},is_new:()=>true,
  async set_value(field,value){this.doc[field]=value;handlers[doctype][field]?.(this);}};
 return {frm,frappe,handlers:handlers[doctype],events};
}

test('PI and PR fill valid defaults on refresh and preserve subsequent clearing',async()=>{
 for(const dt of ['Purchase Invoice','Purchase Receipt']){
  const f=fixture(dt);await f.handlers.refresh(f.frm);
  assert.equal(f.frm.doc.set_warehouse,'Stores - CSSL');
  await f.frm.set_value('set_warehouse',null);await f.handlers.refresh(f.frm);
  assert.equal(f.frm.doc.set_warehouse,null);
 }
});

test('an interrupted initialization can retry instead of consuming its one attempt',async()=>{
 const f=fixture();let resolve;
 f.frappe.db.get_single_value=()=>new Promise(r=>resolve=r);
 const pending=f.handlers.onload(f.frm);
 f.handlers.set_warehouse(f.frm); // Framework initialization clears an already-empty field.
 resolve('Stores - CSSL');await pending;
 assert.equal(f.frm.doc.set_warehouse,undefined);
 assert.equal(f.frm.__retail_warehouse_attempted,false);
 f.frappe.db.get_single_value=async()=> 'Stores - CSSL';
 await f.handlers.refresh(f.frm);
 assert.equal(f.frm.doc.set_warehouse,'Stores - CSSL');
});

test('a direct user edit while lookup is pending prevents automatic replacement',async()=>{
 const f=fixture();let resolve;
 f.frappe.db.get_single_value=()=>new Promise(r=>resolve=r);
 const pending=f.handlers.refresh(f.frm);
 f.events['input.retailDefaultWarehouse']({originalEvent:{}});
 resolve('Stores - CSSL');await pending;
 await f.handlers.refresh(f.frm);
 assert.equal(f.frm.doc.set_warehouse,undefined);
});

test('empty settings can be retried and concurrent events share one lookup',async()=>{
 const f=fixture();let resolve,calls=0;
 f.frappe.db.get_single_value=()=>{calls++;return new Promise(r=>resolve=r);};
 const pending=f.handlers.onload(f.frm);await f.handlers.refresh(f.frm);
 assert.equal(calls,1);resolve(null);await pending;
 f.frappe.db.get_single_value=async()=> 'Stores - CSSL';
 await f.handlers.refresh(f.frm);assert.equal(f.frm.doc.set_warehouse,'Stores - CSSL');
});

test('company, stock-update, submitted-state and existing-choice guards remain enforced',async()=>{
 const f=fixture();
 f.frm.doc.update_stock=0;await f.handlers.refresh(f.frm);assert.equal(f.frm.doc.set_warehouse,undefined);
 f.frm.doc.update_stock=1;f.frm.doc.company='OTHER';await f.handlers.company(f.frm);assert.equal(f.frm.doc.set_warehouse,undefined);
 f.frm.doc.company='CSSL';await f.handlers.company(f.frm);assert.equal(f.frm.doc.set_warehouse,'Stores - CSSL');
 const g=fixture();g.frm.doc.docstatus=1;await g.handlers.update_stock(g.frm);assert.equal(g.frm.doc.set_warehouse,undefined);
 const h=fixture();h.frm.doc.set_warehouse='User selection';await h.handlers.refresh(h.frm);assert.equal(h.frm.doc.set_warehouse,'User selection');
});
