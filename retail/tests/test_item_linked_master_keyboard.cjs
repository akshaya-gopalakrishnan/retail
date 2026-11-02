const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function fixture() {
	const source = fs.readFileSync(path.join(__dirname, '../public/js/forms/item.js'), 'utf8');
	let handler, hidden, saved, calls = 0, focus = 0;
	const oldEntry = {}, oldLink = {};
	const fields = Object.fromEntries(['item_group', 'brand', 'item_name'].map(name => [name, {
		df: {}, $input: Object.assign([{}], { focus: () => focus++ }),
		get_options: () => name === 'brand' ? 'Brand' : 'Item Group',
		get_label_value: () => 'Typed name',
		set_value: async value => { fields[name].value = value; },
		awesomplete: { close() {} },
	}]));
	const frappe = {
		quick_entry: oldEntry, _from_link: oldLink, model: { can_create: () => true },
		ui: { form: { make_quick_entry: (doctype, afterInsert, init, doc, force) => {
			calls++;
			assert.equal(force, true);
			assert.equal(frappe.route_options.name_field, 'Typed name');
			assert.equal(frappe._from_link, null);
			saved = afterInsert;
			frappe.quick_entry = {};
			init({ $wrapper: { one: (event, fn) => { hidden = fn; } } });
			return Promise.resolve();
		} } },
	};
	// Frappe Form.wrapper is a DOM element; only Form.$wrapper is jQuery.
	const frm = { fields_dict: fields, wrapper: { addEventListener: (name, fn, capture) => {
		assert.equal(capture, true); handler = fn;
	} } };
	const context = { frappe, setTimeout, console };
	vm.createContext(context);
	vm.runInContext(source.slice(source.indexOf('\tfunction setupLinkedMasterKeyboard'),
		source.indexOf('\tfunction setupSaveAndNew')), context);
	context.setupLinkedMasterKeyboard(frm);
	return { fields, frappe, frm, oldEntry, oldLink,
		event: (name, extra = {}) => {
			const event = { key: 'Tab', target: fields[name].$input[0],
				preventDefault() { this.prevented = true; }, stopImmediatePropagation() {}, ...extra };
			handler(event); return event;
		},
		save: value => saved({ name: value }), close: () => hidden(),
		calls: () => calls, focus: () => focus,
	};
}

for (const name of ['item_group', 'brand']) {
	test(`Tab creates ${name}, selects saved value and restores focus/context`, async () => {
		const f = fixture();
		assert.equal(f.event(name).prevented, true);
		f.event(name); // Repeated keys must not open a second popup.
		assert.equal(f.calls(), 1);
		await f.save('Created record');
		assert.equal(f.fields[name].value, 'Created record');
		f.close();
		assert.equal(f.focus(), 1);
		assert.equal(f.frappe.quick_entry, f.oldEntry);
		assert.equal(f.frappe._from_link, f.oldLink);
		assert.equal(f.frm._retail_creating_linked_master, false);
	});
}

test('Cancel restores focus without changing the current value', () => {
	const f = fixture();
	f.fields.brand.value = 'Existing';
	f.event('brand'); f.close();
	assert.equal(f.fields.brand.value, 'Existing');
	assert.equal(f.focus(), 1);
});

test('Normal navigation, permissions and read-only controls are respected', () => {
	const f = fixture();
	for (const extra of [{ shiftKey: true }, { ctrlKey: true }, { metaKey: true },
		{ altKey: true }, { isComposing: true }, { key: 'Enter' }]) {
		assert.equal(f.event('brand', extra).prevented, undefined);
	}
	assert.equal(f.event('item_name').prevented, undefined);
	f.frappe.model.can_create = () => false;
	assert.equal(f.event('brand').prevented, undefined);
	f.frappe.model.can_create = () => true;
	f.fields.brand.df.read_only = true;
	assert.equal(f.event('brand').prevented, undefined);
	f.fields.item_group.df.only_select = true;
	assert.equal(f.event('item_group').prevented, undefined);
	assert.equal(f.calls(), 0);
});
