frappe.query_reports["Fast Moving Items"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), -30),
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
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
		},
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group",
		},
		{
			fieldname: "brand",
			label: __("Brand"),
			fieldtype: "Link",
			options: "Brand",
		},
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier",
		},
		{
			fieldname: "limit",
			label: __("Top"),
			fieldtype: "Int",
			default: 50,
		},
		{
			fieldname: "hide_zero_stock",
			label: __("Hide Zero Stock"),
			fieldtype: "Check",
			default: 0,
		},
	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname !== "movement_status" || !data) {
			return value;
		}

		const color_by_status = {
			"Stock Risk": "red",
			"Fast Moving": "green",
			"Moving": "blue",
		};
		const color = color_by_status[data.movement_status];

		if (!color) {
			return value;
		}

		return `<span class="indicator-pill ${color}">${value}</span>`;
	},
};
