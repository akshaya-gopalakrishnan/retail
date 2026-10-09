const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const {test} = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '../public/js/retail_keyboard.js'), 'utf8');

function fixture() {
 const listeners = {};
 const document = {head: {}, body: {}, activeElement: null,
  addEventListener: (name, fn) => listeners[name] = fn};
 let popup = false;
 class Query {
  constructor(el) {this[0] = el; this.length = el ? 1 : 0;}
  is() {return this[0]?.visible !== false && !!this[0];}
  on() {return this;}
  appendTo() {return this;}
  each() {return this;}
  removeClass() {return this;}
  closest() {return new Query(this[0]?.row?.wrapper);}
  data(name) {return this[0]?.[name];}
 }
 const $ = el => typeof el === 'string' ? new Query(el.includes('listbox') && popup ? {} : null) : new Query(el);
 const delays = [];
 const context = {document, $, console, __: s => s, queueMicrotask, setTimeout: (fn, ms) => {delays.push(ms);queueMicrotask(fn);}};
 context.window = context;
 const frappe = context.frappe = {provide() {context.retail = {keyboard: {}};}, get_route: () => ['Form'],
  router: {on: (_, fn) => listeners.route = fn}, request: {}, flags: {}, model: {no_value_type: ['Section Break','HTML']},
  show_alert: () => {context.alerts++;}};
 context.alerts = 0;
 const frm = context.cur_frm = {doctype:'Purchase Invoice', doc:{}, fields:[], fields_dict:{}, wrapper:{contains: () => true}};
 function field(name, opts = {}, row) {
  const input = {value: opts.value ?? 'value', type:'text', visible:true, row,
   getBoundingClientRect:()=>input.rect, rect:{left:frm.fields.length*220,right:frm.fields.length*220+200,top:0,bottom:30},
   selectionStart:0, selectionEnd:0, focus() {document.activeElement = this;},
   select() {}, blur() {document.activeElement = document.body;},
   closest(selector) {return selector.includes('textarea') && this.multiline ? this : null;}};
  const control = {df:{fieldname:name, fieldtype:'Data', ...opts}, $input:[input], get_status:()=> 'Write',
   get_input_value:()=>input.value, get_model_value:()=>row ? row.doc[name] : frm.doc[name],
   async parse_validate_and_set_in_model(value) {if (row) row.doc[name] = value; else frm.doc[name] = value;}};
  if (!row) {frm.fields.push(control);frm.fields_dict[name] = control;}
  return control;
 }
 const company = field('company', {reqd:1});
 const optional = field('remarks');
 const supplier = field('supplier', {reqd:1});
 const hidden = field('hidden_required', {reqd:1,hidden:1});
 const readonly = field('read_only_required', {reqd:1,read_only:1});
 const scan = field('scan_barcode');
 scan.$input[0].rect={left:0,right:200,top:400,bottom:430};
 const docs = [];
 const grid = {df:{fieldname:'items',options:'Purchase Invoice Item'},frm,docfields:[{fieldname:'item_code'}],
  grid_rows:[],grid_rows_by_docname:{},is_editable:()=>true,allow_on_grid_editing:()=>true,get_data:()=>docs,
  add_new_row(idx) {const row = makeRow('NEW', ''); docs.splice(idx == null ? docs.length : idx - 1,0,row.doc);
   docs.forEach((doc,i)=>doc.idx=i+1);return row.doc;}};
 frm.fields_dict.items = {grid,df:grid.df};
 frm.fields.push(frm.fields_dict.items);
 function makeRow(name, item='ITEM') {
  const row = {grid,doc:{doctype:'Purchase Invoice Item',name,idx:docs.length+1,item_code:item},
   toggle_editable_row() {},activate() {},columns_list:[]};
  row.wrapper = {'grid_row':row};
  for (const [name, opts] of [['item_code',{value:item}], ['qty',{value:'1'}], ['amount',{read_only:1}], ['rate',{value:'10'}]]) {
   const f = field(name,opts,row);
   f.$input[0].rect={left:row.columns_list.length*220,right:row.columns_list.length*220+200,top:500+grid.grid_rows.length*50,bottom:530+grid.grid_rows.length*50};
   const cell = {df:f.df,field:f,visible:true,getBoundingClientRect:()=>f.$input[0].rect,contains:el=>el===f.$input[0]};
   row.columns_list.push(cell);
  }
  grid.grid_rows.push(row);grid.grid_rows_by_docname[name] = row;
  return row;
 }
 const row = makeRow('ROW');docs.push(row.doc);
 const second = makeRow('ROW2');docs.push(second.doc);
 vm.runInNewContext(source,context);
 const flush = async () => {for(let i=0;i<70;i++) await Promise.resolve();};
 async function key(control, key='Enter', flags={}) {
  const target = control.$input[0];target.focus();
  const event = {key,target,preventDefault(){this.prevented=true;},stopImmediatePropagation(){},...flags};
  listeners.keydown(event);await flush();return event;
 }
 const cell = (r,name)=>r.columns_list.find(c=>c.df.fieldname===name).field;
 return {context,document,frm,grid,row,second,company,optional,supplier,scan,hidden,readonly,key,cell,delays,listeners,
  popup:value=>popup=value,flush};
}

