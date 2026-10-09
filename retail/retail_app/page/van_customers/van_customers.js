frappe.pages["van-customers"].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Van Customers"),
		single_column: false,
	});

	wrapper.van_sales_wrapper = new retail.VanDocumentWrapper({
		page,
		doctype: "Customer",
		flag_field: "custom_is_van_customer",
		title: __("Van Customer"),
		new_doc_values: {
			custom_is_van_customer: 1,
		},
	});
};

frappe.pages["van-customers"].on_page_show = function(wrapper) {
	wrapper.van_sales_wrapper?.refresh();
};
