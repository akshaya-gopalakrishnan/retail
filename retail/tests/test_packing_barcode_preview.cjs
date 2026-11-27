const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../public/js/forms/item.js'), 'utf8');
const start = source.indexOf('\tfunction previewPackingBarcode(');
const end = source.indexOf('\n\tfunction getAutoPackingName', start);
const rows = [{packing_uom: 'Box', conversion_factor: 10}, {packing_uom: 'Carton', conversion_factor: 20}];
const calls = [];
const context = {flt: v => Number(v) || 0, locals: {Packing: {a: rows[0], b: rows[1]}}, frappe: {
 call: async ({args}) => { const used = JSON.parse(args.excluded); calls.push(used); return {message: used.includes('first') ? 'second' : 'first'}; },
 model: {set_value: async (cdt, cdn, field, value) => {context.locals[cdt][cdn][field] = value;}}
}};
vm.createContext(context);
vm.runInContext(source.slice(start, end), context);
(async () => {
 const frm = {doc: {custom_barcode: 'master', custom_retail_packing_detail: rows}};
 await Promise.all([context.previewPackingBarcode(frm, 'Packing', 'a'), context.previewPackingBarcode(frm, 'Packing', 'b')]);
 assert.deepEqual(rows.map(r => r.barcode), ['first', 'second']);
 assert.ok(calls[1].includes('first'));
 rows[0].barcode = 'edited';
 await context.previewPackingBarcode(frm, 'Packing', 'a');
 assert.equal(rows[0].barcode, 'edited');
 assert.equal(calls.length, 2);
 const c = {packing_uom: 'Pack', conversion_factor: 0};
 context.locals.Packing.c = c;
 rows.push(c);
 await context.previewPackingBarcode(frm, 'Packing', 'c');
 assert.equal(calls.length, 2);
 console.log('PASS: distinct queued previews, editable barcode preservation, positive factor required');
})().catch(error => {console.error(error); process.exitCode = 1;});
