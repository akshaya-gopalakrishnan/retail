const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../public/js/sales_invoice_list.js'), 'utf8');
const setup = source.slice(source.indexOf('\tfunction setupInvoiceSourceView'), source.lastIndexOf('\n})();'));
for (const roles of [[], ['Sales Manager'], ['System Manager'], ['POS Manager']]) {
    const buttons = {};
    const context = { frappe: { user_roles: roles }, __: text => text };
    vm.runInNewContext(setup, context);
    const list = {
        get_filters_for_args: () => [['Sales Invoice', 'customer', '=', 'C-1'], ['Sales Invoice', 'is_consolidated', '=', 1]],
        page: { add_inner_button: (label, fn) => buttons[label] = fn, set_title: title => list.title = title },
        refresh: () => {},
    };
    context.setupInvoiceSourceView(list);
    assert.equal(list.get_filters_for_args().at(-1)[3], 0);
    assert.equal(list.get_filters_for_args()[0][1], 'customer');
    if (roles.includes('POS Manager')) {
        buttons['POS Invoices']();
        assert.equal(list.get_filters_for_args().at(-1)[3], 1);
        assert.equal(list.title, 'POS-generated Sales Invoices');
        assert.deepEqual(Object.keys(buttons), ['POS Invoices']);
        buttons['POS Invoices']();
        assert.equal(list.get_filters_for_args().at(-1)[3], 0);
        assert.equal(list.title, 'Sales Invoice');
        buttons['POS Invoices']();
        assert.equal(list.retail_reset_invoice_source(), true);
        assert.equal(list.get_filters_for_args().at(-1)[3], 0);
        context.frappe.user_roles = [];
        buttons['POS Invoices']();
        assert.equal(list.get_filters_for_args().at(-1)[3], 0);
    } else {
        assert.deepEqual(Object.keys(buttons), []);
        list.retail_pos_invoices = true;
        assert.equal(list.get_filters_for_args().at(-1)[3], 0);
    }
}
console.log('PASS: source filtering, exact role gating, and backend navigation reset');
