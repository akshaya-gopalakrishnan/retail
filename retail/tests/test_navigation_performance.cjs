const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

test('navigation ignores content mutations but handles sidebar mounts and changes', () => {
    const source = fs.readFileSync(path.join(__dirname, '../public/js/retail_navigation.js'), 'utf8');
    const start = source.indexOf('    function observeSidebarChanges() {');
    const end = source.indexOf('    function scheduleRetry()', start);
    let callback;
    let refreshes = 0;
    class Element {
        constructor({ sidebar = false, containsSidebar = false, tabs = false } = {}) {
            Object.assign(this, { sidebar, containsSidebar, tabs });
        }
        closest(selector) { return (selector === '.retail-open-work' ? this.tabs : this.sidebar) ? this : null; }
        matches() { return this.sidebar; }
        querySelector() { return this.containsSidebar ? this : null; }
    }
    vm.runInNewContext(source.slice(start, end) + '\nobserveSidebarChanges();', {
        Element, document: { body: {} }, debugLog() {},
        scheduleSidebarEnhancements() { refreshes++; },
        MutationObserver: class { constructor(fn) { callback = fn; } observe() {} },
    });
    const mutation = (target, node) => ({ target, addedNodes: [node], removedNodes: [] });
    callback([mutation(new Element(), new Element())]);
    assert.equal(refreshes, 0, 'ordinary grid/dialog changes do not refresh navigation');
    callback([mutation(new Element({ tabs: true, sidebar: true }), new Element())]);
    assert.equal(refreshes, 0, 'work-tab updates do not refresh navigation');
    callback([mutation(new Element({ sidebar: true }), new Element())]);
    assert.equal(refreshes, 1);
    callback([mutation(new Element(), new Element({ containsSidebar: true }))]);
    assert.equal(refreshes, 2, 'new page sidebar mounts are detected');
});

test('inner sidebar reuses filtered boot and shares concurrent fallback requests', async () => {
    const source = fs.readFileSync(path.join(__dirname, '../public/js/retail_navigation.js'), 'utf8');
    const start = source.indexOf('    function getSidebarItems() {');
    const end = source.indexOf('    function renderPersistentSidebar()', start);
    let calls = 0;
    let resolve;
    const bootPages = [{ name: 'permitted' }];
    const context = vm.createContext({
        frappe: { boot: { retail_workspace_sidebar_groups: {}, allowed_workspaces: bootPages },
            xcall() { calls++; return new Promise(r => { resolve = r; }); } },
        ensureVanSalesSidebarChildren: items => items,
        ensureBusinessHomeSidebarItem: items => items,
        registerSidebarItems() {},
    });
    vm.runInContext('let sidebarItemsCache = null; let sidebarItemsPromise = null; let useBootSidebarItems = true; let sidebarItemsGeneration = 0;\n' + source.slice(start, end), context);
    assert.equal(await vm.runInContext('getSidebarItems()', context), bootPages);
    assert.equal(calls, 0);
    assert.equal(await vm.runInContext('getSidebarItems()', context), bootPages);
    vm.runInContext('sidebarItemsCache = null; useBootSidebarItems = false;', context);
    const first = vm.runInContext('getSidebarItems()', context);
    const second = vm.runInContext('getSidebarItems()', context);
    assert.equal(first, second);
    assert.equal(calls, 1);
    const freshPages = [{ name: 'freshly-permitted' }];
    resolve({ pages: freshPages });
    assert.equal(await first, freshPages);
    assert.equal(await vm.runInContext('getSidebarItems()', context), freshPages);
    vm.runInContext('sidebarItemsCache = null;', context);
    const obsolete = vm.runInContext('getSidebarItems()', context);
    const resolveObsolete = resolve;
    vm.runInContext('sidebarItemsGeneration++; sidebarItemsCache = null; sidebarItemsPromise = null;', context);
    const latest = vm.runInContext('getSidebarItems()', context);
    resolveObsolete({ pages: bootPages });
    await obsolete;
    assert.equal(vm.runInContext('sidebarItemsCache', context), null, 'old route cannot refill cache');
    assert.equal(vm.runInContext('sidebarItemsPromise', context), latest, 'old route cannot clear pending request');
    resolve({ pages: freshPages });
    assert.equal(await latest, freshPages);
});
