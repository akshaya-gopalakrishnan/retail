const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function fixture() {
	let handlers;
	const requests = [], dialogs = [], routes = [], buttons = new Map();
	const frappe = {
		ui: {form: {on: (_doctype, events) => { handlers = events; }}},
		utils: {escape_html: value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]))},
		datetime: {get_today: () => '2026-11-06', add_days: () => '2026-08-08', str_to_user: value => value},
		router: {slug: value => value.toLowerCase().replaceAll(' ', '-')},
		call: args => new Promise((resolve, reject) => requests.push({args, resolve, reject})),
		set_route: (...args) => routes.push(args),
	};
	frappe.ui.Dialog = class {
		constructor(options) {
			this.options = options;
			this.fields_dict = {review: {$wrapper: {html: value => { this.html = value; }}}};
			this.months = '12'; this.visible = false; dialogs.push(this);
		}
		show() { this.visible = true; }
		hide() { this.visible = false; }
		get_value() { return this.months; }
	};
	vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../public/js/forms/payment_entry.js'), 'utf8'),
		{window: {frappe}, frappe, __: value => value});
	const frm = {
		doc: {payment_type:'Receive', party_type:'Customer', party:'C-1', company:'nesto'},
		remove_custom_button: label => buttons.delete(label),
		add_custom_button: (label, callback) => buttons.set(label, callback),
	};
	return {frm, handlers, buttons, requests, dialogs, routes};
}

function result(name='Customer') {
	return {
		customer:'C-1', customer_name:name, company:'nesto', currency:'AED', as_of:'2026-11-06', from_date:'2025-11-06',
		snapshot:{credit_limit:1000, outstanding:100, commitments:0, credit_exposure:100, available_credit:900,
			overdue:100, oldest_overdue_days:6, unallocated_receipts:0, unused_credit_notes:0,
			ageing:{'1_30':100,'31_60':0,'61_90':0,over_90:0}},
		statistics:{due_terms:1, paid_on_time:0, paid_late:0, overdue_unpaid:1, excluded_terms:0, on_time_percent:0},
		trends:[], invoices:[], payments:[], invoice_count:0, payment_count:0,
	};
}
const flush = () => new Promise(resolve => setImmediate(resolve));

test('customer and supplier review buttons follow all party/payment combinations', () => {
	const f = fixture();
	for (const payment_type of ['Pay','Receive','Internal Transfer']) {
		for (const party_type of ['Supplier','Customer','Employee','']) {
			for (const party of ['PARTY','']) {
				Object.assign(f.frm.doc, {payment_type,party_type,party});
				f.handlers.refresh(f.frm);
				assert.equal(f.buttons.has('Customer Payment Review'), payment_type==='Receive' && party_type==='Customer' && !!party);
				assert.equal(f.buttons.has('View Supplier Stock'), payment_type==='Pay' && party_type==='Supplier' && !!party);
			}
		}
	}
});

test('opening the review uses the selected company/customer and does not modify the payment', async () => {
	const f = fixture(), before = JSON.stringify(f.frm.doc);
	f.handlers.refresh(f.frm); f.buttons.get('Customer Payment Review')();
	assert.deepEqual(JSON.parse(JSON.stringify(f.requests[0].args.args)), {customer:'C-1',company:'nesto',months:'12'});
	f.requests[0].resolve({message:result()}); await flush();
	assert.match(f.dialogs[0].html, /Payment behaviour/);
	assert.equal(f.dialogs[0].options.title, 'Customer Payment Review');
	assert.equal(JSON.stringify(f.frm.doc), before);
});

test('changing the party or company closes an existing review and rejects stale replies', async () => {
	for (const [field,value] of [['party','C-2'],['company','Another'],['payment_type','Pay'],['party_type','Supplier']]) {
		const f = fixture(); f.handlers.refresh(f.frm); f.buttons.get('Customer Payment Review')();
		f.frm.doc[field] = value; f.handlers[field](f.frm);
		assert.equal(f.dialogs[0].visible, false);
		f.requests[0].resolve({message:result('Stale result')}); await flush();
		assert.doesNotMatch(f.dialogs[0].html, /Stale result/);
	}
});

test('changing the review period ignores earlier requests and escapes displayed values', async () => {
	const f = fixture(); f.handlers.refresh(f.frm); f.buttons.get('Customer Payment Review')();
	const dialog = f.dialogs[0]; dialog.months = '3'; dialog.options.fields[0].onchange();
	assert.equal(f.requests[1].args.args.months,'3');
	f.requests[1].resolve({message:result('<img src=x onerror=alert(1)>')}); await flush();
	assert.match(dialog.html, /&lt;img/); assert.doesNotMatch(dialog.html, /<img/);
	f.requests[0].resolve({message:result('Stale result')}); await flush();
	assert.doesNotMatch(dialog.html, /Stale result/);
});

test('failed requests expose a retry message and preserve the payment', async () => {
	const f = fixture(), before = JSON.stringify(f.frm.doc);
	f.handlers.refresh(f.frm); f.buttons.get('Customer Payment Review')();
	f.requests[0].reject(new Error('denied')); await flush();
	assert.match(f.dialogs[0].html, /accounting permissions or try Refresh/);
	assert.equal(JSON.stringify(f.frm.doc), before);
});

test('supplier stock routing remains intact after adding the customer review', () => {
	const f = fixture(); Object.assign(f.frm.doc,{payment_type:'Pay',party_type:'Supplier',party:'S-2'});
	f.handlers.refresh(f.frm); f.buttons.get('View Supplier Stock')();
	assert.equal(f.routes[0][1],'Slow Moving Items');
	assert.equal(f.routes[0][2].supplier,'S-2');
	assert.equal(f.routes[0][2].company,'nesto');
	assert.equal(f.requests.length,0);
});
