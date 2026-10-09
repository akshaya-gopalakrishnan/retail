const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

test('CDN lazy assets retry locally and execute in requested order', async () => {
    const remote = 'https://assets.example.com/r/assets/retail/test.bundle.js';
    const css = 'https://assets.example.com/r/assets/retail/style.bundle.css';
    const calls = [], evaluated = [];
    let frozen = 0;
    const frappe = {
        boot: { retail_cdn_local_assets: { [remote]: '/assets/retail/test.bundle.js', [css]: '/assets/retail/style.bundle.css' } },
        require() { throw new Error('unexpected original loader'); },
        assets: {
            bundled_asset: p => p,
            extn: p => p.split('.').at(-1),
            eval_assets: (p, body) => evaluated.push([p, body]),
        },
        dom: { freeze() { frozen++; }, unfreeze() { frozen--; } },
    };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../public/js/cdn_loader.js'), 'utf8'), {
        frappe, window: { location: { origin: 'http://retail-test.localhost:8000' } },
        URL, AbortController, setTimeout, clearTimeout,
        fetch: async (url, options) => {
            calls.push([url, options.credentials]);
            if (url.startsWith('https://')) throw new Error('CDN unavailable');
            return { ok: true, text: async () => url.endsWith('.css') ? 'a{background:url("../icon.svg")}' : 'local script' };
        },
    });
    await frappe.require([remote, css]);
    assert.deepEqual(evaluated.map(([p]) => p), [remote, css]);
    assert.equal(evaluated[0][1], 'local script');
    assert.ok(evaluated[1][1].includes('http://retail-test.localhost:8000/assets/icon.svg'));
    assert.equal(frozen, 0);
    assert.ok(calls.some(([url, credentials]) => url === remote && credentials === 'omit'));
});

test('failed CDN and local downloads reject and release the UI', async () => {
    let frozen = 0;
    const remote = 'https://assets.example.com/test.bundle.js';
    const frappe = { boot: { retail_cdn_local_assets: { [remote]: '/assets/test.bundle.js' } },
        require() {}, assets: { bundled_asset: p => p },
        dom: { freeze() { frozen++; }, unfreeze() { frozen--; } } };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../public/js/cdn_loader.js'), 'utf8'), {
        frappe, window: { location: { origin: 'http://localhost' } }, URL, AbortController, setTimeout, clearTimeout,
        fetch: async () => ({ ok: false, status: 404 }),
    });
    await assert.rejects(frappe.require(remote), /Local asset response 404/);
    assert.equal(frozen, 0);
});
