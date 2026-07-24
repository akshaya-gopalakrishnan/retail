from hashlib import sha256
from secrets import token_hex

import frappe
from frappe import _
from frappe.utils import cint


def hash_quick_pin(quick_pin, salt):
	return sha256(f"{salt}:{quick_pin}".encode("utf-8")).hexdigest()


def make_quick_pin_hash(quick_pin):
	salt = token_hex(16)
	return salt, hash_quick_pin(str(quick_pin), salt)


def validate_quick_pin(quick_pin):
	if quick_pin in (None, ""):
		return
	quick_pin = str(quick_pin)
	if not quick_pin.isdigit() or len(quick_pin) != 4:
		frappe.throw(_("POS Quick PIN must be exactly 4 digits."))


def apply_employee_pos_login(doc, method=None):
	if not doc.meta.has_field("pos_quick_pin"):
		return

	if doc.get("pos_login_user") and doc.get("user_id") != doc.get("pos_login_user"):
		doc.user_id = doc.pos_login_user

	quick_pin = doc.get("pos_quick_pin")
	if quick_pin:
		validate_quick_pin(quick_pin)
		salt, pin_hash = make_quick_pin_hash(quick_pin)
		doc.pos_quick_pin_salt = salt
		doc.pos_quick_pin_hash = pin_hash
		doc.pos_login_enabled = 1
		doc.pos_quick_pin = None


def sync_employee_pos_user(doc, method=None):
	if not doc.meta.has_field("pos_login_user") or not doc.get("pos_login_user"):
		return
	if frappe.db.exists("User", doc.pos_login_user):
		frappe.db.set_value("User", doc.pos_login_user, "pos_cashier_employee", doc.name, update_modified=False)


def apply_user_pos_login(doc, method=None):
	if not doc.meta.has_field("pos_cashier_employee"):
		return

	employee = doc.get("pos_cashier_employee")
	quick_pin = doc.get("pos_quick_pin")
	if quick_pin:
		validate_quick_pin(quick_pin)
	if not employee:
		if quick_pin:
			frappe.throw(_("Select POS Cashier Employee before setting POS Quick PIN."))
		return
	if not frappe.db.exists("Employee", employee):
		frappe.throw(_("POS Cashier Employee {0} was not found.").format(employee))

	values = {
		"pos_login_enabled": cint(doc.get("pos_login_enabled")),
		"pos_login_user": doc.name,
		"user_id": doc.name,
	}
	if quick_pin:
		salt, pin_hash = make_quick_pin_hash(quick_pin)
		values.update({"pos_quick_pin_salt": salt, "pos_quick_pin_hash": pin_hash})
		doc.pos_quick_pin = None

	frappe.db.set_value("Employee", employee, values, update_modified=True)
