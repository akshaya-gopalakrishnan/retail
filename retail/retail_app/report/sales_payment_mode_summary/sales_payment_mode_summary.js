frappe.query_reports["Sales Payment Mode Summary"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "payment_mode",
			label: __("Payment Mode"),
			fieldtype: "Link",
			options: "Mode of Payment",
		},
		{
			fieldname: "include_pos_invoices",
			label: __("Include POS Invoices"),
			fieldtype: "Check",
			default: 0,
		},
	],
};
