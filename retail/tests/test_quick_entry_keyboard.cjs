const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function fixture() {
 const frappe = { ui: { form: { QuickEntryForm: class {} } } };
 vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../public/js/forms/retail_quick_entry.js'), 'utf8'), { frappe, window: {}, setTimeout });
 const form = new frappe.ui.form.RetailQuickEntryForm();
 form.dialog = { working: false, get_primary_btn: () => ({ focus() {} }) };
 return form;
}
function field(x, y, onCommit = async () => {}) {
 const input = { focus() { input.focused = true; }, select() {}, getBoundingClientRect: () => ({ left: x, top: y, width: 100, height: 24 }) };
 return { $input: [input], get_input_value: () => 'edited', set_value: onCommit };
}
function event(key, target, ctrlKey = false) {
 return { key, target, ctrlKey, preventDefault() { this.prevented = true; }, stopImmediatePropagation() { this.stopped = true; } };
}

test('Enter commits before advancing and honors fields removed by dependencies', async () => {
 const form = fixture();
 let fields;
 const next = field(0, 80);
 const current = field(0, 0, async value => { assert.equal(value, 'edited'); fields = [current, next]; });
 fields = [current, field(0, 40), next];
 form.keyboard_fields = () => fields;
 await form.move_field(current, 'Enter');
 assert.ok(next.$input[0].focused);
});

test('arrows move spatially across both columns and within the current column', async () => {
 for (const [key, destination] of [['ArrowLeft', 0], ['ArrowRight', 2], ['ArrowUp', 3], ['ArrowDown', 4]]) {
  const form = fixture();
  const fields = [field(0,100), field(200,100), field(400,100), field(200,0), field(200,200)];
  form.keyboard_fields = () => fields;
  await form.move_field(fields[1], key);
  assert.ok(fields[destination].$input[0].focused, key);
 }
});

test('Ctrl+S commits the active value before saving and suppresses repeated saves', async () => {
 const form = fixture();
 let release;
 const order = [];
 const active = field(0, 0, () => new Promise(resolve => { order.push('commit'); release = resolve; }));
 form.keyboard_fields = () => [active];
 form.save_and_new = async () => { order.push('save'); };
 const first = event('s', active.$input[0], true);
 form.handle_key(first);
 form.handle_key(event('s', active.$input[0], true));
 assert.ok(first.prevented && first.stopped);
 assert.deepEqual(order, ['commit']);
 release();
 await new Promise(setImmediate);
 assert.deepEqual(order, ['commit', 'save']);
});

test('open link suggestions retain native up/down selection', () => {
 const form = fixture();
 const active = field(0, 0);
 active.awesomplete = { opened: true };
 form.keyboard_fields = () => [active];
 for (const key of ['ArrowUp', 'ArrowDown']) {
  const keyEvent = event(key, active.$input[0]);
  form.handle_key(keyEvent);
  assert.equal(keyEvent.prevented, undefined);
 }
});

test('Tab opens creation for the active link; Shift+Tab and ordinary fields retain normal focus', async () => {
 const form = fixture();
 const active = field(0, 0);
 active.df = { fieldtype: 'Link' };
 active.get_options = () => 'Brand';
 let opened = 0;
 active.new_doc = () => { opened++; };
 form.keyboard_fields = () => [active];
 // The vm tool checks the normal create permission before opening a popup.
 const permissionSource = fs.readFileSync(path.join(__dirname, '../public/js/forms/retail_quick_entry.js'), 'utf8');
 const frappe = {model:{can_create:()=>true},ui:{form:{QuickEntryForm:class {}}}};
 vm.runInNewContext(permissionSource, {frappe,window:{},setTimeout});
 Object.setPrototypeOf(form,frappe.ui.form.RetailQuickEntryForm.prototype);
 const tab=event('Tab',active.$input[0]);
 form.handle_key(tab);
 assert.ok(tab.prevented && tab.stopped);assert.equal(opened,1);
 await new Promise(setImmediate);
 const backwards=event('Tab',active.$input[0]);backwards.shiftKey=true;
 form.handle_key(backwards);assert.equal(backwards.prevented,undefined);
 active.df.fieldtype='Data';
 const normal=event('Tab',active.$input[0]);form.handle_key(normal);
 assert.equal(normal.prevented,undefined);assert.equal(opened,1);
});

test('Ctrl+Enter commits the active value and saves/closes instead of saving/new', async () => {
 const form=fixture();const order=[];
 const active=field(0,0,async()=>{order.push('commit');});
 form.keyboard_fields=()=>[active];
 form.save_and_close=async()=>{order.push('close');};
 form.save_and_new=async()=>{order.push('new');};
 const key=event('Enter',active.$input[0],true);
 form.handle_key(key);await new Promise(setImmediate);
 assert.ok(key.prevented && key.stopped);assert.deepEqual(order,['commit','close']);
});
