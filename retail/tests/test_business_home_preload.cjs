const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const {test} = require('node:test');
function setup(pageName='Business Home', fail=false) {
 const locals={},docinfo={};let requests=0;
 const defs=['One','Two'].map(name=>({docs:[{doctype:'Number Card',name}],docinfo:{doctype:'Number Card',name,user_info:{}}}));
 const context=vm.createContext({document:{},$:()=>({on(){}}),frappe:{views:{Workspace:class{get_data(){this.page_data={retail_widget_definitions:defs};return Promise.resolve('original result')}}},model:{sync(r){const d=r.docs[0];(locals[d.doctype]??={})[d.name]=d;if(fail&&d.name==='One')throw Error('sync failure');(docinfo[d.doctype]??={})[d.name]=r.docinfo},clear_doc(dt,n){delete locals[dt]?.[n]},with_doc(dt,n){if(!locals[dt]?.[n]||!docinfo[dt]?.[n])requests++;return Promise.resolve(locals[dt]?.[n])}}}});
 vm.runInContext(fs.readFileSync(path.resolve(__dirname,'../public/js/business_home_preload.js'),'utf8'),context);
 return {context,locals,docinfo,getRequests:()=>requests,pageName};
}
test('cache has both docs and docinfo before construction; no later getdoc',async()=>{const s=setup();const w=new s.context.frappe.views.Workspace();assert.equal(await w.get_data({name:s.pageName}),'original result');for(const name of ['One','Two'])await s.context.frappe.model.with_doc('Number Card',name);assert.equal(s.getRequests(),0);assert.ok(s.docinfo['Number Card'].One);assert.equal(w.page_data.retail_widget_definitions,undefined)});
test('one sync failure falls back independently',async()=>{const s=setup('Business Home',true);await new s.context.frappe.views.Workspace().get_data({name:s.pageName});for(const name of ['One','Two'])await s.context.frappe.model.with_doc('Number Card',name);assert.equal(s.getRequests(),1);assert.ok(s.locals['Number Card'].Two)});
test('other workspace does not hydrate definitions',async()=>{const s=setup('POS');await new s.context.frappe.views.Workspace().get_data({name:s.pageName});assert.equal(Object.keys(s.locals).length,0)});
test('preloaded chart sources run before widgets; failures retain standard fallback',async()=>{
 const s=setup();const f=s.context.frappe;f.dashboards={chart_sources:{Existing:{keep:true}}};let calls=[];
 f.dom={eval(config){calls.push(config);if(config==='broken'){f.dashboards.chart_sources.Bad={};throw Error('bad')}f.dashboards.chart_sources.New={filters:[]}}};
 const w=new f.views.Workspace();
 // Supply configs through the underlying native response, before hydration.
 const old=Object.getPrototypeOf(w).get_data;
 // setup's native method sets page_data; intercept the definitions assignment.
 const defs=[];Object.defineProperty(w,'page_data',{get(){return defs.value},set(value){value.retail_chart_source_configs={Existing:'existing',New:'new',Bad:'broken'};defs.value=value},configurable:true});
 await old.call(w,{name:'Business Home'});
 assert.deepEqual(calls,['new','broken']);assert.ok(f.dashboards.chart_sources.New);assert.ok(f.dashboards.chart_sources.Existing.keep);assert.equal(f.dashboards.chart_sources.Bad,undefined);assert.equal(w.page_data.retail_chart_source_configs,undefined);
});
