const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../public/js/forms/purchase_history.js'), 'utf8');
const section = source.slice(source.indexOf('\tasync function refresh(frm)'), source.indexOf('\n\tfunction comparisonText('));

test('hidden purchase history resumes after Quick Entry closes without joining item-add requests', async () => {
    let visible = true, calls = 0, timer;
    const state = {generation: 1};
    const frm = {doc: {doctype: 'Purchase Invoice', company: 'Company', supplier: 'Supplier', items: [{name: 'row', item_code: 'SKU'}]},
        __quick_receipt: {dialog: {$wrapper: {is: () => visible}}}};
    const context = vm.createContext({setup: () => state, snapshot: () => frm.doc,
        render() {}, __: s => s, api: 'history.', setTimeout(fn) { timer = fn; },
        pacedParents: new Set(['Purchase Order', 'Purchase Receipt', 'Purchase Invoice']),
        frappe: {after_ajax: async () => {}, request: {ajax_count: 0}, async call() {
            calls++; return {message: {currency: 'AED', rows: [{row_name: 'row', current_rate: 10}]}};
        }}});
    vm.runInContext(section, context);
    await context.refresh(frm);
    assert.equal(calls, 0);
    assert.equal(typeof timer, 'function');
    visible = false;
    await timer();
    assert.equal(calls, 1);
    assert.equal(state.comparisons.row.current_rate, 10);
});
