const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../public/js/forms/transaction_items.js'), 'utf8');
const flt = (v, p) => p === undefined ? Number(v) || 0 : Number((Number(v) || 0).toFixed(p));

async function main() {
 const timers = [];
 const handlers = {};
 const locals = {};
 let vat = 5;
 const writes = [];
 const frappe = {ui: {form: {}}, meta: {get_docfield: () => ({precision: 2})},
  call: async () => ({message: vat}),
  model: {set_value: async (dt, name, field, value) => {writes.push({field, value}); locals[dt][name][field] = value;}}};
 const window = {frappe};
 vm.runInNewContext(source, {window, frappe, locals, flt, cint: flt,
  setTimeout: fn => timers.push(fn), clearTimeout() {}, __: s => s});
 assert.equal(window.__retail_transaction_items_registered, undefined, 'Wait for form.on, not just form namespace');
 frappe.ui.form.on = (dt, events) => {
  handlers[dt] ||= {};
  for (const [event, handler] of Object.entries(events)) (handlers[dt][event] ||= []).push(handler);
 };
 timers.shift()();
 assert.equal(window.__retail_transaction_items_registered, true);
 const flush = async () => {for (let i = 0; i < 30; i++) await Promise.resolve();};
 for (const dt of Object.keys(handlers).filter(dt => dt.endsWith(' Item'))) {
  const row = {doctype: dt, name: 'ROW', item_code: 'ITEM', qty: 2, rate: 100, amount: 200, net_amount: 0,
   custom_rate_including_vat: 0, custom_amount_including_vat: 0};
  locals[dt] = {ROW: row};
  let vatReadOnly;
  const grid = {update_docfield_property: (field, property, value) => {
   if (field === 'custom_vat_amount' && property === 'read_only') vatReadOnly = value;
  }};
  const frm = {doc: {doctype: dt.slice(0, -5), docstatus: 0, items: [row], taxes: [{rate: 5}]}, fields_dict: {items: {grid}}};
  const trigger = async event => {for (const fn of handlers[dt][event]) await fn(frm, dt, 'ROW'); await flush();};
  vat = 5;
  await trigger('rate');
  assert.equal(row.custom_rate_including_vat, 105, dt);
  assert.equal(row.custom_amount_including_vat, 210, dt);
  assert.equal(row.custom_vat_amount, 10, dt);
  await trigger('net_amount');
  assert.equal(row.custom_vat_amount, 10, `${dt}: stale net amount must not overwrite row VAT`);
  await handlers[frm.doc.doctype].refresh[0](frm);
  assert.equal(row.custom_vat_amount, 10, `${dt}: refresh uses qty and rate`);
  assert.equal(vatReadOnly, 1, `${dt}: VAT column remains read-only`);
  row.custom_rate_including_vat = 210;
  await trigger('custom_rate_including_vat');
  assert.equal(row.rate, 200, dt);
  assert.equal(row.amount, 400, dt);
  assert.equal(row.custom_vat_amount, 20, dt);
  row.custom_amount_including_vat = 630;
  await trigger('custom_amount_including_vat');
  assert.equal(row.rate, 300, dt);
  row.amount = 200;
  await trigger('amount');
  assert.equal(row.rate, 100, dt);
  row.qty = 3;
  await trigger('qty');
  assert.equal(row.custom_amount_including_vat, 315, dt);
  assert.equal(row.custom_vat_amount, 15, dt);
  row.qty = -3;
  await trigger('qty');
  assert.equal(row.custom_vat_amount, -15, dt);
  vat = 0;
  await trigger('item_tax_template');
  assert.equal(row.custom_rate_including_vat, 100, `${dt}: zero template overrides form tax`);
  row.rate = 0;
  await trigger('rate');
  assert.equal(row.amount, 0, dt);
  assert.equal(row.custom_rate_including_vat, 0, dt);
  assert.equal(row.custom_amount_including_vat, 0, dt);
  assert.equal(row.custom_vat_amount, 0, dt);
 }
 // Automatic refreshes must never invoke ERPNext's rate-change discount handler.
 const dt = 'Sales Invoice Item';
 const row = {doctype: dt, name: 'RACE', item_code: 'I-43', qty: 1,
  price_list_rate: 4.76, discount_amount: 0, discount_percentage: 0,
  custom_rate_including_vat: 0, custom_amount_including_vat: 0};
 locals[dt].RACE = row;
 const frm = {doc: {doctype: 'Sales Invoice', docstatus: 0, items: [row]}, fields_dict: {}};
 for (const event of ['item_code', 'price_list_rate', 'rate', 'qty', 'item_tax_template', 'tax_rate']) {
  writes.length = 0;
  for (const handler of handlers[dt][event]) await handler(frm, dt, row.name);
  await flush();
  assert.equal(writes.some(write => write.field === 'rate'), false, event + ': no synthetic rate event');
  assert.equal(row.rate, undefined, event + ': loading rate stays unset');
  assert.equal(row.discount_amount, 0);
 }
 // A slow VAT lookup must not overwrite a rate supplied by item details.
 let resolveVat;
 frappe.call = () => new Promise(resolve => {resolveVat = resolve;});
 handlers[dt].item_code[0](frm, dt, row.name);
 Object.assign(row, {rate: 100, price_list_rate: 100, discount_amount: 0});
 writes.length = 0;
 resolveVat({message: 5});
 await flush();
 assert.equal(row.rate, 100);
 assert.equal(row.custom_rate_including_vat, 105);
 assert.equal(row.discount_amount, 0);
 assert.equal(writes.some(write => write.field === 'rate'), false);
 // Preserve an intentional discount; VAT synchronization is not pricing policy.
 frappe.call = async () => ({message: 5});
 Object.assign(row, {rate: 95, price_list_rate: 100, discount_amount: 5, discount_percentage: 5});
 handlers[dt].rate[0](frm, dt, row.name);
 await flush();
 assert.equal(row.rate, 95);
 assert.equal(row.discount_amount, 5);
 assert.equal(row.discount_percentage, 5);
 assert.equal(row.custom_rate_including_vat, 99.75);
 console.log('PASS: automatic VAT refreshes cannot create discounts, slow lookup preserves pricing, intentional discounts remain');
 console.log('PASS: delayed form loading and VAT rates/amounts, quantity, zero-rated and zero-price rows across 14 transaction item types');
}
main().catch(error => {console.error(error); process.exitCode = 1;});
