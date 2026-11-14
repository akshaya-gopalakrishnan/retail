"""Enable customer-managed POS profiles on sites with custom permissions."""

import frappe


def execute():
	from retail.access_defaults import grant

	grant("POS Operator Privilege", "Customer Administrator", {
		"read": 1, "write": 1, "create": 1,
	})
	frappe.clear_cache(doctype="POS Operator Privilege")
