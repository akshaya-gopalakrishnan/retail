const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
test('Item selector searches typed text, resets pagination and rejects old responses', async () => {
    const events = {}, timers = new Map(), calls = [];
    let timerId = 0, text = '';
    const input = {attr(){return this;},on(event,fn){events[event]=fn;return this;}};
    const field = {df:{},$input:input,refresh(){}};
    const wrapper = {empty(){return this;},hide(){return this;}};
    const modal = {on(event,fn){events[event]=fn;}};
    class Selector {}
    const frappe = {ui:{form:{LinkSelector:Selector,on(){}}},utils:{escape_html:String},
        call(request){return new Promise(resolve=>calls.push({request,resolve}));}};
    const window = {retail:{}};
    vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../public/js/forms/purchase_packing_search.js'),'utf8'),
        {window,frappe,document:{getElementById(){return true;}},__:s=>s,
         setTimeout(fn){timers.set(++timerId,fn);return timerId;},clearTimeout(id){timers.delete(id);}});
    const selector = new Selector();
    Object.assign(selector,{doctype:'Item',start:10,page_length:10,target:{},dialog:{$wrapper:modal,
        fields_dict:{txt:field,results:{$wrapper:wrapper},more:{$wrapper:wrapper}},get_value(){return text;},get_primary_btn(){return {};}}});
    const original = selector.search();
    assert.equal(field.df.label,'Search Item');
    text='mott';events['input.retailPackingSelector']();
    text='motto';events['input.retailPackingSelector']();
    assert.equal(timers.size,1);assert.equal(selector.start,0);
    calls[0].resolve({message:[]});await original;
    [...timers.values()][0]();
    assert.equal(calls.length,2);
    assert.equal(calls[1].request.args.txt,'motto');
    assert.equal(calls[1].request.args.start,0);
    events['hidden.bs.modal.retailPackingSelector']();
    calls[1].resolve({message:[]});
    await Promise.resolve();
});
