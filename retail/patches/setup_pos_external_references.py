"""Install permanent offline shift/session identities without renaming documents."""
import frappe


def execute():
	for name in ("pos_cashier_shift", "pos_counter_session", "pos_sync_log"):
		frappe.reload_doc("retail_app", "doctype", name, force=True)
