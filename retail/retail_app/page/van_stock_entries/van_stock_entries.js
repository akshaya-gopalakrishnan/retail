frappe.pages["van-stock-entries"].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Van Stock Entries"),
		single_column: false,
	});

	wrapper.van_sales_wrapper = new retail.VanDocumentWrapper({
		page,
		doctype: "Stock Entry",
		flag_field: "custom_is_van_stock_entry",
		title: __("Van Stock Entry"),
		new_doc_values: {
			custom_is_van_stock_entry: 1,
		},
		columns: [
			{ fieldname: "name", label: __("Stock Entry"), link: true },
			{ fieldname: "posting_date", label: __("Date"), type: "Date" },
			{ fieldname: "stock_entry_type", label: __("Stock Entry Type") },
			{ fieldname: "custom_van_stock_entry_type", label: __("Van Type") },
			{ fieldname: "custom_van_session", label: __("Session") },
			{ fieldname: "docstatus", label: __("Status"), type: "DocStatus" },
		],
		fields: ["name", "posting_date", "stock_entry_type", "custom_van_stock_entry_type", "custom_van_session", "docstatus"],
	});
};

frappe.pages["van-stock-entries"].on_page_show = function(wrapper) {
	wrapper.van_sales_wrapper?.refresh();
};
