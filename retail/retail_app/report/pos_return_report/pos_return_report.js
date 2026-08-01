frappe.query_reports["POS Return Report"] = {
	filters: get_pos_report_filters({ include_customer: true }),
};
