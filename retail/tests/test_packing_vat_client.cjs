const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const handlers = {};
const cdt = 'Retail Packing Detail';
const row = {doctype: cdt, name: 'ROW', conversion_factor: 1, packing_margin: 0};
const frm = {doc: {doctype: "Item", name: "ITEM", custom_tax: 'VAT5', custom_purchase_tax_template: 'VAT5', custom_retail_packing_detail: [row]}, fields_dict: {},
 set_value: async values => Object.assign(frm.doc, values), refresh_field() {}};
const locals = {[cdt]: {ROW: row}, Item: {ITEM: frm.doc}};
const flt = (v, p) => p === undefined ? Number(v) || 0 : Number((Number(v) || 0).toFixed(p));
let writes = 0;
const frappe = {ui: {form: {on: (dt, events) => handlers[dt] = {...handlers[dt], ...events}}},
 call: async () => ({message: frm.doc.custom_tax === 'ZERO' ? 0 : 5}),
 model: {set_value: async (dt, name, field, value) => {
  assert.ok(++writes < 200, 'Recursive VAT updates');
  const doc = locals[dt][name];
  for (const [key, val] of Object.entries(typeof field === 'string' ? {[field]: value} : field)) {
   if (doc[key] === val) continue;
   doc[key] = val;
   await handlers[dt]?.[key]?.(frm, dt, name);
  }
 }}};
vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname, '../public/js/forms/item.js'), 'utf8'),
 {window: {frappe}, frappe, locals, flt, cint: v => Number(v) || 0, __: s => s, setTimeout});
(async () => {
 for (const side of ['selling', 'purchase']) {
  for (const [source, amount, mode] of [['rate', 100, 'Excluding VAT'], ['gross_rate', 105, 'Excluding VAT'], ['net_rate', 100, 'Including VAT']]) {
   writes = 0;
   Object.assign(row, {[`${side}_vat_confirmed`]: 1, [`${side}_vat_rate`]: 0, [`${side}_vat_mode`]: mode, [`${side}_${source}`]: amount});
   await handlers[cdt][`${side}_${source}`](frm, cdt, 'ROW');
   assert.equal(row[`${side}_net_rate`], 100);
   assert.equal(row[`${side}_gross_rate`], 105);
   assert.equal(row[`${side}_vat_rate`], 5);
  }
 }
 frm.doc.custom_tax = 'ZERO';
 row.selling_gross_rate = 105;
 writes = 0;
 await handlers[cdt].selling_gross_rate(frm, cdt, 'ROW');
 assert.equal(row.selling_net_rate, 105);
 assert.equal(row.selling_vat_rate, 0);
 frm.doc.custom_tax = 'VAT5';
 frm.doc.custom_sales_rate_includes_vat = 1;
 frm.doc.custom_sales_rate_entry = 105;
 row.conversion_factor = 12;
 writes = 0;
 await handlers.Item.custom_sales_rate_entry(frm);
 assert.equal(row.selling_net_rate, 1200);
 assert.equal(row.selling_gross_rate, 1260);
 assert.equal(frm.doc.custom_sales_net_rate, 100);
 frm.doc.custom_sales_rate_entry = 0;
 writes = 0;
 await handlers.Item.custom_sales_rate_entry(frm);
 assert.equal(row.selling_net_rate, 0);
 assert.equal(row.selling_gross_rate, 0);
 // New packing rows must finish initialization before their factor is edited.
 Object.assign(frm.doc, {item_code: 'I-42', item_name: 'Pendrive', custom_tax: 'ZERO',
  custom_purchase_tax_template: 'ZERO', custom_sales_net_rate: 15, custom_sales_gross_rate: 15,
  custom_purchase_net_rate: 10, custom_purchase_gross_rate: 10});
 Object.assign(row, {selling_rate: 0, purchase_rate: 0, conversion_factor: 0, uom: ''});
 writes = 0;
 await handlers[cdt].custom_retail_packing_detail_add(frm, cdt, 'ROW');
 row.uom = 'Box';
 await handlers[cdt].uom(frm, cdt, 'ROW');
 row.conversion_factor = 24;
 await handlers[cdt].conversion_factor(frm, cdt, 'ROW');
 assert.equal(row.purchase_net_rate, 240);
 assert.equal(row.purchase_gross_rate, 240);
 assert.equal(row.selling_net_rate, 360);
 assert.equal(row.selling_gross_rate, 360);
 Object.assign(frm.doc, {custom_tax: 'VAT5', custom_sales_net_rate: 428.57, custom_sales_gross_rate: 450});
 for (const [factor, gross, net] of [[12, 5400, 5142.86], [2, 900, 857.14], [50, 22500, 21428.57]]) {
  Object.assign(row, {__islocal: 1, __retail_manual_selling_price: false, selling_rate: 450,
   selling_vat_mode: 'Including VAT', conversion_factor: factor});
  writes = 0;
  await handlers[cdt].custom_retail_packing_detail_add(frm, cdt, 'ROW');
  assert.equal(row.selling_gross_rate, gross);
  assert.equal(row.selling_net_rate, net);
 }
 console.log('PASS: purchase/selling entry, inclusive, exclusive, zero-rated template, and event reentry');
})().catch(e => {console.error(e); process.exitCode = 1;});
