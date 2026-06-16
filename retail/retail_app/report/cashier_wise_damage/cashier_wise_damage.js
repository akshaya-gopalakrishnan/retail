frappe.query_reports["Cashier Wise Damage"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company") },
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.add_months(frappe.datetime.get_today(), -1), reqd: 1 },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "warehouse", label: __("Warehouse"), fieldtype: "MultiSelectList", options: "Warehouse", get_data: (txt) => frappe.db.get_link_options("Warehouse", txt) },
	],
};
