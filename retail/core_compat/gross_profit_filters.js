(() => {
	const settings = frappe.query_reports["Gross Profit"];
	if (!settings?.filters || settings.filters.some(f => f.fieldname === "sales_source")) return;
	const companyIndex = settings.filters.findIndex(f => f.fieldname === "company");
	settings.filters.splice(companyIndex + 1, 0, {
		fieldname: "sales_source",
		label: __("Sales Source"),
		fieldtype: "Select",
		options: ["Trading Sales", "POS Sales", "Trading + POS Sales"].join("\n"),
		default: "Trading Sales",
		reqd: 1,
		description: __("POS sales use posted Sales Invoices, including POS closing entries."),
	});
})();
