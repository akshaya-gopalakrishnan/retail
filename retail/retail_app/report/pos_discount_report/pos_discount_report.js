frappe.query_reports["POS Discount Report"] = {
	filters: get_pos_report_filters({ include_cashier: true, include_item_filters: true }),
};
