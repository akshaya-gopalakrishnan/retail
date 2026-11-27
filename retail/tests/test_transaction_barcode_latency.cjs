const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
test('barcode reads skip unchanged rows and wait for native item actions', async () => {
    const handlers = {}, timers = [], calls = [];
    const row = {name:'row',doctype:'Sales Invoice Item',item_code:'A',uom:'Nos'};
    const frm = {doc:{doctype:'Sales Invoice',docstatus:0,items:[row]},meta:{fields:[{fieldtype:'Table',options:row.doctype}]},refresh_field(){}};
    const window = {retail:{}};
    const frappe = {meta:{has_field(){return true;}},ui:{form:{on(dt,events){handlers[dt]={...handlers[dt],...events};}}},
        async call(request){calls.push(request);return {message:{row:'MASTER'}};}};
    vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../public/js/forms/purchase_item_barcode.js'),'utf8'),
        {window,frappe,locals:{[row.doctype]:{row}},setTimeout(fn){timers.push(fn);return timers.length;},clearTimeout(){}});
    handlers['Sales Invoice'].setup(frm);
    const refresh = async () => {handlers['Sales Invoice'].refresh(frm);await timers.pop()();};
    await refresh();assert.equal(calls.length,1);assert.equal(row.custom_item_barcode,'MASTER');
    await refresh();assert.equal(calls.length,1);
    row.uom='Box';frm.__retail_purchase_action={active:1};
    await refresh();assert.equal(calls.length,1);
    delete frm.__retail_purchase_action;
    row.barcode='PACK';row.custom_item_barcode='PACK';row.custom_packing_detail='packing';
    window.retail.remember_transaction_barcode(row);
    await timers.pop()();assert.equal(calls.length,1,'Selected packing needs no barcode refetch');
    row.uom='Other';await refresh();assert.equal(calls.length,2,'A later UOM edit resolves again');
});
