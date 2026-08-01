import frappe


no_cache = 1


def get_context(context):
	context.no_cache = 1
	context.title = "CELESTA ERP"
	context.show_sidebar = False
	context.hide_login = False
	context.is_logged_in = frappe.session.user != "Guest"
