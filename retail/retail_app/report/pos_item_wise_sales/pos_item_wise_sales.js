frappe.query_reports["POS Item-wise Sales"] = {
	formatter: (...args) => window.retail_profitability_formatter(...args),
	filters: get_pos_report_filters({ include_item_filters: true }),
};
