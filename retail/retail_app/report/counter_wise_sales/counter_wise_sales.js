frappe.query_reports["Counter Wise Sales"] = {
	formatter: (...args) => window.retail_profitability_formatter(...args),
	filters: get_pos_report_filters(),
};
