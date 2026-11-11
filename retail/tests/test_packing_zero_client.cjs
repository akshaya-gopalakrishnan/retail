const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname,'../domains/item/packing_rate.py'),'utf8').split("'''")[1];
const row={purchase_rate:0,conversion_factor:10};
const frm={doc:{custom_default_purchase_rate:2,last_purchase_rate:38}};
const writes=[];
const context={flt:v=>Number(v)||0,locals:{Packing:{ROW:row}},frappe:{
    ui:{form:{on:()=>{}}},model:{set_value:(...args)=>writes.push(args)}}};
vm.createContext(context);
vm.runInContext(source,context);
context.set_default_packing_purchase_rate(frm,'Packing','ROW');
assert.equal(writes.length,0); // Saved zero packing must remain zero.
row.__islocal=1;
frm.doc.custom_default_purchase_rate=0;
context.set_default_packing_purchase_rate(frm,'Packing','ROW');
assert.equal(writes.length,0); // History must not refill a zero maintained rate.
frm.doc.custom_default_purchase_rate=2;
context.set_default_packing_purchase_rate(frm,'Packing','ROW');
assert.equal(writes[0][3],20); // Preserve defaulting for new packings.
console.log('PASS: saved packing zeros survive and new defaults never use historical cost');
