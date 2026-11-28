const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let hooks;
const frappe = {boot:{can_manage_access:true},ui:{form:{on(dt, handlers){if(dt==='User') hooks=handlers;}}}};
vm.runInNewContext(fs.readFileSync('apps/retail/retail/public/js/forms/access_control.js','utf8'),{frappe,__:s=>s});
let changePassword;
const enabled = {};
const frm={doc:{name:'existing@example.com',new_password:'autofilled'},is_new:()=>false,
 fields_dict:{},toggle_enable(field,value){enabled[field]=value;},refresh_field(){},
 add_custom_button(label,action){if(label==='Change Password') changePassword=action;}};
hooks.refresh(frm);
assert.equal(frm.doc.new_password,'');
assert.equal(enabled.new_password,false);
frm.doc.new_password='late-autofill';hooks.before_save(frm);
assert.equal(frm.doc.new_password,'');
changePassword();assert.equal(enabled.new_password,true);
frm.doc.new_password='intentional-change';hooks.before_save(frm);
assert.equal(frm.doc.new_password,'intentional-change');
hooks.after_save(frm);assert.equal(frm.doc.new_password,'');assert.equal(enabled.new_password,false);
changePassword();frm.doc={name:'another@example.com',new_password:'autofill'};hooks.before_save(frm);
assert.equal(frm.doc.new_password,'');
frm.is_new=()=>true;frm.doc.new_password='new-user-password';hooks.before_save(frm);
assert.equal(frm.doc.new_password,'new-user-password');
console.log('PASS: autofill discarded; explicit change preserved; save disarms; other users and new users handled');
