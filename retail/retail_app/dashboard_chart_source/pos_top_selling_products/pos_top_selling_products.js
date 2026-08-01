frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["POS Top Selling Products"] = {
	method: "retail.retail_app.retail_dashboard.get_pos_top_selling_products",
	filters: [],
};
