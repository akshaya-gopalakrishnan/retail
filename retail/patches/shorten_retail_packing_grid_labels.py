import frappe


DOCFIELD_LABELS = {
	"purchase_rate": "Pur Rate",
	"selling_rate": "Sell Rate",
}

CUSTOM_FIELD_LABELS = {
	"purchase_net_rate": "Pur Rate Exc",
	"purchase_gross_rate": "Pur Rate Inc",
	"selling_net_rate": "Sell Rate Exc",
	"selling_gross_rate": "Sell Rate Inc",
}


def execute():
	for fieldname, label in DOCFIELD_LABELS.items():
		frappe.db.set_value(
			"DocField",
			{"parent": "Retail Packing Detail", "fieldname": fieldname},
			"label",
			label,
			update_modified=False,
		)

	for fieldname, label in CUSTOM_FIELD_LABELS.items():
		name = f"Retail Packing Detail-{fieldname}"
		if frappe.db.exists("Custom Field", name):
			frappe.db.set_value("Custom Field", name, "label", label, update_modified=False)

	frappe.clear_cache(doctype="Retail Packing Detail")
