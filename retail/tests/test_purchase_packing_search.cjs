const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function fixture(call, options = {}) {
    const handlers = {};
    const timers = [];
    const calls = [];
    let nativeRemovedBeforeFocus = false;
    const awesome = {ul: {}, list: [], close() {}, get_item(value) { return this.list.find(row => row.value === value); }};
    let text = 'Search';
    const input = {0: {addEventListener() {}}, off(event) { if (event === "input" && !handlers["focus.retailSitePacking"]) nativeRemovedBeforeFocus = true; return this; },
        on(event, fn) { handlers[event] = fn; return this; },
        is() { return true; }, val() { return text; }, trigger() { return this; }};
    const control = {awesomplete: awesome, $input: input, df: {only_select: true, fieldtype: options.dynamic ? "Dynamic Link" : "Link", options: options.dynamic ? "quotation_to" : "Item"},
        set_custom_query() {}, get_reference_doctype() { return 'Purchase Receipt'; }};
    control.set_input = value => { text = value; };
    control.get_options = () => { if (options.dynamic) throw new Error('Dynamic Link context is not ready'); return 'Item'; };
    control.doc = options.row;
    control.df.fieldname = 'item_code';
    control.get_reference_doctype = () => options.parent || 'Purchase Receipt';
    control.set_value = async value => { if (control.doc) control.doc.item_code = value; };
    const updates = [];
    const window = {retail: {}};
    const context = {window, document: {getElementById() { return true; }}, locals: {},
        console, structuredClone, __: value => value,
        $() { return {addClass() {}}; },
        setTimeout(fn) { timers.push(fn); return timers.length; }, clearTimeout() {},
        frappe: {utils: {escape_html: String},
            meta: {has_field(dt, field) { return Object.hasOwn(options.row || {}, field); }},
            model: {async set_value(dt, name, field, value) { updates.push([field, value]); options.row[field] = value; }},
            ui: {form: {make_control: options => ({...options}), ControlLink: {prototype: {setup_awesomeplete() {}}}, on() {}}},
            async call(args) { calls.push(args.args); return call(args.args); }}};
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../public/js/forms/purchase_packing_search.js'), 'utf8'), context);
    if (options.global) {
        context.frappe.ui.form.ControlLink.prototype.setup_awesomeplete.call(control);
        handlers['focus.retailSitePacking']?.call(control);
    } else window.retail.purchase_packing_search.bind(control, () => {});
    return {awesome, calls, updates, nativeRemovedBeforeFocus, makeControl: options => context.frappe.ui.form.make_control(options),
        input(value) { text = value; handlers['input.retailPacking'](); timers.shift()(); },
        select(value) { handlers['awesomplete-select.retailPacking']({preventDefault() {}, originalEvent: {text: {value}}}); }};
}
const row = i => ({item_code: `SKU${i}`, packing_id: `PACK${i}`, item_name: 'Search'});
const flush = () => new Promise(resolve => setImmediate(resolve));

test('load-more fetches the next page and preserves every packing choice', async () => {
    const f = fixture(async args => ({message: Array.from({length: args.start ? 5 : 21}, (_, i) => row(args.start + i))}));
    f.input('Search'); await flush();
    assert.equal(f.awesome.list.filter(r => r.packing).length, 20);
    assert.equal(f.calls[0].page_length, 21);
    assert.ok(f.awesome.list.some(r => r.value === 'load_more__retail_packing'));
    f.select('load_more__retail_packing'); await flush();
    assert.equal(f.calls[1].start, 20);
    assert.equal(f.awesome.list.filter(r => r.packing).length, 25);
    assert.equal(new Set(f.awesome.list.map(r => r.value)).size, 25);
    assert.ok(!f.awesome.list.some(r => r.value === 'load_more__retail_packing'));
});

test('late previous-search response cannot replace current results', async () => {
    let oldResolve;
    const f = fixture(args => args.txt === 'Old'
        ? new Promise(resolve => { oldResolve = resolve; })
        : Promise.resolve({message: [row(99)]}));
    f.input('Old'); f.input('New'); await flush();
    oldResolve({message: [row(1)]}); await flush();
    assert.equal(f.awesome.list[0].packing.item_code, 'SKU99');
});


test('site-wide stock picker preserves native item selection and applies packing UOM and barcode', async () => {
    const line = {doctype: 'Stock Entry Detail', name: 'ROW', item_code: '', uom: 'Nos', barcode: ''};
    const packing = {...row(1), uom: 'Box-10', barcode: 'BOXBAR'};
    const f = fixture(async () => ({message: [packing]}), {global: true, parent: 'Stock Entry', row: line});
    f.input('Search'); await flush();
    assert.equal(f.calls[0].transaction_type, 'all');
    f.select(f.awesome.list[0].value); await flush();
    assert.equal(line.item_code, 'SKU1');
    assert.equal(line.uom, 'Box-10');
    assert.equal(line.barcode, 'BOXBAR');
    assert.deepEqual(f.updates, [['uom', 'Box-10'], ['barcode', 'BOXBAR']]);
});

test('site-wide selling picker uses sales eligibility', async () => {
    const f = fixture(async () => ({message: []}), {global: true, parent: 'Delivery Note'});
    f.input('Search'); await flush();
    assert.equal(f.calls[0].transaction_type, 'selling');
});


test('native row Item Name uses the filtered Item selector without changing stored metadata', () => {
    const f = fixture(async () => ({message: []}));
    const name = {fieldname: 'item_name', fieldtype: 'Data', label: 'Item Name'};
    const code = {fieldname: 'item_code', fieldtype: 'Link', options: 'Item'};
    const query = () => ({filters: {is_sales_item: 1}});
    const grid = {fields_map: {item_code: code}, get_field: () => ({get_query: query})};
    const field = f.makeControl({df: name, layout: {grid}});
    assert.equal(field.df.fieldname, 'item_code');
    assert.equal(field.df.options, 'Item');
    assert.equal(field.df.label, 'Item Name');
    assert.equal(field.is_title_link(), true);
    assert.deepEqual(field.get_query(), query());
    assert.equal(name.fieldtype, 'Data');
    assert.equal(name.fieldname, 'item_name');
    const readonly = {...name, read_only: 1};
    assert.equal(f.makeControl({df: readonly, grid}).df, readonly);
});


test('native debounced Item search is removed before the first focus can schedule it', () => {
    const f = fixture(async () => ({message: []}), {global: true, parent: 'Quotation'});
    assert.equal(f.nativeRemovedBeforeFocus, true);
});


test('Quotation dynamic customer filter is not evaluated during list construction', () => {
    const f = fixture(async () => ({message: []}), {global: true, parent: 'Quotation', dynamic: true});
    assert.equal(f.nativeRemovedBeforeFocus, false);
    assert.equal(f.calls.length, 0);
});
