const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
function fixture(docstatus=0, active=true, editor=false) {
    const handlers={},timers=[],calls=[];
    let displayCount=0;
    const frm={doc:{docstatus},cscript:{apply_pricing_rule(item, calculate){calls.push({item,calculate});return Promise.resolve();}}};
    const context={frappe:{boot:{retail_has_whole_bill_promotions:active},after_ajax:()=>Promise.resolve(),
        ui:{form:{on(dt,events){handlers[dt]={...handlers[dt],...events};}}}},
        setTimeout(fn){timers.push(fn);return timers.length;},clearTimeout(){}};
    let input,field,focus;
    const events={};
    if(editor){
        input={value:'1',selectionStart:1,selectionEnd:1,isConnected:true,
            matches:()=>true,closest:()=>({getAttribute:()=> 'ROW'}),
            addEventListener(event,fn){events[event]=fn;},setSelectionRange(start,end){this.selectionStart=start;this.selectionEnd=end;}};
        field={$input:{0:input},refresh(){input.value='1';input.selectionStart=0;input.selectionEnd=0;return 'native';}};
        frm.wrapper={addEventListener(event,fn){focus=fn;}};
        frm.fields_dict={items:{grid:{grid_rows_by_docname:{ROW:{on_grid_fields_dict:{qty:field}}}}}};
        context.document={activeElement:input};
    }
    context.window={retail:{transaction_items:{async refreshVatDisplays(){displayCount++;}}}};
    vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../public/js/forms/whole_bill_promotions.js'),'utf8'),context);
    handlers['Sales Invoice'].refresh(frm);
    return {frm,calls,handlers,timers,input,field,events,focus:()=>focus({target:input}),displayCount:()=>displayCount};
}
test('row pricing refresh keeps the edited row immediate and evaluates the whole bill once idle',async()=>{
    const f=fixture();
    await f.frm.cscript.apply_pricing_rule({name:'ROW'},true);
    assert.equal(f.calls[0].item.name,'ROW');
    assert.equal(f.calls[0].calculate,true);
    await f.timers.shift()();
    assert.equal(f.calls[1].item,undefined);
    await f.timers.shift()();
    assert.equal(f.displayCount(),1);
});
test('completed documents and sites without whole-bill promotions keep native row requests',async()=>{
    for(const f of [fixture(1),fixture(0,false)]){
        const item={name:'ROW'};
        await f.frm.cscript.apply_pricing_rule(item,true);
        assert.equal(f.calls[0].item,item);
        assert.equal(f.timers.length,0);
    }
});
test('adding or removing an item schedules a complete native rule evaluation',async()=>{
    for(const event of ['item_code','uom','items_remove']){
        const f=fixture();
        f.handlers['Sales Invoice Item'][event](f.frm);
        await f.timers.shift()();
        assert.equal(f.calls.length,1,event);
        assert.equal(f.calls[0].item,undefined,event);
    }
});
test('a quantity edit does not schedule a bill-wide reprice',()=>{
    const f=fixture();
    assert.equal(typeof f.handlers['Sales Invoice Item'].qty,'undefined');
});


test('native background refresh preserves uncommitted quantity text and caret until change',()=>{
    const f=fixture(0,true,true);
    f.focus();
    f.input.value='15';f.input.selectionStart=f.input.selectionEnd=2;f.events.input();
    assert.equal(f.field.refresh(),'native');
    assert.equal(f.input.value,'15');
    assert.equal(f.input.selectionStart,2);
    f.input.value='';f.events.input();f.field.refresh();
    assert.equal(f.input.value,'');
    f.events.change();f.field.refresh();
    assert.equal(f.input.value,'1');
});

test('blur clears the quantity draft so subsequent model changes display normally',()=>{
    const f=fixture(0,true,true);
    f.focus();f.input.value='5';f.events.input();f.events.blur();f.field.refresh();
    assert.equal(f.input.value,'1');
});
