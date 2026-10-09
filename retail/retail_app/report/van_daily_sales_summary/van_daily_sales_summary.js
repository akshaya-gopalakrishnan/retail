frappe.query_reports["Van Daily Sales Summary"] = {
	formatter: (...args) => window.retail_profitability_formatter(...args),
	filters: retail.van_sales_report_filters(),
};
