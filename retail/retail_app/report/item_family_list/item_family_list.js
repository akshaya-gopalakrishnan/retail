frappe.query_reports["Item Family List"] = {
	onload() {
		frappe.set_route("retail-item-family-l");
	},
	filters: [
		{ fieldname: "item_code", label: __("Item Code"), fieldtype: "Link", options: "Item" },
		{ fieldname: "item_group", label: __("Item Group"), fieldtype: "Link", options: "Item Group" },
		{ fieldname: "brand", label: __("Brand"), fieldtype: "Link", options: "Brand" },
		{ fieldname: "barcode", label: __("Barcode"), fieldtype: "Data" },
		{
			fieldname: "disabled",
			label: __("Item Disabled"),
			fieldtype: "Select",
			options: "\n0\n1",
			default: "0",
		},
		{
			fieldname: "packing_disabled",
			label: __("Packing Disabled"),
			fieldtype: "Select",
			options: "\n0\n1",
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "item_code" && data?.idx === 1) {
			return `<strong>${value}</strong>`;
		}
		return value;
	},
};
