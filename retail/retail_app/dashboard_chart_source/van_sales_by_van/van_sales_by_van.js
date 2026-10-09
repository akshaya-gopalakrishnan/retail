frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Van Sales by Van"] = {
	method: "retail.retail_app.retail_dashboard.get_van_sales_by_van",
	filters: [],
};