test('Enter skips optional, hidden and read-only headers; final mandatory field focuses scanner',async()=>{
 const f=fixture();await f.key(f.company);assert.equal(f.document.activeElement,f.supplier.$input[0]);
 await f.key(f.supplier);assert.equal(f.document.activeElement,f.scan.$input[0]);
 assert.equal(f.frm.doc.supplier,'value');
});
test('dynamic required fields are included and blank/invalid fields retain focus',async()=>{
 const f=fixture();f.optional.df.reqd=1;await f.key(f.company);assert.equal(f.document.activeElement,f.optional.$input[0]);
 f.optional.$input[0].value='';await f.key(f.optional);assert.equal(f.document.activeElement,f.optional.$input[0]);assert.equal(f.context.alerts,1);
 f.optional.$input[0].value='bad';f.optional.df.invalid=1;await f.key(f.optional);assert.equal(f.document.activeElement,f.optional.$input[0]);
});
test('no scan field falls back to first editable item cell',async()=>{
 const f=fixture();f.scan.$input[0].visible=false;await f.key(f.supplier);
 assert.equal(f.document.activeElement,f.cell(f.row,'item_code').$input[0]);
});
test('Enter edits the next cell directly, skips read-only fields, and inserts below active row',async()=>{
 const f=fixture();await f.key(f.cell(f.row,'qty'));assert.equal(f.document.activeElement,f.cell(f.row,'rate').$input[0]);
 await f.key(f.cell(f.row,'rate'));assert.equal(f.grid.get_data()[1].name,'NEW');assert.equal(f.grid.get_data()[2].name,'ROW2');
 assert.equal(f.document.activeElement,f.cell(f.grid.grid_rows_by_docname.NEW,'item_code').$input[0]);
});
test('empty item row does not create another row and row-add restrictions are honored',async()=>{
 const f=fixture();f.row.doc.item_code='';await f.key(f.cell(f.row,'rate'));assert.equal(f.grid.get_data().length,2);
 f.row.doc.item_code='ITEM';f.grid.cannot_add_rows=true;await f.key(f.cell(f.row,'rate'));assert.equal(f.grid.get_data().length,2);
});
test('Shift+Enter commits quantity and focuses form scanner',async()=>{
 const f=fixture();const qty=f.cell(f.row,'qty');qty.$input[0].value='7';await f.key(qty,'Enter',{shiftKey:true});
 assert.equal(f.row.doc.qty,'7');assert.equal(f.document.activeElement,f.scan.$input[0]);
});
test('Tab, dialogs, dropdowns, multiline and save shortcuts remain native',async()=>{
 const f=fixture();for(const flags of [{},{shiftKey:true}])assert.equal((await f.key(f.company,'Tab',flags)).prevented,undefined);
 f.popup(true);assert.equal((await f.key(f.company)).prevented,undefined);f.popup(false);
 f.context.cur_dialog={};assert.equal((await f.key(f.company)).prevented,undefined);f.context.cur_dialog=null;
 f.optional.$input[0].multiline=true;assert.equal((await f.key(f.optional)).prevented,undefined);
 assert.equal((await f.key(f.company,'s',{ctrlKey:true})).prevented,undefined);
});
test('arrow navigation moves cells even while the caret is inside a value',async()=>{
 const f=fixture();const qty=f.cell(f.row,'qty');qty.$input[0].value='123';qty.$input[0].selectionStart=1;qty.$input[0].selectionEnd=1;
 await f.key(qty,'ArrowRight');assert.equal(f.document.activeElement,f.cell(f.row,'rate').$input[0]);
 qty.$input[0].selectionStart=qty.$input[0].selectionEnd=3;await f.key(qty,'ArrowRight');assert.equal(f.document.activeElement,f.cell(f.row,'rate').$input[0]);
 await f.key(qty,'ArrowDown');assert.equal(f.document.activeElement,f.cell(f.second,'qty').$input[0]);
});
test('scanner Enter stays native and repeated Enter cannot add rows',async()=>{
 const f=fixture();assert.equal((await f.key(f.scan)).prevented,undefined);assert.equal(f.document.activeElement,f.scan.$input[0]);
 await f.key(f.cell(f.row,'rate'),'Enter',{repeat:true});assert.equal(f.grid.get_data().length,2);
});
test('new user activity cancels pending focus movement and Enter never submits',async()=>{
 const f=fixture();let finish;
 f.company.parse_validate_and_set_in_model=()=>new Promise(resolve=>{finish=resolve;});
 const moving=f.key(f.company);
 await Promise.resolve();
 await f.key(f.optional,'Tab');finish();await moving;await f.flush();
 assert.equal(f.document.activeElement,f.optional.$input[0]);
 let submitted=false;f.frm.save=()=>submitted=true;f.frm.page={btn_primary:{click:()=>submitted=true}};
 const control={$input:[{focus(){},closest:()=>null}]};
 assert.equal((await f.key(control)).prevented,undefined);
 assert.equal(submitted,false);
});

