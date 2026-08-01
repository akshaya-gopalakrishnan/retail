frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["POS Sales Trend 7 Days"] = {
	method: "retail.retail_app.retail_dashboard.get_pos_sales_trend_7_days",
	filters: [],
};
