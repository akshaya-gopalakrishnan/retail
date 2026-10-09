const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../public/js/retail_navigation.js'), 'utf8');
let filters = [];
let savedFilters = [];
let refreshes = 0;
const customerFilter = ['Sales Invoice', 'customer', '=', 'Customer A'];
const returnFilter = ['Sales Invoice', 'is_return', '=', 1];
const list = {
    doctype: 'Sales Invoice',
    filter_area: {
        get: () => filters,
        remove: field => { filters = filters.filter(filter => filter[1] !== field); },
    },
    refresh() {
        refreshes++;
        savedFilters = filters.slice();
        context.window.location.search = filters.some(filter => filter[1] === 'is_return') ? '?is_return=1' : '';
        return Promise.resolve();
    },
};
const context = {
    window: { cur_list: list, location: { search: '' } },
    frappe: { route_options: null, get_route: () => ['List', 'Sales Invoice'] },
    $: { isPlainObject: value => value !== null && typeof value === 'object' && !Array.isArray(value) },
    getTargetUrl: target => '/app/' + target[1].toLowerCase().replaceAll(' ', '-') + (target[2] ? '?is_return=1' : ''),
    routeToUrl: async url => {
        context.window.location.pathname = url.split('?')[0];
        context.window.location.search = url.includes('?') ? '?' + url.split('?')[1] : '';
        // A newly opened list restores persisted filters before the route completes.
        if (context.window.cur_list !== list) filters = savedFilters.slice();
        context.window.cur_list = list;
        if (url.includes('is_return=1')) filters = [returnFilter];
    },
};
for (const name of ['clearListFilter', 'resetSalesInvoiceListFilters', 'clearSalesInvoiceListState',
    'normalizeSalesInvoiceListRoute', 'targetWithFilters', 'isVanSalesInvoiceWrapperRoute', 'routeToTarget']) {
    const start = source.indexOf(`    function ${name}(`);
    assert(start >= 0, name);
    const end = source.indexOf('\n    function ', start + 1);
    vm.runInNewContext(source.slice(start, end), context);
}
// A full-page override would bypass route completion and restore stale saved filters.
assert(!source.includes('forceSalesInvoiceContext'));
(async () => {
    filters = [customerFilter, returnFilter, ['Sales Invoice', 'custom_is_van_sale', '=', 1]];
    list.filters = filters.slice();
    await context.routeToTarget(['List', 'Sales Invoice']);
    assert.deepEqual(filters, [customerFilter]);
    assert.equal(context.window.location.search, '');
    for (let i = 0; i < 3; i++) {
        await context.routeToTarget(['List', 'Sales Invoice', { is_return: 1 }]);
        assert.deepEqual(filters, [returnFilter]);
        assert.equal(context.window.location.search, '?is_return=1');
        await context.routeToTarget(['List', 'Sales Invoice']);
        assert.deepEqual(filters, []);
        assert.equal(context.window.location.search, '');
    }
    context.window.cur_list = { doctype: 'Customer' };
    savedFilters = [customerFilter, returnFilter];
    await context.routeToTarget(['List', 'Sales Invoice']);
    assert.deepEqual(filters, [customerFilter]);
    assert.deepEqual(savedFilters, [customerFilter]);
    assert(refreshes > 0);
    console.log('PASS: repeated sales/returns switching and restored saved filters use in-app navigation.');
})().catch(error => { console.error(error); process.exitCode = 1; });
