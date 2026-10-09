frappe.query_reports["POS Hourly Sales"] = {
	formatter: (...args) => window.retail_profitability_formatter(...args),
	filters: get_pos_report_filters(),
};
