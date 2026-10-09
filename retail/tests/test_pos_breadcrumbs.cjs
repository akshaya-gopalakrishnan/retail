const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../public/js/retail_navigation.js'), 'utf8');
const core = fs.readFileSync(path.join(__dirname, '../../../frappe/frappe/public/js/frappe/views/breadcrumbs.js'), 'utf8');
const context = { frappe: {}, localStorage: {}, __: s => s };
vm.runInNewContext(core, context);
const breadcrumbs = context.frappe.breadcrumbs;
const output = [];
context.frappe.visible_modules = ['Retail-app', 'Accounts'];
context.frappe.router = { slug: s => s.toLowerCase().replaceAll(' ', '-') };
context.frappe.boot = { module_wise_workspaces: { 'Retail-app': ['Promotions', 'POS'], Accounts: ['Accounts'] } };
context.frappe.get_module = module => ({ module });
context.frappe.route_history = [['Workspaces', 'Promotions'], ['List', 'POS Sync Log']];
breadcrumbs.append_breadcrumb_element = (route, label) => output.push({ route, label });
// Desk may load this bundle before its first route exists. Installation must
// never render breadcrumbs and interrupt the rest of sidebar initialization.
breadcrumbs.update = () => { throw new Error('Desk route is not initialized'); };
const start = source.indexOf('    function installPOSBreadcrumbs()');
const end = source.indexOf('\n    function init()', start);
vm.runInNewContext(source.slice(start, end), context);
// Reproduce the native shared-module fallback before applying the fix.
breadcrumbs.set_workspace_breadcrumb({ doctype: 'POS Sync Log', module: 'Retail-app' });
assert.equal(output.pop().label, 'Promotions');
context.installPOSBreadcrumbs();
const wrapper = breadcrumbs.set_workspace_breadcrumb;
context.installPOSBreadcrumbs();
assert.equal(breadcrumbs.set_workspace_breadcrumb, wrapper);
for (const doctype of ['POS Branch Counter', 'POS Cashier Shift', 'POS Counter Session', 'POS Closing Entry', 'POS Branch Day Closing', 'POS Sync Log']) {
    for (const workspace of [undefined, 'Promotions', 'Accounts']) {
        const entry = { doctype, module: doctype === 'POS Closing Entry' ? 'Accounts' : 'Retail-app', workspace };
        const before = JSON.stringify(entry);
        breadcrumbs.set_workspace_breadcrumb(entry);
        assert.equal(output.pop().route, '/app/pos');
        assert.equal(JSON.stringify(entry), before);
    }
}
for (const [doctype, module, expected] of [['Promo Price', 'Retail-app', 'Promotions'], ['Payment Entry', 'Accounts', 'Accounts']]) {
    breadcrumbs.set_workspace_breadcrumb({ doctype, module });
    assert.equal(output.pop().label, expected);
}
// Preserve native blocked-module behavior.
breadcrumbs.set_workspace_breadcrumb({ doctype: 'POS Sync Log', module_info: { module: 'Retail-app', blocked: true } });
assert.equal(output.length, 0);
// Run the real startup sequence with DOM helpers stubbed: the breadcrumb hook
// must allow icon, direct-link and submenu initialization to finish.
const initStart = source.indexOf('    function init()', start);
const initEnd = source.indexOf('\n    if (window.frappe?.ready)', initStart);
const initSource = source.slice(initStart, initEnd);
const startupCalls = [];
for (const match of initSource.matchAll(/^        (\w+)\(/gm)) {
    if (match[1] !== 'installPOSBreadcrumbs') {
        context[match[1]] = () => startupCalls.push(match[1]);
    }
}
context.window = { matchMedia: () => ({ addEventListener() {} }) };
context.DESKTOP_MEDIA = '(min-width: 992px)';
delete breadcrumbs.__retail_pos_installed;
vm.runInNewContext(initSource, context);
context.init();
for (const name of ['applyIcons', 'applyDirectLinks', 'renderPersistentSidebar', 'bindSubmenuRouting', 'bindMobileSidebarToggle']) {
    assert.ok(startupCalls.includes(name), `${name} must run during startup`);
}
console.log('PASS: six POS breadcrumbs, cached/history cases, unrelated pages, native gates and repeated installation.');
