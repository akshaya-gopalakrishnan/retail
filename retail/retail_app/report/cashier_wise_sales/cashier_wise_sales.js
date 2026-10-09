frappe.query_reports["Cashier Wise Sales"] = {
	formatter: (...args) => window.retail_profitability_formatter(...args),
	filters: get_pos_report_filters({ include_cashier: true }),
};
