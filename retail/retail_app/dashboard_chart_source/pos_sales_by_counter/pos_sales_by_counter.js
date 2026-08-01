frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["POS Sales by Counter"] = {
	method: "retail.retail_app.retail_dashboard.get_pos_sales_by_counter",
	filters: [],
};
