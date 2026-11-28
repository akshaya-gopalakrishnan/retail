const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../public/js/forms/sales_invoice_accounts.js'), 'utf8');
let validate, calls = 0, pending;
const doc = {doctype:'Sales Invoice',name:'new-test',company:'Company',docstatus:0,
 items:Array.from({length:38},(_,i)=>({doctype:'Sales Invoice Item',name:'ROW'+i,item_code:'SKU'+i%10,qty:i+1,rate:7}))};
doc.items[0].income_account = 'Manual Account';
const frm = {doc};
const frappe = {ui:{form:{on(_dt,hooks){validate=hooks.validate;}}},
 call:async()=>{calls++;if(pending)return pending;return {message:doc.items.map(r=>({name:r.name,item_code:r.item_code,income_account:'Sales'}))};},
 model:{set_value:async(_dt,name,key,value)=>{doc.items.find(r=>r.name===name)[key]=value;}},
 throw(message){throw new Error(message);}};
vm.runInNewContext(source,{frappe,__:s=>s});
(async()=>{
 const figures=doc.items.map(r=>[r.qty,r.rate]);
 await validate(frm);
 assert.equal(calls,1);
 assert.equal(doc.items[0].income_account,'Manual Account');
 assert.ok(doc.items.slice(1).every(r=>r.income_account==='Sales'));
 assert.deepEqual(doc.items.map(r=>[r.qty,r.rate]),figures);
 await validate(frm);assert.equal(calls,1,'Complete rows do not add a Save request');
 delete doc.items[1].income_account;
 let finish;pending=new Promise(resolve=>finish=resolve);
 const checking=validate(frm);doc.company='Changed';finish({message:[{name:'ROW1',item_code:'SKU1',income_account:'Old Company Sales'}]});
 await assert.rejects(checking,/invoice changed/);
 assert.equal(doc.items[1].income_account,undefined);
 pending=null;doc.is_pos=1;const before=calls;await validate(frm);assert.equal(calls,before);
 console.log('PASS missing rows filled once; manual accounts and figures preserved; complete/POS rows skipped; stale replies rejected');
})().catch(error=>{console.error(error);process.exitCode=1;});