test('manual navigation adds no timers and ignores unrelated background requests',async()=>{
 const f=fixture();f.context.frappe.request.ajax_count=2;
 await f.key(f.company);assert.equal(f.document.activeElement,f.supplier.$input[0]);
 await f.key(f.cell(f.row,'qty'));assert.equal(f.document.activeElement,f.cell(f.row,'rate').$input[0]);
 await f.key(f.cell(f.row,'rate'));assert.equal(f.grid.get_data()[1].name,'NEW');
 await f.key(f.cell(f.row,'qty'),'Enter',{shiftKey:true});assert.equal(f.document.activeElement,f.scan.$input[0]);
 assert.deepEqual(f.delays,[],'No fixed waits for commits, insertion, or scan-field focusing');
});
test('focus waits for real field validation, then moves without another timer',async()=>{
 const f=fixture();let finish;
 f.company.parse_validate_and_set_in_model=()=>new Promise(resolve=>{finish=()=>{f.frm.doc.company='value';resolve();};});
 const moving=f.key(f.company);await Promise.resolve();
 assert.equal(f.document.activeElement,f.company.$input[0]);finish();await moving;
 assert.equal(f.document.activeElement,f.supplier.$input[0]);assert.deepEqual(f.delays,[]);
});


test('form arrows override caret movement but preserve open dropdown navigation',async()=>{
 const f=fixture();f.optional.$input[0].selectionStart=f.optional.$input[0].selectionEnd=2;
 await f.key(f.optional,'ArrowRight');assert.equal(f.document.activeElement,f.supplier.$input[0]);
 f.popup(true);assert.equal((await f.key(f.company,'ArrowDown')).prevented,undefined);
});


