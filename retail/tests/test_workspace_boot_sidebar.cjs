const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {test} = require('node:test');
function setup(boot) {
 let calls=0;const handlers=[];
 class Workspace {get_pages(){calls++;return Promise.resolve({pages:[{name:'Fresh'}],has_access:false,has_create_access:false})}}
 const context=vm.createContext({document:{},$:()=>({on:(event,fn)=>handlers.push(fn)}),frappe:{boot,views:{Workspace}}});
 vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../public/js/workspace_boot_sidebar.js'),'utf8'),context);
 return {workspace:new Workspace(),handlers,calls:()=>calls};
}
test('first mount uses filtered boot; later customization reload fetches fresh permissions',async()=>{
 const boot={allowed_workspaces:[{name:'Allowed',content:'[]'}],retail_workspace_sidebar_access:{has_access:false,has_create_access:true}};
 const s=setup(boot);s.handlers.forEach(fn=>fn());
 const result=await s.workspace.get_pages();assert.equal(s.calls(),0);assert.equal(result.has_access,false);assert.equal(result.has_create_access,true);assert.equal(result.pages[0].name,'Allowed');
 result.pages[0].name='Changed';assert.equal(boot.allowed_workspaces[0].name,'Allowed');
 assert.equal((await s.workspace.get_pages()).pages[0].name,'Fresh');assert.equal(s.calls(),1);
});
test('old boot and missing capability flags use the standard permission-checked endpoint',async()=>{
 for(const boot of [undefined,{}, {allowed_workspaces:[]}, {retail_workspace_sidebar_access:{has_access:true}}]) {
  const s=setup(boot);assert.equal((await s.workspace.get_pages()).pages[0].name,'Fresh');assert.equal(s.calls(),1);
 }
});
test('empty restricted boot remains empty without requesting more navigation',async()=>{
 const s=setup({allowed_workspaces:[],retail_workspace_sidebar_access:{has_access:false,has_create_access:false}});
 assert.equal((await s.workspace.get_pages()).pages.length,0);assert.equal(s.calls(),0);
});
