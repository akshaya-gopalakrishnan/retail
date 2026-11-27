const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../public/js/forms/transaction_items.js'),'utf8');
const start=source.indexOf('\tfunction refreshRowVatAmounts(');
const end=source.indexOf('\n\tObject.keys(liveVatFormDoctypes)',start);
(async()=>{
 for(const type of ['Purchase Invoice','Purchase Receipt','Sales Invoice']){
  let next=0, properties=0, paints=0;
  const timers=new Map();const field={precision:2};
  const row={doctype:type+' Item',name:'r',item_code:'I',qty:2,rate:100,custom_vat_amount:0};
  const grid={docfields:[{fieldname:'custom_vat_amount',read_only:0}],update_docfield_property:(name,property,value)=>{properties++;grid.docfields[0][property]=value;},grid_rows_by_docname:{r:{refresh_field:()=>paints++}}};
  const frm={doc:{doctype:type,items:[row]},fields_dict:{items:{grid}}};
  const context={isCompletedPos:()=>false,getVatRate:async()=>5,flt:(v,p)=>p===undefined?Number(v)||0:Number(Number(v).toFixed(p)),cint:Number,frappe:{meta:{get_docfield:()=>field}},setTimeout:fn=>{timers.set(++next,fn);return next;},clearTimeout:id=>timers.delete(id)};
  vm.createContext(context);vm.runInContext(source.slice(start,end),context);
  for(let i=0;i<100;i++)context.refreshRowVatAmounts(frm);
  assert.equal(timers.size,1);
  const flush=async()=>{const callbacks=[...timers.values()];timers.clear();for(const cb of callbacks)cb();for(let i=0;i<10;i++)await Promise.resolve();};
  await flush();assert.equal(properties,1);assert.equal(paints,1);assert.equal(row.custom_vat_amount,10);
  context.refreshRowVatAmounts(frm);await flush();assert.equal(properties,1);assert.equal(paints,1);
  row.qty=3;context.refreshRowVatAmounts(frm);await flush();assert.equal(row.custom_vat_amount,15);assert.equal(paints,2);
 }
 console.log('PASS: 100 VAT display events coalesce, no repeated metadata/grid refresh, quantity VAT stays correct');
})().catch(e=>{console.error(e);process.exitCode=1;});
