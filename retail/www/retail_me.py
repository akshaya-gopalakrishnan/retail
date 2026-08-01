import frappe
from frappe import _


no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.throw(_("You need to be logged in to access this page"), frappe.PermissionError)

	if frappe.db.get_value("User", frappe.session.user, "user_type") == "System User":
		frappe.local.flags.redirect_location = "/app"
		raise frappe.Redirect

	from frappe.www.me import get_context as get_frappe_me_context

	return get_frappe_me_context(context)
