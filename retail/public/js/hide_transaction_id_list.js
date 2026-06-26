// Transaction names remain the permanent system identifiers, but they do not
// need to occupy a client-facing list column when a useful business title is
// already available.
[
	"Journal Entry",
	"Payment Entry",
	"Sales Invoice",
	"Purchase Invoice",
	"Sales Order",
	"Purchase Order",
	"Delivery Note",
	"Purchase Receipt",
	"Stock Entry",
	"Material Request",
	"Customer",
	"Item",
	"Supplier",
	"Serial and Batch Bundle",
	"Bin",
	"Sales Taxes and Charges Template",
	"Counter",
].forEach((doctype) => {
	frappe.listview_settings[doctype] = frappe.listview_settings[doctype] || {};
	Object.assign(frappe.listview_settings[doctype], {
		hide_name_column: true,
		hide_name_filter: true,
	});
});

// Sales Invoice stores Counter's internal name as the link value. Show the
// business-facing Counter Name in the list while retaining that stable link.
const sales_invoice_settings = frappe.listview_settings["Sales Invoice"];
sales_invoice_settings.add_fields = [
	...(sales_invoice_settings.add_fields || []),
	"custom_counter_name",
];
sales_invoice_settings.formatters = sales_invoice_settings.formatters || {};
sales_invoice_settings.formatters.custom_counter = (value, df, doc) =>
	frappe.utils.escape_html(doc.custom_counter_name || value || "");
