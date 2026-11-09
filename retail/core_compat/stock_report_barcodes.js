// Extend native filters without replacing the report's handlers or defaults.
for (const name of ["Stock Ledger", "Stock Balance"]) {
	const settings = frappe.query_reports[name];
	if (!settings || settings.filters.some((filter) => filter.fieldname === "barcode")) continue;
	const index = settings.filters.findIndex((filter) => filter.fieldname === "item_code");
	settings.filters.splice(index + 1, 0, {
		fieldname: "barcode",
		label: __("Barcode"),
		fieldtype: "Data",
	});
}
