frappe.query_reports["Daily Sales Summary"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
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
			fieldname: "counter",
			label: __("Counter"),
			fieldtype: "Link",
			options: "Counter",
		},
		{
			fieldname: "sales_channel",
			label: __("Sales Channel"),
			fieldtype: "Select",
			options: "\nTrading\nPOS",
		},
	],
};
