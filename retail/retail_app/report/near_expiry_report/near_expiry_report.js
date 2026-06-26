frappe.query_reports["Near Expiry Report"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company") },
		{ fieldname: "days_to_expire", label: __("Days to Expire"), fieldtype: "Int", default: 30, reqd: 1 },
		{ fieldname: "warehouse", label: __("Warehouse"), fieldtype: "MultiSelectList", options: "Warehouse", get_data: (txt) => frappe.db.get_link_options("Warehouse", txt) },
		{ fieldname: "item_code", label: __("Item Code"), fieldtype: "Link", options: "Item" },
		{ fieldname: "supplier", label: __("Supplier"), fieldtype: "Link", options: "Supplier" },
	],
};
