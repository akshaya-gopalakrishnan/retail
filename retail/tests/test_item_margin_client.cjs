const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../public/js/forms/item.js'), 'utf8');
const descriptions = [];
const frm = {doc: {name: 'Finished', custom_purchase_rate_entry: 0,
    custom_purchase_net_rate: 0, standard_rate: 7.14},
    _retail_stock_margin_cost: {cost: 1773.37 / 248, source: 'Stock valuation'},
    set_df_property: (...args) => descriptions.push(args)};
const context = {flt: (v, p) => p === undefined ? Number(v) || 0 : Number((Number(v) || 0).toFixed(p)),
    __: s => s, frappe: {model: {set_value: async (_dt, _name, values) => Object.assign(frm.doc, values)}}};
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('\tfunction loadStockMarginCost'),
    source.indexOf('\tfunction removeEmptyBarcodeRows')), context);
(async () => {
    await context.refreshMargin(frm);
    assert.equal(frm.doc.custom_margin, -0.01);
    assert.ok(frm.doc.custom_margin_ < 0);
    assert.match(descriptions.at(-1)[2], /Cost per stock unit/);
    frm.doc.custom_purchase_net_rate = 4;
    await context.refreshMargin(frm);
    assert.equal(frm.doc.custom_margin, 3.14);
    frm.doc.custom_purchase_net_rate = 0;
    frm._retail_stock_margin_cost = null;
    await context.refreshMargin(frm);
    assert.equal(frm.doc.custom_margin, null);
    assert.equal(frm.doc.custom_margin_, null);
    assert.match(descriptions.at(-1)[2], /Cost unavailable/);
    console.log('PASS: stock cost fallback, maintained purchase cost, unavailable margin');
})().catch(error => { console.error(error); process.exitCode = 1; });
