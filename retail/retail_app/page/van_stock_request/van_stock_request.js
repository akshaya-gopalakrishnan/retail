frappe.pages["van-stock-request"].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Stock Request"),
		single_column: false,
	});

	wrapper.van_sales_wrapper = new retail.VanDocumentWrapper({
		page,
		doctype: "Material Request",
		flag_field: "custom_is_van_stock_request",
		title: __("Stock Request"),
		new_doc_values: {
			custom_is_van_stock_request: 1,
			material_request_type: "Material Transfer",
			custom_van_request_type: "Loading",
		},
		columns: [
			{ fieldname: "name", label: __("Request"), link: true },
			{ fieldname: "transaction_date", label: __("Date"), type: "Date" },
			{ fieldname: "custom_van_request_type", label: __("Type") },
			{ fieldname: "custom_van_session", label: __("Session") },
			{ fieldname: "custom_van", label: __("Van") },
			{ fieldname: "custom_van_warehouse", label: __("Warehouse") },
			{ fieldname: "custom_driver_name", label: __("Driver") },
			{ fieldname: "status", label: __("Status") },
		],
		fields: [
			"name",
			"transaction_date",
			"custom_van_request_type",
			"custom_van_session",
			"custom_van",
			"custom_van_warehouse",
			"custom_driver_name",
			"status",
		],
	});
};

frappe.pages["van-stock-request"].on_page_show = function(wrapper) {
	wrapper.van_sales_wrapper?.refresh();
};
