const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../public/js/forms/transaction_items.js'),'utf8');
const fn=source.slice(source.indexOf('\tfunction replaceManagedVatTaxRows('),source.indexOf('\n\tasync function runErpnextTotals('));
function fixture(){
 let added=0,removed=0;
 const context={liveVatFormDoctypes:{'Sales Invoice':'VAT'},isManagedVatTaxRow:r=>r.description==='VAT',
 frappe:{meta:{get_docfield:(_dt,field)=>!['category','add_deduct_tax'].includes(field)},model:{clear_doc(){removed++;}}},refreshTaxTable(){}};
 vm.createContext(context);vm.runInContext(fn,context);
 const row={name:'saved-tax',doctype:'Sales Taxes and Charges',description:'VAT',account_head:'VAT Account',rate:5,cost_center:null};
 const frm={doc:{doctype:'Sales Invoice',taxes:[row]},add_child(){added++;const r={};this.doc.taxes.push(r);return r;}};
 return {context,frm,row,counts:()=>({added,removed})};
}
test('identical saved VAT rows retain identity without dirtying the form',()=>{
 const f=fixture();
 f.context.replaceManagedVatTaxRows(f.frm,[{description:'VAT',account_head:'VAT Account',rate:5,cost_center:'',category:'Total',add_deduct_tax:'Add'}]);
 assert.equal(f.frm.doc.taxes[0],f.row);assert.deepEqual(f.counts(),{added:0,removed:0});
});
test('changed VAT configuration still replaces managed rows and preserves other taxes',()=>{
 const f=fixture();const other={description:'Freight'};f.frm.doc.taxes.push(other);
 f.context.replaceManagedVatTaxRows(f.frm,[{description:'VAT',account_head:'VAT Account',rate:10}]);
 assert.deepEqual(f.counts(),{added:1,removed:1});assert.equal(f.frm.doc.taxes[0],other);
 assert.equal(f.frm.doc.taxes[1].rate,10);
});
