const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function fixture(doctype='Purchase Receipt', writer) {
 const events=[], flags={trigger_from_barcode_scanner:false};
 const row={name:'row',uom:'Nos',qty:0};
 const frm={doc:{doctype,docstatus:0},cscript:{}};
 const scanner=frm.cscript.barcode_scanner={async set_barcode(target,barcode){
  events.push({method:'barcode',guard:flags.trigger_from_barcode_scanner,uom:target.uom,receiver:this});
  if(writer) await writer(target,barcode);target.barcode=barcode;
 },async update_table(data){
  events.push({method:'update',data,receiver:this});
  await this.set_barcode(row,data.barcode);
  events.push({method:'item',uom:row.uom});row.item_code=data.item_code;row.qty++;
  row.uom=data.uom;return row;
 }};
 const window={retail:{}};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../public/js/forms/purchase_packing_search.js'),'utf8'),
  {window,$:()=>({length:0}),frappe:{flags,ui:{form:{on(){}}}},document:{getElementById:()=>true},setTimeout,clearTimeout,console});
 const install=window.retail.purchase_packing_search.installScanner;
 install(frm);return {frm,scanner,row,events,flags,install,window};
}
for(const dt of ['Purchase Receipt','Purchase Invoice']) test(dt+': resolved packing enters native item handlers once with the selected UOM',async()=>{
 const f=fixture(dt), data={item_code:'A',barcode:'PACK',uom:'Box',serial_no:'SERIAL',batch_no:'BATCH'};
 const update=f.scanner.update_table;f.install(f.frm);assert.equal(f.scanner.update_table,update);
 assert.equal(await f.scanner.update_table(data),f.row);
 assert.equal(f.events[0].data,data,'Retain batch/serial data and native update');
 assert.equal(f.events[1].guard,false,'Native barcode handlers keep their original flags');assert.equal(f.events[2].uom,'Box');
 assert.equal(f.events[0].receiver,f.scanner);assert.equal(f.events[1].receiver,f.scanner);
 assert.equal(f.flags.trigger_from_barcode_scanner,false);assert.equal(f.row.qty,1);
 f.row.uom='Nos';await f.scanner.update_table(data);
 assert.equal(f.events[5].uom,'Nos','Existing row uses native UOM transition');assert.equal(f.row.qty,2);
 await f.scanner.set_barcode(f.row,'MANUAL');
 assert.equal(f.events.at(-1).guard,false,'No guard remains after the scan');
});
test('returns, internal suppliers and submitted documents retain native scanner behavior',async()=>{
 for(const values of [{is_return:1},{is_internal_supplier:1},{docstatus:1}]){
  const f=fixture();Object.assign(f.frm.doc,values);
  await f.scanner.update_table({item_code:'A',barcode:'PACK',uom:'Box'});
  assert.equal(f.events[1].guard,false);assert.equal(f.events[2].uom,'Nos');
 }
});
test('overlapping barcode writes run in order and preserve native scanner flags',async()=>{
 const finish=[], f=fixture('Purchase Receipt',()=>new Promise(resolve=>finish.push(resolve)));
 const a=f.scanner.update_table({item_code:'A',barcode:'ONE',uom:'Box'});
 const b=f.scanner.update_table({item_code:'A',barcode:'TWO',uom:'Box'});
 await Promise.resolve();assert.equal(finish.length,1,'Second scan waits for the first');
 finish[0]();await a;assert.equal(f.flags.trigger_from_barcode_scanner,false);
 finish[1]();await b;assert.equal(f.flags.trigger_from_barcode_scanner,false);
});
for(const dt of ['Purchase Receipt','Purchase Invoice']) test(dt+': five rapid scans increment the same row and restore barcode focus',async()=>{
 const f=fixture(dt,()=>new Promise(resolve=>setTimeout(resolve,2)));
 let focused=0;
 f.frm.fields_dict={scan_barcode:{set_focus(){focused++;}}};
 f.window.cur_frm=f.frm;
 const scans=Array.from({length:5},()=>f.scanner.update_table({item_code:'A',barcode:'PACK',uom:'Box'}));
 await Promise.all(scans);
 assert.equal(f.row.qty,5);assert.equal(f.frm.__retail_purchase_scan_active,false);assert.equal(focused,5);
});
test('barcode validation errors restore the input UOM and release scan state',async()=>{
 const f=fixture('Purchase Receipt',async()=>{throw new Error('invalid barcode');});
 await assert.rejects(f.scanner.update_table({item_code:'A',barcode:'PACK',uom:'Box'}),/invalid barcode/);
 assert.equal(f.row.uom,'Nos');assert.equal(f.flags.trigger_from_barcode_scanner,false);
 await assert.rejects(f.scanner.set_barcode(f.row,'PACK'),/invalid barcode/);
 assert.equal(f.events.at(-1).guard,false);
});
