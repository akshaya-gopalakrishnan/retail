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

const counter_settings = frappe.listview_settings["Counter"];
counter_settings.add_fields = [
	...(counter_settings.add_fields || []),
	"counter_name",
];
counter_settings.formatters = counter_settings.formatters || {};
counter_settings.formatters.name = (value, df, doc) =>
	frappe.utils.escape_html(doc.counter_name || value || "");
