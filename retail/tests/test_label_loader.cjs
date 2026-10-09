const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

test('label printing loads on first use and shares concurrent requests', async () => {
    let loads = 0;
    let complete;
    const retail = { zebra: {} };
    const context = { retail, frappe: {
        provide() {},
        require(bundle) {
            assert.equal(bundle, 'retail_labels.bundle.js');
            loads++;
            return new Promise(resolve => { complete = resolve; });
        },
    } };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../public/js/zebra_label_loader.js'), 'utf8'), context);
    assert.equal(loads, 0);
    const first = retail.zebra.open_bulk_print_dialog({ id: 1 });
    const second = retail.zebra.open_bulk_print_dialog({ id: 2 });
    assert.equal(loads, 1);
    retail.zebra.open_bulk_print_dialog = async opts => opts.id;
    complete();
    assert.deepEqual(await Promise.all([first, second]), [1, 2]);
    assert.equal(await retail.zebra.open_bulk_print_dialog({ id: 3 }), 3);
    assert.equal(loads, 1);
});
