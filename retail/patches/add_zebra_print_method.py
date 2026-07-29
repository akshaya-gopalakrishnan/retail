import frappe


def execute():
	if not frappe.db.exists("DocType", "Zebra Label Format"):
		return
	if not frappe.db.has_column("Zebra Label Format", "print_method"):
		return

	frappe.db.sql(
		"""
		update `tabZebra Label Format`
		set print_method = 'Network Printer'
		where ifnull(print_method, '') = ''
		"""
	)
