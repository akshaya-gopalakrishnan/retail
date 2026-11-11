const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

for (const doctype of ['Purchase Receipt', 'Purchase Invoice']) test(doctype + ': barcode metadata shares the active Item bundle with a native fallback', async () => {
 const handlers={}, calls=[];
 let prepared={name:'A',custom_barcode:''};
 const row={item_code:'A',barcode:'PACKING',qty:3,rate:12};
 const frm={doc:{doctype,items:[row]},__retail_purchase_action:{},refresh_field(){}};
 const frappe={ui:{form:{on(dt,events){handlers[dt]=events;}}},db:{async get_list(dt,args){calls.push(args);return [{name:'A',custom_barcode:'MASTER'}];}}};
 const window={retail:{transaction_items:{preparedPurchaseItem:async()=>prepared}}};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../public/js/forms/purchase_item_barcode.js'),'utf8'),{window,frappe});
 await handlers[doctype+' Item'].item_code(frm);
 assert.equal(calls.length,0,'A recorded empty master barcode still avoids a duplicate read');
 assert.equal(row.custom_item_barcode,'');
 prepared={name:'A'};
 await handlers[doctype+' Item'].item_code(frm);
 assert.equal(calls.length,1,'Missing fields require the native permission-aware read');
 assert.equal(row.custom_item_barcode,'MASTER');
 assert.equal(row.barcode,'PACKING');assert.equal(row.qty,3);assert.equal(row.rate,12);
 delete frm.__retail_purchase_action;
 await handlers[doctype].refresh(frm);
 assert.equal(calls.length,2,'Ordinary refresh rereads master values');
});
