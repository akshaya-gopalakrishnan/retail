const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../public/js/forms/item.js'), 'utf8');
const doc = {name: 'SKU', custom_purchase_rate_entry: 10.5, custom_purchase_rate_includes_vat: 1,
    last_purchase_rate: 7, custom_average_purchase_rate: 6};
const frm = {doc, is_new: () => true, set_value: async values => Object.assign(doc,values)};
const fields = {entry:'custom_purchase_rate_entry', inclusive:'custom_purchase_rate_includes_vat',
    template:'custom_purchase_tax_template', base:'custom_default_purchase_rate', net:'custom_purchase_net_rate',
    vat:'custom_purchase_vat_amount', gross:'custom_purchase_gross_rate'};
const context = {flt: (v,p) => p === undefined ? Number(v)||0 : Number((Number(v)||0).toFixed(p)),
    cint: v => Number(v)||0, vatPriceFields: {purchase: fields},
    getTemplateVatRate: async () => 5, refreshMargin: async () => {},
    setValuesIfChanged: async (_doc,_dt,_name,values) => Object.assign(doc,values),
    frappe: {call: req => req.callback({message:{buying_rate:38,average_purchase_rate:99}}),
        model:{set_value: async (_dt,_name,values) => Object.assign(doc,values)}},
    packingVatFields: {purchase:{net:'purchase_net_rate',gross:'purchase_gross_rate'}},
    locals: {'Retail Packing Detail':{PACK:{conversion_factor:10,purchase_net_rate:100,purchase_gross_rate:105}}},
    refreshPackingVatRows: async () => {},
    Promise};
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('\tfunction calculateVatPrice('),
    source.indexOf('\tfunction addPackingVatButton(')),context);
vm.runInContext(source.slice(source.indexOf('\tfunction setLastPurchaseRateFromSameItemName('),
    source.indexOf('\tfunction clearFetchedItemPrices(')),context);
vm.runInContext(source.slice(source.indexOf('\tfunction updateItemRateFromPacking('),
    source.indexOf('\tfunction isPackingRowProgrammaticUpdate(')),context);
vm.runInContext(source.slice(source.indexOf('\tfunction getItemRateState('),
    source.indexOf('\tfunction getDefaultPackingVatMode(')),context);
(async () => {
    await context.calculateVatPrice(frm,'purchase');
    assert.equal(doc.custom_purchase_net_rate,10);
    assert.equal(doc.last_purchase_rate,7);
    assert.equal(doc.custom_average_purchase_rate,6);
    doc.custom_purchase_rate_entry=0;
    await context.calculateVatPrice(frm,'purchase');
    assert.equal(doc.custom_purchase_net_rate,0);
    assert.equal(context.getItemRateState(frm,'purchase').net,0);
    assert.equal(doc.last_purchase_rate,7);
    assert.equal(doc.custom_average_purchase_rate,6);
    doc.item_name='Product';
    context.setLastPurchaseRateFromSameItemName(frm,'Product');
    await Promise.resolve();
    assert.equal(doc.custom_default_purchase_rate,38);
    assert.equal(doc.last_purchase_rate,7);
    assert.equal(doc.custom_average_purchase_rate,6);
    await context.updateItemRateFromPacking(frm,'Retail Packing Detail','PACK','purchase','entry');
    assert.equal(doc.custom_purchase_net_rate,10);
    assert.equal(doc.last_purchase_rate,7);
    assert.equal(doc.custom_average_purchase_rate,6);
    console.log('PASS: positive/zero purchase entry and same-name lookup preserve historical rates');
})().catch(error => {console.error(error);process.exitCode=1;});
