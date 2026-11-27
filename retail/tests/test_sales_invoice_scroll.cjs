const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
function fixture() {
    let install; const timers = [], focused = [], revealed = [];
    const page = {scrollTop:900,scrollLeft:0,parentElement:null};
    const container = {scrollTop:180,scrollLeft:240};
    const wrapper = {scrollTop:0,scrollLeft:0,parentElement:page,querySelectorAll(){return [container];}};
    const input = {focus(options){focused.push(options);},scrollIntoView(options){revealed.push(options);}};
    const row = {toggle_editable_row(){page.scrollTop=0;container.scrollLeft=0;},row:{find(){return {filter(){return [input];}};}}};
    let nativeFocus = 0;
    const grid = {wrapper:[wrapper],grid_rows:[row],allow_on_grid_editing(){return true;},
        refresh(arg){page.scrollTop=0;container.scrollTop=0;container.scrollLeft=0;return arg;},set_focus_on_row(){nativeFocus++;}};
    vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../public/js/forms/sales_invoice_scroll.js'),'utf8'),
        {frappe:{ui:{form:{on(dt,events){install=events.refresh;}}}},document:{scrollingElement:page},setTimeout(fn){timers.push(fn);}});
    const frm = {fields_dict:{items:{grid}}};install(frm);
    return {grid,page,container,timers,focused,revealed,install,frm,nativeFocus:()=>nativeFocus};
}
test('row refresh keeps page and grid positions, returns native result, and installs once',()=>{
    const f=fixture();const refresh=f.grid.refresh;f.install(f.frm);assert.equal(f.grid.refresh,refresh);
    assert.equal(f.grid.refresh('result'),'result');
    assert.equal(f.page.scrollTop,900);assert.equal(f.container.scrollTop,180);assert.equal(f.container.scrollLeft,240);
    f.page.scrollTop=600;f.grid.refresh();assert.equal(f.page.scrollTop,600,'Later manual scroll is respected');
});
test('Add Row focus preserves current position and only reveals the nearest row',()=>{
    const f=fixture();f.grid.set_focus_on_row();f.timers.pop()();
    assert.equal(f.focused.length,1);assert.equal(f.focused[0].preventScroll,true);
    assert.equal(f.page.scrollTop,900);assert.equal(f.container.scrollLeft,240);
    assert.equal(f.revealed[0].block,'nearest');assert.equal(f.nativeFocus(),0);
});
test('expanded row mode retains native focus and a removed row does not throw',()=>{
    const f=fixture();f.grid.allow_on_grid_editing=()=>false;f.grid.set_focus_on_row(0);assert.equal(f.nativeFocus(),1);
    f.grid.allow_on_grid_editing=()=>true;f.grid.set_focus_on_row(4);assert.doesNotThrow(()=>f.timers.pop()());
});
