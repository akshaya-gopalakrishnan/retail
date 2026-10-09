const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

function setup() {
 const context = vm.createContext({ console, Promise, Map, Set, Error, document: {},
  Widget: class { constructor(opts) { Object.assign(this, opts); } },
  locals: { DocType: {} }, retail: { business_home_charts: {} },
  $: () => ({ on() {} }),
  __: x => x, format_currency: (v, c) => `${c} ${v}`,
 });
 context.frappe = {
  provide() {}, dashboards: { chart_sources: {} }, widget: {},
  get_route: () => ['Workspaces', 'Business Home'],
  get_meta: dt => context.locals.DocType[dt],
  format: (v, df) => JSON.stringify({ v, df }),
  utils: { make_chart: (_el, args) => ({ args, update(data) { this.data = data; } }) },
  model: { with_doctype: async (dt, callback) => { context.locals.DocType[dt] = { fields: [] }; callback?.(); } },
 };
 const core = path.resolve(__dirname, '../../../frappe/frappe/public/js/frappe/widgets/chart_widget.js');
 vm.runInContext(fs.readFileSync(core, 'utf8').replace(/^import .*;\n/m, '').replace('export default class ChartWidget', 'class ChartWidget') + '\nfrappe.widget.widget_factory = {chart: ChartWidget};', context);
 const Base = context.frappe.widget.widget_factory.chart;
 vm.runInContext(fs.readFileSync(path.resolve(__dirname, '../public/js/business_home_charts.js'), 'utf8'), context);
 return { context, Base, Chart: context.frappe.widget.widget_factory.chart, load: context.retail.business_home_charts.with_metadata };
}
function widget(Chart, name = 'Top Selling Products') {
 const w = new Chart({ chart_name: name });
 w.chart_doc = { name, source: name, chart_type: 'Custom', document_type: 'Sales Invoice', type: 'Bar', y_axis: [], filters_json: '[]' };
 w.data = { labels: ['A'], datasets: [{ name: 'Sales', values: [10] }] };
 for (const k of ['loading', 'empty', 'chart_wrapper']) w[k] = { 0: {}, show() {}, hide() {} };
 return w;
}
test('three actual chart renderers skip metadata and preserve core formatting/source DocType', async () => {
 const { context, Chart, Base } = setup();
 context.locals.DocType['Sales Invoice'] = { fields: [{ fieldname: 'grand_total', fieldtype: 'Currency', options: 'currency' }] };
 const widgets = ['Top Selling Products', 'Sales by Counter', 'Sales Trend 7 Days'].map(n => widget(Chart, n));
 for (const w of widgets) {
  const expected = Base.prototype.get_chart_args.call(w);
  const actual = w.get_chart_args();
  assert.equal(JSON.stringify(actual), JSON.stringify(expected));
  assert.equal(actual.tooltipOptions.formatTooltipY(123.45), expected.tooltipOptions.formatTooltipY(123.45));
 }
 delete context.locals.DocType['Sales Invoice'];
 context.frappe.model.with_doctype = () => { throw Error('Unexpected metadata request'); };
 await Promise.all(widgets.map(w => w.render()));
 for (const w of widgets) {
  assert.ok(w.dashboard_chart);
  assert.equal(w.chart_doc.document_type, 'Sales Invoice');
  w.chart_doc.currency = 'AED';
  assert.equal(w.get_chart_args().tooltipOptions.formatTooltipY(10), 'AED 10');
  w.data = null;
  await w.render();
 }
});
test('field-based fallback shares one pending request and resolved metadata', async () => {
 const { context, Chart, load } = setup();
 let count = 0, finish;
 context.frappe.model.with_doctype = (dt, callback) => { if (context.locals.DocType[dt]) { callback?.(); return Promise.resolve(); } count++; return new Promise(resolve => { finish = () => { context.locals.DocType[dt] = { fields: [{fieldname:'grand_total',fieldtype:'Currency',options:'currency'}] }; resolve(); }; }); };
 const widgets = ['Top Selling Products', 'Sales by Counter', 'Sales Trend 7 Days'].map(n => widget(Chart, n));
 widgets.forEach(w => w.chart_doc.value_based_on = 'grand_total');
 const tasks = widgets.map(w => w.render());
 await Promise.resolve();
 assert.equal(count, 1);
 finish();
 await Promise.all(tasks);
 await load('Sales Invoice');
 assert.equal(count, 1);
 widgets.forEach(w => assert.ok(w.dashboard_chart));
});
test('failure rejects all callers, clears pending, and permits retry', async () => {
 const { context, load } = setup();
 let count = 0;
 context.frappe.model.with_doctype = async () => { count++; throw Error('Network failed'); };
 const first = load('Sales Invoice');
 assert.equal(load('Sales Invoice'), first);
 const results = await Promise.allSettled([first, load('Sales Invoice'), load('Sales Invoice')]);
 assert.ok(results.every(r => r.status === 'rejected'));
 assert.equal(count, 1);
 context.frappe.model.with_doctype = async dt => { count++; context.locals.DocType[dt] = { fields: [] }; };
 await load('Sales Invoice');
 assert.equal(count, 2);
});
test('missing metadata rejects and other DocTypes have independent requests', async () => {
 const { context, load } = setup();
 context.frappe.model.with_doctype = async () => ({});
 await assert.rejects(load('Sales Invoice'), /Unable to load metadata/);
 let count = 0;
 context.frappe.model.with_doctype = async dt => { count++; context.locals.DocType[dt] = { fields: [] }; };
 await Promise.all([load('Sales Invoice'), load('Item')]);
 assert.equal(count, 2);
});
test('unrelated charts and other workspace instances retain the core renderer', async () => {
 const { context, Chart } = setup();
 let count = 0;
 const original = context.frappe.model.with_doctype;
 context.frappe.model.with_doctype = async (dt, callback) => { count++; await original(dt, callback); };
 const unrelated = widget(Chart, 'Other Chart');
 await unrelated.render();
 assert.equal(count, 1);
 delete context.locals.DocType['Sales Invoice'];
 context.frappe.get_route = () => ['Workspaces', 'Other Workspace'];
 const other_workspace = widget(Chart);
 await other_workspace.render();
 assert.equal(count, 2);
});
