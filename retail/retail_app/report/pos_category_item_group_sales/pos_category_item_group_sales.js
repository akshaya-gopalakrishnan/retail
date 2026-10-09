frappe.query_reports["POS Category Item Group Sales"] = {
	formatter: (...args) => window.retail_profitability_formatter(...args),
	filters: get_pos_report_filters({ include_item_group: true }),
};
