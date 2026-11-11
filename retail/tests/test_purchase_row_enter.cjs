const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../public/js/forms/purchase_receipt_quick_entry.js'), 'utf8');

test('item-row Enter moves across editable fields and respects selection and boundaries', () => {
 const context = {frappe:{ui:{form:{on(){}}}}, $:()=>({closest:()=>({find:()=>({length:0})})})};
 vm.runInNewContext(source.replace(/\}\)\(\);\s*$/, 'globalThis.bindItemRowEnter = bindItemRowEnter;globalThis.focusFirstEditable = focusFirstEditable;})();'), context);
 let handler, focused, added = 0, allowed = true;
 const root = {addEventListener(name, fn){assert.equal(name, 'keydown');handler = fn;}};
 const fields = Array.from({length:4}, (_, i)=>({type:'text', tabIndex:0, tagName:'INPUT',
  matches:selector=>selector.startsWith('input'), getAttribute:()=>null, getClientRects:()=>[{}], blur(){},
  closest:()=>({querySelectorAll:()=>fields}), focus(){focused=i;}, select(){}}));
 fields[1].readOnly = true;
 assert.equal(context.focusFirstEditable({querySelectorAll:()=>[fields[1], fields[2]]}), true);
 assert.equal(focused, 2);
 fields[2].type = 'checkbox';
 context.bindItemRowEnter(root, 'tr', ()=>allowed, ()=>added++);
 function press(index, options={}) {
  focused = undefined;
  const event = {key:'Enter', target:fields[index], preventDefault(){this.prevented=true;}, stopImmediatePropagation(){}, ...options};
  handler(event); return event;
 }
 assert.equal(press(0).prevented, true); assert.equal(focused, 2);
 press(0,{key:'ArrowRight'});assert.equal(focused,2);
 press(2,{key:'ArrowLeft'});assert.equal(focused,0);
 press(2, {shiftKey:true}); assert.equal(focused, 0);
 assert.equal(press(3).prevented, true); assert.equal(focused, undefined);
 assert.equal(added, 1);
 press(3, {repeat:true}); assert.equal(added, 1);
 press(0, {shiftKey:true}); assert.equal(added, 1);
 assert.equal(press(0, {altKey:true}).prevented, undefined);
 fields[0].getAttribute=()=> 'true';
 assert.equal(press(0).prevented, undefined);
 fields[0].getAttribute=()=>null;
 fields[0].matches=()=>false; // Multiline serial fields retain Enter.
 assert.equal(press(0).prevented, undefined);
 allowed=false;
 assert.equal(press(2).prevented, undefined);
});
