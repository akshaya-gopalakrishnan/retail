frappe.query_reports["POS Payment Mode Summary"] = {
	filters: get_pos_report_filters({ include_cashier: true, include_payment_mode: true }).map((filter) => {
		if (filter.fieldname === "payment_mode") {
			return {
				...filter,
				fieldtype: "Data",
				options: undefined,
				description: __("Enter a payment mode or Credit Sale, Credit Note Issued, Credit Note Redeemed, Original Debt Reduction."),
			};
		}
		return filter;
	}),
};
