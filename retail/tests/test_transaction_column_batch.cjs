const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../public/js/forms/transaction_items.js'),'utf8');
const fn=source.slice(source.indexOf('\tfunction installColumnDisplayBatch('),source.indexOf('\n\tfunction installPurchaseGridRefresh('));
function fixture(fail=false){
 let paints=0;const values=[];
 const grid={refresh(){assert.equal(this,grid);paints++;}};
 const frm={cscript:{toggle_item_grid_columns(currency){assert.equal(this,frm.cscript);for(let i=0;i<8;i++){values.push([i,currency]);grid.refresh();}if(fail)throw Error('native');return 'native-result';}}};
 const context={};vm.createContext(context);vm.runInContext(fn,context);
 const refresh=grid.refresh;context.installColumnDisplayBatch(frm,grid);const toggle=frm.cscript.toggle_item_grid_columns;
 context.installColumnDisplayBatch(frm,grid);assert.equal(toggle,frm.cscript.toggle_item_grid_columns);
 return {frm,grid,refresh,values,paints:()=>paints};
}
test('all native currency column operations finish before one grid paint',()=>{
 const f=fixture();assert.equal(f.frm.cscript.toggle_item_grid_columns('AED'),'native-result');
 assert.equal(f.values.length,8);assert.equal(f.paints(),1);assert.equal(f.grid.refresh,f.refresh);
});
test('native errors still propagate and restore grid refresh',()=>{
 const f=fixture(true);assert.throws(()=>f.frm.cscript.toggle_item_grid_columns('AED'),/native/);
 assert.equal(f.grid.refresh,f.refresh);assert.equal(f.paints(),1);
});
