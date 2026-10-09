const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
let route = ['Workspaces', 'Business Home'], calls = [], fail = false, changed;
class Base { async get_data() { return 'legacy'; } }
const frappe = {
 widget: {widget_factory: {number_card: Base}},
 get_route: () => route,
 router: {on: (event, callback) => { changed = callback; }},
 xcall: async (method, args) => {
  calls.push({method, args});
  await new Promise(r => setTimeout(r, 5));
  if (fail) throw Error('failed');
  return args.contexts.map(() => ({sales: 100, profit: '<span>N/A</span>', count: 5, returns: 10}));
 }
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../public/js/business_home_profit_cards.js'), 'utf8'),
 {frappe, setTimeout, $: () => ({on() {}}), document: {}});
const names = ["Today's Sales", "Today's Profit", 'Invoice Count Today', 'Return Amount Today'];
const methods = ['get_today_sales', 'get_profit_number_card', 'get_invoice_count_today', 'get_return_amount_today'];
function widget(i, args = {filters: {branch:'ignored'}}) {
 const w = new frappe.widget.widget_factory.number_card();
 w.card_doc = {name:names[i], type:'Custom'};
 w.settings = {method:'retail.retail_app.retail_dashboard.'+methods[i], args, get_number:value => value};
 return w;
}
(async () => {
 assert.deepEqual(await Promise.all(names.map((_,i)=>widget(i).get_data())), [100,'<span>N/A</span>',5,10]);
 assert.equal(calls.length,1);
 assert.equal(calls[0].args.contexts.length,1);
 assert.equal(calls[0].args.contexts[0].branch,null);
 const refreshing = widget(0);
 await refreshing.get_data(); assert.equal(calls.length,1); // delayed initial widget shares page snapshot
 await refreshing.get_data(); assert.equal(calls.length,2); // explicit refresh gets fresh values
 calls=[];
 await Promise.all(names.map((_,i)=>widget(i,{company:'Co', branch:'B',counter:'C',from_date:'2026-10-01'}).get_data()));
 assert.equal(calls.length,1);assert.equal(calls[0].args.contexts.length,2);
 assert.equal(calls[0].args.contexts[0].branch,'B');assert.equal(calls[0].args.contexts[1].branch,null);
 changed();fail=true;
 const results=await Promise.allSettled(names.map((_,i)=>widget(i).get_data()));
 assert.ok(results.every(r=>r.status==='rejected'));fail=false;
 assert.equal(await widget(0).get_data(),100);
 route=['Workspaces','Other'];changed();assert.equal(await widget(0).get_data(),'legacy');
 route=['Workspaces','Business Home'];const other=widget(0);other.settings.method='other.method';
 assert.equal(await other.get_data(),'legacy');
 console.log('PASS: one request, split filters, nested-filter compatibility, late widgets, fresh refresh, failure/retry, other pages/APIs');
})().catch(error=>{console.error(error);process.exitCode=1});
