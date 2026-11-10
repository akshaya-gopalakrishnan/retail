const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function fixture(call) {
    const handlers = {};
    const timers = [];
    const calls = [];
    const awesome = {ul: {}, list: [], close() {}, get_item(value) { return this.list.find(row => row.value === value); }};
    let text = 'Search';
    const input = {0: {addEventListener() {}}, off() { return this; },
        on(event, fn) { handlers[event] = fn; return this; },
        is() { return true; }, val() { return text; }, trigger() { return this; }};
    const control = {awesomplete: awesome, $input: input, df: {only_select: true},
        set_custom_query() {}, get_reference_doctype() { return 'Purchase Receipt'; }};
    const window = {retail: {}};
    const context = {window, document: {getElementById() { return true; }}, locals: {},
        console, structuredClone, __: value => value,
        $() { return {addClass() {}}; },
        setTimeout(fn) { timers.push(fn); return timers.length; }, clearTimeout() {},
        frappe: {utils: {escape_html: String}, ui: {form: {on() {}}},
            async call(args) { calls.push(args.args); return call(args.args); }}};
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../public/js/forms/purchase_packing_search.js'), 'utf8'), context);
    window.retail.purchase_packing_search.bind(control, () => {});
    return {awesome, calls,
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
