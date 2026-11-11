const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../public/js/forms/item.js'),'utf8');
const row={name:'PACK',doctype:'Packing',conversion_factor:10,selling_rate:0,selling_net_rate:0};
const writes=[];
const context={flt:(v,p)=>p===undefined?Number(v)||0:Number((Number(v)||0).toFixed(p)),cint:v=>Number(v)||0,
    locals:{Packing:{PACK:row}},packingVatFields:{selling:{entry:'selling_rate',mode:'selling_vat_mode',
        net:'selling_net_rate',vat:'selling_vat_amount',gross:'selling_gross_rate'}},
    setPackingValuesWithoutReentry:async (_r,_dt,_name,values)=>{writes.push(values);Object.assign(row,values);}};
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('\tfunction setPackingRowFromItemRates('),
    source.indexOf('\tfunction updateItemRateFromPacking(')),context);
vm.runInContext(source.slice(source.indexOf('\tfunction getItemRateState('),
    source.indexOf('\tfunction setPackingMargin(')),context);
(async()=>{
    const frm={doc:{standard_rate:5,custom_sales_net_rate:5,custom_sales_gross_rate:5}};
    await context.setPackingRowFromItemRates(frm,'Packing','PACK','selling');
    assert.equal(row.selling_rate,0); // Refresh must preserve saved zero.
    row.__islocal=1;row.__retail_manual_selling_price=true;
    await context.setPackingRowFromItemRates(frm,'Packing','PACK','selling');
    assert.equal(row.selling_rate,0); // New manually cleared row also remains zero.
    delete row.__retail_manual_selling_price;
    await context.setPackingRowFromItemRates(frm,'Packing','PACK','selling');
    assert.equal(row.selling_rate,50); // New defaults still scale.
    frm.doc.standard_rate=frm.doc.custom_sales_net_rate=frm.doc.custom_sales_gross_rate=0;
    await context.setPackingRowFromItemRates(frm,'Packing','PACK','selling',true);
    assert.equal(row.selling_rate,0); // Explicit unit clear propagates through existing flow.
    console.log('PASS: saved/manual selling zeros survive refresh; defaults and explicit unit clear work');
})().catch(error=>{console.error(error);process.exitCode=1;});
