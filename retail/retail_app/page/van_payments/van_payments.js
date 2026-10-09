frappe.pages["van-payments"].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Van Payments"),
		single_column: false,
	});

	wrapper.van_sales_wrapper = new retail.VanDocumentWrapper({
		page,
		doctype: "Payment Entry",
		flag_field: "custom_is_van_payment",
		title: __("Van Payment"),
		new_doc_values: {
			custom_is_van_payment: 1,
			payment_type: "Receive",
		},
		columns: [
			{ fieldname: "name", label: __("Payment"), link: true },
			{ fieldname: "posting_date", label: __("Date"), type: "Date" },
			{ fieldname: "payment_type", label: __("Type") },
			{ fieldname: "party", label: __("Party") },
			{ fieldname: "mode_of_payment", label: __("Mode") },
			{ fieldname: "paid_amount", label: __("Paid Amount"), type: "Currency" },
			{ fieldname: "custom_van_session", label: __("Session") },
		],
		fields: ["name", "posting_date", "payment_type", "party", "mode_of_payment", "paid_amount", "custom_van_session"],
	});
};

frappe.pages["van-payments"].on_page_show = function(wrapper) {
	wrapper.van_sales_wrapper?.refresh();
};
