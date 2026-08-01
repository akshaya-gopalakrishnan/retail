frappe.query_reports["POS Transaction Log"] = {
	filters: get_pos_report_filters({ include_status: true }),
};
