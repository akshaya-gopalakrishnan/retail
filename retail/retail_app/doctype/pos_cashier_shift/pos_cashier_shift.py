import frappe
from frappe import _
from frappe.model.document import Document


class POSCashierShift(Document):
	def validate(self):
		if not self.branch:
			frappe.throw(_("Branch is required."))
		if not self.cashier_employee:
			frappe.throw(_("Cashier Employee is required."))
		if not self.opening_time:
			frappe.throw(_("Opening Time is required."))

		if not self.cashier_name:
			self.cashier_name = frappe.db.get_value("Employee", self.cashier_employee, "employee_name")

		if self.status in ("Open", "Paused"):
			duplicate = frappe.db.get_value(
				"POS Cashier Shift",
				{
					"cashier_employee": self.cashier_employee,
					"status": ["in", ["Open", "Paused"]],
					"name": ["!=", self.name],
				},
				"name",
			)
			if duplicate:
				frappe.throw(_("Cashier already has an open shift: {0}").format(duplicate))
