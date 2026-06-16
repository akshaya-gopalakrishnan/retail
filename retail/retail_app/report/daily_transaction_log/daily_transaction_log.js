frappe.query_reports["Daily Transaction Log"] = {
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
			fieldname: "cashier",
			label: __("Cashier"),
			fieldtype: "Link",
			options: "User",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nPaid\nUnpaid\nOverdue\nReturn\nCancelled",
		},
		{
			fieldname: "payment_mode",
			label: __("Payment Mode"),
			fieldtype: "Link",
			options: "Mode of Payment",
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname !== "display_status" || !data) {
			return value;
		}

		const color_by_status = {
			Paid: "green",
			Unpaid: "orange",
			Overdue: "orange",
			Return: "blue",
			Cancelled: "red",
		};
		const color = color_by_status[data.display_status];

		if (!color) {
			return value;
		}

		return `<span class="indicator-pill ${color}">${value}</span>`;
	},
};
