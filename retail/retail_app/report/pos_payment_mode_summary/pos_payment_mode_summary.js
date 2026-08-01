frappe.query_reports["POS Payment Mode Summary"] = {
	filters: get_pos_report_filters({ include_cashier: true, include_payment_mode: true }),
};
