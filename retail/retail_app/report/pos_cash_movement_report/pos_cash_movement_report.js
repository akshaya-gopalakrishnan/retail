frappe.query_reports["POS Cash Movement Report"] = {
	filters: get_pos_report_filters({ include_cashier: true, include_movement_type: true }),
};
