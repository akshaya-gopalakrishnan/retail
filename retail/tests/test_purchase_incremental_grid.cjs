const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../public/js/forms/transaction_items.js'), 'utf8');
const section = source.slice(source.indexOf('\tconst qtyKeepRateForms'), source.indexOf('\n\tfunction installPurchaseActionReads('));

function fixture(count = 100, paginated = false, doctype = 'Purchase Invoice') {
    const stats = {full: 0, cells: [], dependencies: [], layouts: 0};
    const names = ['item_code', 'item_name', 'uom', 'qty', 'rate', 'amount', 'barcode', 'warehouse'];
    const rows = Array.from({length: count}, (_, i) => ({name: 'row-' + i, idx: i + 1,
        item_code: 'SKU-' + i, item_name: 'Item ' + i, uom: 'Nos', qty: 1, rate: 10, amount: 10}));
    const grid = {docfields: names.map(fieldname => ({fieldname})), filter: {},
        visible_columns: names.map(fieldname => [{fieldname}, 1]), grid_rows: [], grid_rows_by_docname: {},
        refresh() {
            stats.full++;
            const start = grid.grid_pagination ? (grid.grid_pagination.page_index - 1) * 50 : 0;
            const visible = grid.grid_pagination ? rows.slice(start, start + 50) : rows;
            grid.grid_rows = visible.map(row => ({doc: row,
                refresh_field(key) { stats.cells.push([row.name, key, row[key]]); },
                refresh_dependency() { stats.dependencies.push(row.name); }}));
            grid.grid_rows_by_docname = Object.fromEntries(grid.grid_rows.map(row => [row.doc.name, row]));
        }};
    if (paginated) grid.grid_pagination = {page_index: 1, page_length: 50};
    grid.refresh(); stats.full = 0;
    grid.debounced_refresh = grid.refresh.bind(grid);
    const frm = {doc: {doctype, name: 'new-pi', docstatus: 0, items: rows},
        fields_dict: {items: {grid}}, refresh_field() { grid.refresh(); }};
    const context = vm.createContext({purchaseForms: ['Purchase Receipt', 'Purchase Invoice'],
        window: {frappe: {utils: {debounce: fn => fn}},
            retail: {scrollable_grid: {scheduleLayout() { stats.layouts++; }}}}});
    vm.runInContext(section, context);
    context.installPurchaseGridRefresh(frm);
    return {frm, grid, rows, stats};
}

test('100-row receipt refreshes only changed committed cells and native dependencies', () => {
    const {grid, rows, stats} = fixture();
    Object.assign(rows[50], {item_name: 'New name', uom: 'Box-10', rate: 25, amount: 25, barcode: 'BOX'});
    grid.refresh(); grid.refresh(); grid.refresh();
    assert.equal(stats.full, 0);
    assert.equal(stats.cells.length, 5);
    assert.ok(stats.cells.every(([name]) => name === 'row-50'));
    assert.deepEqual(stats.dependencies, ['row-50']);
    assert.equal(stats.layouts, 1);
});

test('cleared values repaint; changing item code refreshes its paired Item Name control', () => {
    const {grid, rows, stats} = fixture();
    Object.assign(rows[0], {item_code: 'NEW', rate: 0, amount: 0});
    grid.refresh();
    assert.ok(stats.cells.some(([, field, value]) => field === 'rate' && value === 0));
    assert.ok(stats.cells.some(([, field]) => field === 'item_name'));
});

test('metadata debounce uses the optimized refresh instead of its old bound callback', () => {
    const {grid, rows, stats} = fixture();
    rows[0].rate = 30;
    grid.debounced_refresh();
    assert.equal(stats.full, 0);
    assert.ok(stats.cells.some(([name, field, value]) => name === 'row-0' && field === 'rate' && value === 30));
});

test('100-row documents update the visible page without rebuilding for off-page rows', () => {
    const {grid, rows, stats} = fixture(100, true);
    rows[5].rate = 20; grid.refresh();
    assert.equal(stats.full, 0);
    assert.equal(stats.cells.length, 1);
    rows[70].rate = 30; grid.refresh();
    assert.equal(stats.full, 0);
    assert.equal(stats.cells.length, 1);
    grid.grid_pagination.page_index = 2; grid.refresh();
    assert.equal(stats.full, 1);
    assert.equal(grid.grid_rows[0].doc.name, 'row-50');
});

test('selection and table editability changes retain native toolbar/permission refresh', () => {
    const {grid, rows, stats} = fixture();
    rows[0].__checked = 1; grid.refresh(); assert.equal(stats.full, 1);
    grid.df = {read_only: 1}; grid.refresh(); assert.equal(stats.full, 2);
});

test('add/remove, column settings, filters and submitted records use native full refresh', () => {
    const {grid, frm, rows, stats} = fixture(2);
    rows.push({name: 'added', idx: 3}); grid.refresh();
    assert.equal(stats.full, 1);
    rows.pop(); grid.refresh(); assert.equal(stats.full, 2);
    grid.docfields[0].hidden = 1; grid.refresh(); assert.equal(stats.full, 3);
    grid.filter = {item_code: 'SKU'}; grid.refresh(); assert.equal(stats.full, 4);
    grid.filter = {}; frm.doc.docstatus = 1; grid.refresh(); assert.equal(stats.full, 5);
});

test('Quick Entry defers the hidden full-form grid and repaints it once on close', () => {
    const {grid, frm, rows, stats} = fixture();
    let visible = true, closed, listeners = 0;
    frm.__quick_receipt = {dialog: {$wrapper: {is() { return visible; },
        one(event, callback) { listeners++; closed = callback; }}}};
    rows.push({name: 'quick-added', idx: 101});
    grid.refresh(); grid.refresh(); grid.refresh();
    assert.equal(stats.full, 0); assert.equal(listeners, 1);
    visible = false; closed();
    assert.equal(stats.full, 1);
    assert.ok(grid.grid_rows_by_docname['quick-added']);
});

test('pagination holes do not abort an edit or the following save refresh', () => {
    const {grid, rows, stats} = fixture(100, true);
    grid.grid_pagination.page_index = 2;
    grid.refresh();
    assert.equal(stats.full, 1);
    const visible = grid.grid_rows[0];
    const sparse = [];
    sparse[50] = visible;
    grid.grid_rows = sparse;
    rows[50].rate = 44;
    grid.refresh();
    assert.equal(stats.full, 1);
    assert.ok(stats.cells.some(([name, field, value]) => name === 'row-50' && field === 'rate' && value === 44));
    rows.push({name: 'added', idx: 101, item_code: 'SKU-NEW', qty: 1, rate: 10, amount: 10});
    assert.doesNotThrow(() => grid.refresh());
    assert.equal(stats.full, 2);
});

test('Purchase Order and Sales Invoice keep the visible page editable after pagination holes', () => {
    for (const doctype of ['Purchase Order', 'Sales Invoice']) {
        const {grid, rows, stats} = fixture(100, true, doctype);
        grid.grid_pagination.page_index = 2;
        grid.refresh();
        const visible = grid.grid_rows[0];
        const sparse = [];
        sparse[50] = visible;
        grid.grid_rows = sparse;
        rows[50].rate = 18;
        assert.doesNotThrow(() => grid.refresh());
        assert.ok(stats.cells.some(([name, field, value]) => name === 'row-50' && field === 'rate' && value === 18), doctype);
    }
});