test('arrows can leave blank required fields and selected values; Enter still validates',async()=>{
 const f=fixture();f.company.$input[0].value='';await f.key(f.company,'ArrowRight');assert.equal(f.document.activeElement,f.optional.$input[0]);
 await f.key(f.company,'Enter');assert.equal(f.document.activeElement,f.company.$input[0]);
 f.optional.$input[0].selectionStart=0;f.optional.$input[0].selectionEnd=5;
 await f.key(f.optional,'ArrowRight');assert.equal(f.document.activeElement,f.supplier.$input[0]);
});

function revealFixture(f, input, rect) {
 const scrolls=[];
 f.context.innerHeight=800;f.context.innerWidth=1000;
 f.context.getComputedStyle=el=>el.style || {position:'static',direction:'ltr'};
 f.document.querySelectorAll=()=>[];
 f.context.scrollBy=options=>scrolls.push(options);
 input.scrollIntoView=options=>{assert.equal(options.behavior,'instant');assert.equal(options.block,'nearest');};
 input.getBoundingClientRect=()=>rect;
 return scrolls;
}
test('focused fields reveal above/below viewport instantly with sticky toolbar clearance',async()=>{
 const f=fixture();const rect={left:300,right:450,top:20,bottom:50};
 const scrolls=revealFixture(f,f.supplier.$input[0],rect);
 f.document.querySelectorAll=()=>[{style:{position:'sticky'},getBoundingClientRect:()=>({left:0,right:1000,top:0,bottom:100,height:100})}];
 await f.key(f.company);assert.equal(scrolls[0].top,-92);assert.equal(scrolls[0].behavior,'instant');
 rect.top=790;rect.bottom=820;scrolls.length=0;
 await f.key(f.company);assert.equal(scrolls[0].top,32);
 rect.top=200;rect.bottom=230;scrolls.length=0;
 await f.key(f.company);assert.equal(scrolls.length,0,'Already visible fields do not move the page');
});
test('item focus clears pinned columns horizontally and keeps page still',async()=>{
 const f=fixture();const input=f.cell(f.row,'rate').$input[0];
 const pageScrolls=revealFixture(f,input,{left:180,right:260,top:200,bottom:230});
 const horizontal=[];
 const container={getBoundingClientRect:()=>({left:100,right:900}),scrollBy:opts=>horizontal.push(opts),style:{direction:'ltr'}};
 const row={querySelectorAll:()=>[{style:{position:'sticky'},getBoundingClientRect:()=>({left:100,right:300})}]};
 input.closest=selector=>selector.includes('form-grid-container') ? container : selector==='.data-row' ? row : null;
 await f.key(f.cell(f.row,'qty'));
 assert.equal(horizontal[0].left,-132);assert.equal(horizontal[0].behavior,'instant');assert.equal(pageScrolls.length,0);
});
test('native focus changes reveal the field but no handler follows manual scrolling',async()=>{
 const f=fixture();const input=f.optional.$input[0];
 const scrolls=revealFixture(f,input,{left:300,right:450,top:850,bottom:880});
 input.focus();f.listeners.focusin({target:input});await f.flush();assert.equal(scrolls[0].top,92);
 assert.equal(f.listeners.scroll,undefined);
});

test('Shift+Enter closes active suggestions and returns from blank required fields to scan',async()=>{
 const f=fixture();const item=f.cell(f.row,'item_code');item.df.reqd=1;item.$input[0].value='';
 let closed=0;item.awesomplete={close(){closed++;f.popup(false);}};
 f.popup(true);const event=await f.key(item,'Enter',{shiftKey:true});
 assert.equal(event.prevented,true);assert.equal(closed,1);assert.equal(f.document.activeElement,f.scan.$input[0]);
 assert.equal(f.grid.get_data().length,2,'Shortcut must not select a suggestion or create rows');
});
test('arrow from the last header enters an empty items table and creates one initial row',async()=>{
 const f=fixture();f.grid.grid_rows=[];f.grid.grid_rows_by_docname={};f.grid.get_data().length=0;
 f.frm.fields_dict.items.wrapper={visible:true};f.grid.wrapper={getBoundingClientRect:()=>({left:0,right:800,top:500,bottom:560})};
 await f.key(f.scan,'ArrowDown');assert.equal(f.grid.get_data().length,1);
 assert.equal(f.document.activeElement,f.cell(f.grid.grid_rows_by_docname.NEW,'item_code').$input[0]);
});

