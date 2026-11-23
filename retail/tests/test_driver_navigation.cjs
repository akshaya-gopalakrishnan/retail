const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../public/js/retail_navigation.js'), 'utf8');
const context = {
    frappe: { session: { user: 'driver@example.test' }, boot: {
        retail_sidebar_routes: JSON.parse(fs.readFileSync(path.join(__dirname, '../sidebar_routes.json'), 'utf8')),
        retail_sidebar_labels: JSON.parse(fs.readFileSync(path.join(__dirname, '../sidebar_labels.json'), 'utf8')),
    } },
    dynamicSidebarItems: new Map(),
};
// Load the real navigation mappings and gates without starting the DOM lifecycle.
const constants = source.slice(source.indexOf('    const DIRECT_MAPPING ='), source.indexOf('    function ', source.indexOf('    const DIRECT_MAPPING =')));
vm.runInNewContext(constants, context);
for (const name of ['getBlockedModules', 'moduleIsAllowed', 'getWorkspaceModule',
    'getCurrentUserRoles', 'getRoleAllowedSidebarWorkspaces', 'getSidebarGroup',
    'sidebarWorkspaceIsAllowed', 'workspaceIsAllowed', 'checklistTargetIsAllowed', 'doctypeIsAllowed',
    'routeIsAllowed', 'getSidebarTarget', 'sidebarItemIsAllowed', 'optionIsAllowed',
    'filterSearchResults', 'filterGlobalResultSets']) {
    const start = source.indexOf(`    function ${name}(`);
    const end = source.indexOf('\n    function ', start + 1);
    vm.runInNewContext(source.slice(start, end), context);
}
for (const canRead of [false, true]) {
    for (const enabled of [false, true]) {
        context.frappe.boot = {
            user: { can_read: canRead ? ['Driver', 'Van Fleet'] : [] },
            retail_module_access: { 'Van Sales': enabled },
            retail_blocked_modules: enabled ? [] : ['Van Sales'],
            retail_allowed_sidebar_workspaces: enabled ? ['Van Sales'] : [],
        };
        for (const view of ['List', 'Form', 'Tree']) {
            assert.equal(context.routeIsAllowed([view, 'Driver']), canRead);
        }
        assert.equal(context.filterSearchResults([{ match: 'Driver', route: ['List', 'Driver'] }]).length, Number(canRead));
        assert.equal(context.filterGlobalResultSets([{ title: 'Driver', results: [{ route: ['Form', 'Driver', 'DR-1'] }] }]).length, Number(canRead));
        assert.equal(context.sidebarItemIsAllowed({ name: 'Van Sales Driver Link' }), enabled && canRead);
        assert.equal(context.routeIsAllowed(['List', 'Van Fleet']), enabled && canRead);
    }
}
console.log('PASS: Driver ERP access/search is independent of Van Sales; sidebar visibility and other Van gates are preserved.');

// Server ownership mappings must win over old hard-coded storage modules.
context.frappe.boot = {
    retail_workspace_modules: {'POS': 'POS', 'POS Invoices': 'POS', 'Reports': '', 'Sales Invoices': 'Selling'},
    retail_module_access: {'POS': true},
    retail_blocked_modules: ['Accounts', 'POS', 'Selling'],
    retail_allowed_sidebar_workspaces: ['POS', 'Reports', 'Sales'],
    retail_sidebar_selection: ['pos', 'reports', 'sales', 'pos-invoices'],
    retail_sidebar_registry: [
        {id: 'pos', workspace: 'POS', children: [{id: 'pos-invoices', workspace: 'POS Invoices'}]},
        {id: 'reports', workspace: 'Reports', children: []},
        {id: 'sales', workspace: 'Sales', children: []},
        {id: 'accounts', workspace: 'Accounts', children: []},
    ],
};
assert.equal(context.getWorkspaceModule('POS Invoices'), 'POS');
assert.equal(context.getWorkspaceModule('Reports'), '');
for (const name of ['POS', 'POS Invoices', 'Reports', 'Sales Invoices']) {
    assert.equal(context.workspaceIsAllowed(name), true, name);
}
assert.equal(context.workspaceIsAllowed('Accounts'), false);
assert.equal(context.moduleIsAllowed('POS'), true);
context.frappe.boot.retail_module_access.POS = false;
assert.equal(context.moduleIsAllowed('POS'), false);
console.log('PASS: Explicit business-area choices override storage-module visibility without granting Accounts.');

// Unmapped accounting tools also have registry ownership. Test native New
// suggestions, which have no route, plus recent/tree and record results.
context.frappe.boot.user = {can_read: ['Account', 'Cost Center', 'Sales Invoice', 'POS Invoice']};
context.frappe.boot.retail_sidebar_registry.push({id: 'accounts', workspace: 'Accounts',
    targets: [['doctype', 'Account'], ['doctype', 'Cost Center']], children: []});
context.frappe.boot.retail_sidebar_registry[2].children.push({id: 'sales-invoices', workspace: 'Sales Invoices', targets: [['doctype', 'Sales Invoice']]});
context.frappe.boot.retail_sidebar_selection.push('sales-invoices');
for (const option of [
    {type: 'New', match: 'Account'},
    {match: 'Account', route: ['Tree', 'Account']},
    {route: ['Form', 'Cost Center', 'Main']},
]) assert.equal(context.optionIsAllowed(option), false);
assert.equal(context.optionIsAllowed({match: 'Sales Invoice', route: ['List', 'Sales Invoice']}), true);
assert.equal(context.filterGlobalResultSets([
    {title: 'Account', results: [{route: ['Form', 'Account', 'Cash']}]},
    {title: 'Sales Invoice', results: [{route: ['Form', 'Sales Invoice', 'SI-1']}]},
]).length, 1);
console.log('PASS: Accounting List/Tree/New/recent/global suggestions obey area ownership; Sales Invoice remains accessible.');

(context.frappe.boot.retail_sidebar_registry.find(group=>group.id==='accounts').targets ||= []).push(['dashboard','Accounts']);
context.frappe.boot.retail_sidebar_dashboard_access={'Accounts':false,'Accounting':false,'Finance Custom':false,'Selling':true};
for (const dashboard of ['Accounts','Accounting','Finance Custom']) {
    assert.equal(context.optionIsAllowed({type:'Dashboard',route:['dashboard-view',dashboard]}),false);
}
assert.equal(context.optionIsAllowed({type:'Dashboard',route:['dashboard-view','Selling']}),true);
assert.equal(context.filterSearchResults([
    {route:['dashboard-view','Accounts']}, {route:['dashboard-view','Selling']},
]).length,1);
console.log('PASS: Named accounting dashboards are hidden; permitted dashboards remain searchable.');
