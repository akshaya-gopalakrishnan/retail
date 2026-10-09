frappe.query_reports["POS Daily Closing Summary"] = {
	formatter: (...args) => window.retail_profitability_formatter(...args),
	filters: get_pos_report_filters(),
};
