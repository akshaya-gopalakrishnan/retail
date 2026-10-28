const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../public/js/retail_navigation.js'), 'utf8');
const start = source.indexOf('    function mountPersistentSidebar(section, items) {');
const end = source.indexOf('    function configureReportGroupAnchor', start);

function mount(route, desktop = true, display = 'none') {
 const classes = new Set(['hide-sidebar']);
 const host = {};
 const sidebar = { parentElement: host };
 const section = {
  classList: { remove: c => classes.delete(c), add: c => classes.add(c), contains: c => classes.has(c),
   toggle: (c, enabled) => enabled ? classes.add(c) : classes.delete(c) },
  style: { display, removeProperty(key) { this[key] = ''; } },
  closest: () => section, querySelectorAll: () => [sidebar],
 };
 vm.runInNewContext(source.slice(start, end) + '\nmountPersistentSidebar(section, []);', {
  section, getRetailSidebarHost: () => host, isDesktop: () => desktop,
  frappe: { get_route: () => route },
 });
 return { section, classes };
}

test('desktop form remount preserves native collapsed and expanded display', () => {
 for (const doctype of ['Item', 'Purchase Invoice', 'POS Operator Privilege']) {
  for (const display of ['none', 'block', '']) {
   const { section, classes } = mount(['Form', doctype, 'TEST'], true, display);
   assert.equal(section.style.display, display);
   assert.equal(classes.has('hide-sidebar'), false, 'new forms still get navigation');
   assert.equal(classes.has('retail-form-navigation'), true);
   assert.equal(classes.has('retail-form-sidebar-mounted'), true);
  }
 }
});

test('mobile form visibility and special privilege list behavior are preserved', () => {
 const mobile = mount(['Form', 'Item', 'TEST'], false);
 assert.equal(mobile.section.style.display, 'none');
 assert.equal(mobile.classes.has('hide-sidebar'), true);
 const list = mount(['List', 'POS Operator Privilege']);
 assert.equal(list.section.style.display, '');
 assert.equal(list.classes.has('hide-sidebar'), false);
});
