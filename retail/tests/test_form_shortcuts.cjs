const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
function fixture() {
 const listeners=[]; const calls=[];
 const frm={doc:{docstatus:0},perm:[{write:1}],fields_dict:{},doctype:'Example',is_new:()=>false,is_dirty:()=>false,save:async()=>calls.push('save')};
 const context={retail:{keyboard:{}},frappe:{ui:{form:{QuickEntryForm:class{},RetailQuickEntryForm:class{}}},get_route:()=>['Form'],new_doc:async()=>calls.push('new')},window:{cur_frm:frm},document:{addEventListener:(name,fn)=>listeners.push(fn),activeElement:{blur(){}}},Promise,$:()=>({is:()=>true})};
 vm.runInNewContext(fs.readFileSync('apps/retail/retail/public/js/form_shortcuts.js','utf8'),context);
 const key=(extra={})=>({key:'s',ctrlKey:true,shiftKey:true,preventDefault(){},stopImmediatePropagation(){},...extra});
 return {frm,calls,context,run:async(extra)=>{listeners[0](key(extra));await new Promise(resolve=>setImmediate(resolve));}};
}
test('Save & New opens a new document only after a successful clean draft save',async()=>{
 const f=fixture();await f.run();assert.deepEqual(f.calls,['save','new']);
 const dirty=fixture();dirty.frm.is_dirty=()=>true;await dirty.run();assert.deepEqual(dirty.calls,['save']);
 const posted=fixture();posted.frm.doc.docstatus=1;await posted.run();assert.deepEqual(posted.calls,[]);
});
test('modal save belongs to the dialog; Add Row selects the focused editable table',async()=>{
 const f=fixture();f.context.window.cur_dialog={};await f.run();assert.deepEqual(f.calls,[]);
 delete f.context.window.cur_dialog;
 const grid={df:{fieldname:'items'},wrapper:[{contains:()=>true}],is_editable:()=>true,add_new_row:()=>f.calls.push('row')};
 f.frm.fields_dict.items={grid};await f.run({key:'Enter',altKey:true,ctrlKey:false,shiftKey:false});assert.deepEqual(f.calls,['row']);
});
