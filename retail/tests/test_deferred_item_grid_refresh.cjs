const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../public/js/forms/transaction_items.js'), 'utf8');
const section = source.slice(source.indexOf('\tconst heavyItemForms ='), source.indexOf('\n\tfunction installPurchaseActionReads('));

for (const doctype of ['Purchase Order', 'Purchase Invoice', 'Purchase Receipt', 'Sales Invoice']) {
    for (const mode of ['field', 'single', 'array']) {
        test(`${doctype}: deferred ${mode} refresh paints the existing row when totals finish`, async () => {
            const context = vm.createContext({});
            vm.runInContext(section, context);
            const row = {name: 'existing-row', item_code: 'SKU', item_name: '', uom: '', rate: 0};
            const visible = {};
            let refreshes = 0, finish;
            const field = {
                grid: {grid_rows: [], grid_rows_by_docname: {'existing-row': {refresh_field() {}}}},
                refresh() { refreshes++; Object.assign(visible, row); },
            };
            const frm = {
                doc: {doctype, items: [row]}, fields_dict: {items: field},
                refresh_field(name) { if (name === 'items' || Array.isArray(name) && name.includes('items')) field.refresh(); },
                cscript: {calculate_taxes_and_totals() {
                    Object.assign(row, {item_name: 'Primer', uom: 'Box-10', rate: 25});
                    if (mode === 'field') field.refresh();
                    if (mode === 'single') frm.refresh_field('items');
                    if (mode === 'array') frm.refresh_field(['items', 'taxes']);
                    return new Promise(resolve => { finish = resolve; });
                }},
            };
            context.installLightTotals(frm);
            const calculation = frm.cscript.calculate_taxes_and_totals();
            assert.equal(refreshes, 0, 'Do not rebuild the grid during totals');
            assert.equal(frm.doc.items.length, 1, 'No Add Row action');
            finish();
            await calculation;
            assert.equal(refreshes, 1, 'Replay the refresh once after totals');
            assert.equal(visible.item_name, 'Primer');
            assert.equal(visible.uom, 'Box-10');
            assert.equal(visible.rate, 25);
            assert.equal(frm.__retail_item_refresh_pending, undefined);
        });
    }
}

test('totals failure restores the grid and flushes its pending refresh', () => {
    const context = vm.createContext({});
    vm.runInContext(section, context);
    let refreshes = 0;
    const frm = {doc: {doctype: 'Purchase Invoice', items: []}, fields_dict: {items: {refresh() {}}},
        refresh_field() { refreshes++; }, cscript: {calculate_taxes_and_totals() {
            frm.refresh_field('items'); throw new Error('failed');
        }}};
    const original = frm.refresh_field;
    context.installLightTotals(frm);
    assert.throws(() => frm.cscript.calculate_taxes_and_totals(), /failed/);
    assert.equal(frm.refresh_field, original);
    assert.equal(refreshes, 1);
});
