// Business Home's custom charts have no value_based_on field. Keep their source
// DocType for actions/filters, but do not fetch form metadata just for tooltips.
(() => {
	const chart_names = new Set([
		"Top Selling Products",
		"Sales by Counter",
		"Sales Trend 7 Days",
	]);
	const pending = new Map();

	function with_metadata(doctype) {
		if (pending.has(doctype)) return pending.get(doctype);
		if (locals.DocType[doctype]) return Promise.resolve();
		const request = Promise.resolve()
			.then(() => frappe.model.with_doctype(doctype))
			.then((response) => {
				if (response?.exc || !locals.DocType[doctype]) {
					throw new Error(`Unable to load metadata for ${doctype}`);
				}
			});
		const shared = request.finally(() => {
			if (pending.get(doctype) === shared) pending.delete(doctype);
		});
		pending.set(doctype, shared);
		return shared;
	}

	frappe.provide("retail.business_home_charts");
	retail.business_home_charts.with_metadata = with_metadata;

	function install() {
		const factory = frappe.widget?.widget_factory;
		if (!factory?.chart || factory.chart.retail_business_home) return;
		const ChartWidget = factory.chart;
		class BusinessHomeChart extends ChartWidget {
			constructor(opts) {
				super(opts);
				const route = frappe.get_route();
				this.retail_business_home =
					route[0] === "Workspaces" &&
					route[1] === "Business Home" &&
					chart_names.has(opts.chart_name);
			}

			is_retail_custom_chart() {
				return (
					this.retail_business_home &&
					this.chart_doc?.chart_type === "Custom" &&
					this.chart_doc.source === this.chart_name &&
					this.chart_doc.document_type === "Sales Invoice"
				);
			}

			get_chart_args() {
				if (!this.is_retail_custom_chart() || this.chart_doc.value_based_on) {
					return super.get_chart_args();
				}
				// The core lookup would find no field. Everything else (currency,
				// custom options, axes, colors) still uses the original renderer.
				const chart_doc = this.chart_doc;
				this.chart_doc = { ...chart_doc, document_type: null };
				try {
					return super.get_chart_args();
				} finally {
					this.chart_doc = chart_doc;
				}
			}

			async render() {
				if (!this.is_retail_custom_chart()) return super.render();
				if (this.chart_doc.value_based_on) {
					await with_metadata(this.chart_doc.document_type);
					return super.render();
				}
				// Match ChartWidget.render's display lifecycle without its metadata
				// gate. Do not mutate the saved/in-memory chart's source DocType.
				if (!this.data || !this.data.labels || !Object.keys(this.data).length) {
					this.chart_wrapper.hide();
					this.loading.hide();
					this.$summary && this.$summary.hide();
					this.empty.show();
					return;
				}
				this.loading.hide();
				this.empty.hide();
				this.chart_wrapper.show();
				const chart_args = this.get_chart_args();
				if (!this.dashboard_chart) {
					this.dashboard_chart = frappe.utils.make_chart(this.chart_wrapper[0], chart_args);
				} else {
					this.dashboard_chart.update(this.data);
				}
				this.width == "Full" && this.summary && this.set_summary();
				this.chart_doc.type == "Heatmap" && this.render_heatmap_legend();
			}
		}
		BusinessHomeChart.retail_business_home = true;
		factory.chart = BusinessHomeChart;
	}

	install();
	$(document).on("startup", install);
})();
