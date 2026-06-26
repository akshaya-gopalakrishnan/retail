"""Safe defaults for purchase rates in Retail Packing Detail rows."""

from __future__ import annotations

import frappe


PACKING_RATE_CLIENT_SCRIPT = '''frappe.ui.form.on("Item", {
	last_purchase_rate(frm) {
		fill_empty_packing_purchase_rates(frm);
	},
	custom_default_purchase_rate(frm) {
		fill_empty_packing_purchase_rates(frm);
	},
});

frappe.ui.form.on("Retail Packing Detail", {
	conversion_factor(frm, cdt, cdn) {
		set_default_packing_purchase_rate(frm, cdt, cdn);
	},
	custom_retail_packing_detail_add(frm, cdt, cdn) {
		set_default_packing_purchase_rate(frm, cdt, cdn);
	},
});

function get_packing_base_purchase_rate(frm) {
	return flt(frm.doc.custom_default_purchase_rate || frm.doc.last_purchase_rate);
}

function set_default_packing_purchase_rate(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (flt(row.purchase_rate)) return;

	const base_rate = get_packing_base_purchase_rate(frm);
	if (!base_rate) return;

	frappe.model.set_value(
		cdt,
		cdn,
		"purchase_rate",
		base_rate * flt(row.conversion_factor || 1)
	);
}

function fill_empty_packing_purchase_rates(frm) {
	(frm.doc.custom_retail_packing_detail || []).forEach((row) => {
		if (!flt(row.purchase_rate)) {
			set_default_packing_purchase_rate(frm, row.doctype, row.name);
		}
	});
}
'''


def ensure_packing_purchase_rate_script():
	"""Ensure packing purchase rates are defaulted, never overwritten."""
	if not frappe.db.exists("Client Script", "RPD pr calculation"):
		return

	doc = frappe.get_doc("Client Script", "RPD pr calculation")
	if doc.script != PACKING_RATE_CLIENT_SCRIPT:
		doc.script = PACKING_RATE_CLIENT_SCRIPT
		doc.enabled = 1
		doc.save(ignore_permissions=True)

	frappe.clear_cache(doctype="Item")
