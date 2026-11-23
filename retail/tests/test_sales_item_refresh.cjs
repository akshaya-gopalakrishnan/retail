const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../public/js/forms/sales_invoice.js','utf8');
const fn=source.slice(source.indexOf('\tfunction installItemRefreshBatching'),source.indexOf('\n\tfunction keepCompanyVisible'));
function fixture(status=0){
 let paints=0,calculations=0,id=0;const frames=new Map();
 const frm={doc:{docstatus:status},refresh_fields(){paints++},script_manager:{trigger(){calculations++;frm.refresh_fields();frm.refresh_fields();return Promise.resolve('native result')}}};
 const ctx={requestAnimationFrame:cb=>{frames.set(++id,cb);return id},cancelAnimationFrame:i=>frames.delete(i)};
 vm.createContext(ctx);vm.runInContext(fn+'\nthis.install=installItemRefreshBatching',ctx);ctx.install(frm);
 return {frm,frames,get paints(){return paints},get calculations(){return calculations}};
}
test('draft row handlers retain calculations and paint once before resolution',async()=>{
 const f=fixture();const result=f.frm.script_manager.trigger('rate','Sales Invoice Item','row');
 assert.equal(f.paints,0);assert.equal(f.frames.size,1);
 assert.equal(await result,'native result');assert.equal(f.paints,1);assert.equal(f.calculations,1);assert.equal(f.frames.size,0);
});
test('submitted invoices and ordinary refreshes remain immediate',async()=>{
 const f=fixture(1);await f.frm.script_manager.trigger('rate','Sales Invoice Item','row');assert.equal(f.paints,2);assert.equal(f.frames.size,0);
 const g=fixture();g.frm.refresh_fields();assert.equal(g.paints,1);
});
test('concurrent row chains share a final paint',async()=>{
 const f=fixture();await Promise.all([f.frm.script_manager.trigger('qty','Sales Invoice Item','a'),f.frm.script_manager.trigger('rate','Sales Invoice Item','b')]);
 assert.equal(f.calculations,2);assert.equal(f.paints,1);
});
