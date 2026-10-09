const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const handlers = {};
const requests = [];
const context = {
    frappe: {
        ui: { form: { off() {}, on(dt, events) { Object.assign(handlers, events); } } },
        call(args) { return new Promise(resolve => requests.push({ args, resolve })); },
        throw(message) { throw new Error(message); },
    },
    cint: value => parseInt(value || 0, 10),
    flt: (value, places) => places === undefined ? Number(value || 0) : Number(Number(value || 0).toFixed(places)),
    precision: () => 2,
    __: (text, values = []) => text.replace(/\{(\d+)\}/g, (_, n) => values[n]),
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../public/js/forms/sales_invoice_loyalty.js'), 'utf8'), context);
function form() {
    return {
        fields_dict: { custom_available_loyalty_points: {} },
        doc: { name: 'new-invoice', customer: 'A', company: 'Company', loyalty_program: 'Program',
            posting_date: '2026-09-16', docstatus: 0, loyalty_points: 0, loyalty_amount: 0,
            grand_total: 100, disable_rounded_total: 1, conversion_rate: 1 },
        refresh_field() {}, set_df_property() {}, is_new: () => true,
        async set_value(field, value) {
            Object.assign(this.doc, typeof field === 'object' ? field : { [field]: value });
        },
    };
}
(async () => {
    const frm = form();
    const first = handlers.refresh(frm);
    assert.equal(requests[0].args.method, 'retail.loyalty.get_available_points');
    frm.doc.customer = 'B';
    const second = handlers.customer(frm);
    requests[1].resolve({ message: { available_points: 20, conversion_factor: 0.5 } });
    await second;
    requests[0].resolve({ message: { available_points: 999, conversion_factor: 10 } });
    await first;
    assert.equal(frm.doc.custom_available_loyalty_points, 20, 'stale customer response must be ignored');
    frm.doc.redeem_loyalty_points = 1;
    frm.doc.loyalty_points = 10;
    await handlers.loyalty_points(frm);
    assert.equal(frm.doc.loyalty_amount, 5);
    frm.doc.loyalty_points = 21;
    await assert.rejects(handlers.loyalty_points(frm), /between 0 and 20/);
    assert.equal(frm.doc.loyalty_amount, 0);
    frm.doc.redeem_loyalty_points = 0;
    await handlers.redeem_loyalty_points(frm);
    assert.equal(frm.doc.loyalty_points, 0);
    frm.doc.docstatus = 1;
    frm.doc.loyalty_amount = 5;
    const submitted = handlers.refresh(frm);
    requests.at(-1).resolve({ message: { available_points: 10, conversion_factor: 0.5 } });
    await submitted;
    assert.equal(frm.doc.loyalty_amount, 5, 'refresh must not rewrite submitted redemption');
    console.log('Client checks passed: secure lookup, stale response, amount, over-redemption, reset, submitted refresh.');
})().catch(error => { console.error(error); process.exitCode = 1; });
