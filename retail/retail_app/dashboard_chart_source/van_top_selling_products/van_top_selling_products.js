frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Van Top Selling Products"] = {
	method: "retail.retail_app.retail_dashboard.get_van_top_selling_products",
	filters: [],
};
