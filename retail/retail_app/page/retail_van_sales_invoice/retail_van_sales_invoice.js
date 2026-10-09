frappe.pages["retail-van-sales-invoice"].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Van Sales Invoice"),
		single_column: false,
	});

	wrapper.van_sales_wrapper = new retail.VanDocumentWrapper({
		page,
		doctype: "Sales Invoice",
		flag_field: "custom_is_van_sale",
		clear_fields: ["is_return"],
		title: __("Van Sales Invoice"),
		new_doc_values: {
			custom_is_van_sale: 1,
			update_stock: 1,
		},
		columns: [
			{ fieldname: "name", label: __("Invoice"), link: true },
			{ fieldname: "posting_date", label: __("Date"), type: "Date" },
			{ fieldname: "customer_name", label: __("Customer") },
			{ fieldname: "custom_van_session", label: __("Session") },
			{ fieldname: "grand_total", label: __("Grand Total"), type: "Currency" },
			{ fieldname: "outstanding_amount", label: __("Outstanding"), type: "Currency" },
			{ fieldname: "status", label: __("Status") },
		],
		fields: ["name", "posting_date", "customer_name", "custom_van_session", "grand_total", "outstanding_amount", "status"],
	});
};

frappe.pages["retail-van-sales-invoice"].on_page_show = function(wrapper) {
	wrapper.van_sales_wrapper?.refresh();
};
