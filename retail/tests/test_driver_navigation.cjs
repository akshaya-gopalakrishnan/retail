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
    'sidebarWorkspaceIsAllowed', 'workspaceIsAllowed', 'doctypeIsAllowed',
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