test('spatial arrows follow screen direction and do not wrap item rows',async()=>{
 const f=fixture();
 await f.key(f.company,'ArrowRight');assert.equal(f.document.activeElement,f.optional.$input[0]);
 await f.key(f.optional,'ArrowLeft');assert.equal(f.document.activeElement,f.company.$input[0]);
 await f.key(f.company,'ArrowDown');assert.equal(f.document.activeElement,f.scan.$input[0]);
 await f.key(f.scan,'ArrowUp');assert.equal(f.document.activeElement,f.company.$input[0]);
 await f.key(f.scan,'ArrowDown');assert.equal(f.document.activeElement,f.cell(f.row,'item_code').$input[0]);
 await f.key(f.cell(f.row,'qty'),'ArrowDown');assert.equal(f.document.activeElement,f.cell(f.second,'qty').$input[0]);
 await f.key(f.cell(f.second,'qty'),'ArrowUp');assert.equal(f.document.activeElement,f.cell(f.row,'qty').$input[0]);
 await f.key(f.cell(f.row,'rate'),'ArrowRight');assert.equal(f.document.activeElement,f.cell(f.row,'rate').$input[0]);
 await f.key(f.cell(f.second,'item_code'),'ArrowLeft');assert.equal(f.document.activeElement,f.cell(f.second,'item_code').$input[0]);
 assert.deepEqual(f.delays,[]);
});
test('checkboxes participate in spatial navigation and Enter toggles without leaving',async()=>{
 const f=fixture();const checkbox=f.optional.$input[0];f.optional.df.fieldtype='Check';checkbox.type='checkbox';checkbox.checked=false;
 checkbox.click=()=>{checkbox.checked=!checkbox.checked;f.frm.doc.remarks=Number(checkbox.checked);};
 await f.key(f.company,'ArrowRight');assert.equal(f.document.activeElement,checkbox);
 await f.key(f.optional);assert.equal(checkbox.checked,true);assert.equal(f.frm.doc.remarks,1);assert.equal(f.document.activeElement,checkbox);
 await f.key(f.optional);assert.equal(checkbox.checked,false);assert.equal(f.frm.doc.remarks,0);assert.equal(f.document.activeElement,checkbox);
 await f.key(f.optional,'Enter',{repeat:true});assert.equal(checkbox.checked,false);
 await f.key(f.optional,'ArrowRight');assert.equal(f.document.activeElement,f.supplier.$input[0]);
});

for (const doctype of ['Purchase Receipt', 'Purchase Invoice', 'Sales Invoice', 'Delivery Note', 'Stock Entry', 'Custom Transaction']) {
 test(`${doctype}: Shift+Enter focuses scanner from form background and buttons`, async () => {
  const f = fixture(); f.frm.doctype = doctype;
  for (const target of [f.document.body, {closest: () => ({}), focus() {f.document.activeElement = this;}}]) {
   target.focus ||= function () {f.document.activeElement = this;};
   const event = await f.key({$input: [target]}, 'Enter', {shiftKey: true});
   assert.equal(event.prevented, true);
   assert.equal(f.document.activeElement, f.scan.$input[0]);
  }
 });
}
test('global scanner shortcut respects dialogs, unavailable scanners and doctype opt-outs', async () => {
 const f = fixture(); const target = {focus() {}, closest: () => null}; const control = {$input: [target]};
 f.context.cur_dialog = {};
 assert.equal((await f.key(control, 'Enter', {shiftKey: true})).prevented, undefined);
 f.context.cur_dialog = null; f.scan.$input[0].visible = false;
 assert.equal((await f.key(control, 'Enter', {shiftKey: true})).prevented, undefined);
 f.scan.$input[0].visible = true; f.context.retail.keyboard.doctypes[f.frm.doctype] = {enabled: false};
 assert.equal((await f.key(control, 'Enter', {shiftKey: true})).prevented, undefined);
});
