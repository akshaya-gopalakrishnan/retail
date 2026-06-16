frappe.query_reports["Low Stock Reorder Report"] = {
	filters: [
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
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier",
		},
		{
			fieldname: "brand",
			label: __("Brand"),
			fieldtype: "Link",
			options: "Brand",
		},
		{
			fieldname: "only_low_stock",
			label: __("Only Low Stock"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "only_out_of_stock",
			label: __("Only Out of Stock"),
			fieldtype: "Check",
			default: 0,
		},
	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname !== "status" || !data) {
			return value;
		}

		const color_by_status = {
			"Out of Stock": "red",
			Critical: "orange",
			"Low Stock": "yellow",
			Healthy: "green",
		};
		const color = color_by_status[data.status];

		if (!color) {
			return value;
		}

		return `<span class="indicator-pill ${color}">${value}</span>`;
	},
};
