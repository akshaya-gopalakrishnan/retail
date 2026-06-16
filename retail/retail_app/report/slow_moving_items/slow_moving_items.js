frappe.query_reports["Slow Moving Items"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), -90),
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
			fieldname: "max_net_qty",
			label: __("Max Net Qty"),
			fieldtype: "Float",
			default: 5,
		},
		{
			fieldname: "only_no_sales",
			label: __("Only No Sales"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "only_with_stock",
			label: __("Only With Stock"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "limit",
			label: __("Top"),
			fieldtype: "Int",
			default: 100,
		},
	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname !== "movement_status" || !data) {
			return value;
		}

		const color_by_status = {
			"No Sales": "red",
			"Very Slow": "orange",
			"Slow Moving": "yellow",
		};
		const color = color_by_status[data.movement_status];

		if (!color) {
			return value;
		}

		return `<span class="indicator-pill ${color}">${value}</span>`;
	},
};
