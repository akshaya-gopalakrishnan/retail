frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Van Sales Trend 7 Days"] = {
	method: "retail.retail_app.retail_dashboard.get_van_sales_trend_7_days",
	filters: [],
};
