frappe.query_reports["Shift Closing Variance"] = {
	filters: get_pos_report_filters({ include_cashier: true, include_shift: true }),
};
