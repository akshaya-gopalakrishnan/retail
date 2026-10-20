const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const rows = {};
const handlers = {};
let normalScans = 0, rpcScans = 0;
class Scanner {
  scan_api_call() { normalScans++; }
  update_table() { return 'normal'; }
}
const frappe = {
  provide() {},
  ui: {form: {on(dt, events) { handlers[dt] = events; }}},
  meta: {get_docfield() { return {}; }},
  model: {set_value: async (dt, name, key, value) => {
    Object.assign(rows[name], typeof key === 'string' ? {[key]: value} : key);
  }},
  throw(message) { throw Error(message); },
  call: async () => { rpcScans++; return {message: {item_code: 'ITEM'}}; },
};
const retail = {scale_sales: {}};
const erpnext = {utils: {BarcodeScanner: Scanner}};
vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname, '../public/js/scale_sales.js'), 'utf8'),
  {frappe, retail, window: {erpnext}, erpnext, document: {}, $: () => ({on() {}}),
   flt: value => Number(value) || 0, __: value => value});
const frm = {doc: {doctype: 'Sales Invoice', docstatus: 0},
  fields_dict: {items: {grid: {doctype: 'Sales Invoice Item'}}},
  cscript: {calculate_taxes_and_totals() {}}, refresh_field() {}};
async function check(label, rate, qty, expectedRate) {
  const row = rows.ROW = {name: 'ROW', doctype: 'Sales Invoice Item', rate};
  await retail.scale_sales.apply(frm, row, {...label, barcode: 'LABEL'});
  assert.equal(row.qty, qty);
  assert.equal(row.rate, expectedRate);
  assert.equal(row.discount_percentage, 0);
  assert.equal(row.barcode, 'LABEL');
}
(async () => {
  await check({scale_qty: 0.5, scale_rate: null, scale_amount: null}, 20, 0.5, 20);
  await check({scale_qty: 3, scale_rate: null, scale_amount: null}, 20, 3, 20);
  await check({scale_qty: null, scale_rate: null, scale_amount: 3050}, 20, 152.5, 20);
  await check({scale_qty: null, scale_rate: null, scale_amount: 30.5}, 0, 1, 30.5);
  await check({scale_qty: 0.5, scale_rate: 30.5, scale_amount: null}, 20, 0.5, 30.5);
  await check({scale_qty: 0.333, scale_rate: null, scale_amount: 30.5}, 20, 0.333, 30.5 / 0.333);
  frm.doc.is_return = 1;
  await check({scale_qty: 0.5, scale_rate: 30.5, scale_amount: null}, 20, -0.5, 30.5);
  const scanner = new Scanner();
  scanner.frm = {doc: {doctype: 'Purchase Invoice'}};
  scanner.scan_api_call('ANY', () => {});
  assert.equal(normalScans, 1);
  assert.equal(await scanner.update_table({}), 'normal');
  scanner.frm = frm;
  scanner.scan_api = 'erpnext.stock.utils.scan_barcode';
  await scanner.scan_api_call('9900002005007', () => {});
  assert.equal(rpcScans, 1);
  scanner.scan_api = 'custom.scan';
  scanner.scan_api_call('ANY', () => {});
  assert.equal(normalScans, 2, 'Custom scanner APIs retain their own behavior');
  const existing = {item_code: 'ITEM', name: 'EXISTING', qty: 2};
  const blank = rows.BLANK = {doctype: 'Sales Invoice Item', name: 'BLANK'};
  frm.doc.items = [existing, blank];
  frm.doc.is_return = 0;
  frm.script_manager = {async trigger() {}};
  scanner.items_table_name = 'items';
  scanner.set_warehouse = async () => {};
  scanner.clean_up = () => {};
  const added = await scanner.update_table({item_code: 'ITEM', scale_barcode_type: 'WEIGHT+UPRICE',
    scale_qty: 0.5, scale_rate: 30.5, scale_amount: null, uom: 'Kg', barcode: 'LABEL'});
  assert.equal(added, blank);
  assert.equal(existing.qty, 2, 'Scale label must not merge into an existing item row');
  assert.equal(blank.qty, 0.5);
  frm.doc.docstatus = 1;
  await assert.rejects(() => retail.scale_sales.apply(frm, rows.ROW, {}), /draft/);
  console.log('PASS: five sale types, large prices, zero-rate fallback, precision, returns, purchase fallback, submitted guard');
})().catch(error => {console.error(error); process.exitCode = 1;});
