frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Retail Top Selling Products"] = {
	method: "retail.retail_app.retail_dashboard.get_top_selling_products",
	filters: [],
};
