import frappe
from frappe import _
from frappe.model.document import Document


class POSCounterSession(Document):
	def validate(self):
		if not self.branch:
			frappe.throw(_("Branch is required."))
		if not self.counter:
			frappe.throw(_("Counter is required."))
		if not self.cashier_shift:
			frappe.throw(_("Cashier Shift is required."))
		if not self.cashier_employee:
			frappe.throw(_("Cashier Employee is required."))
		if not self.started_at:
			frappe.throw(_("Started At is required."))

		if not self.counter_code:
			self.counter_code = frappe.db.get_value("POS Branch Counter", self.counter, "counter_code")

		if self.status == "Active":
			duplicate_counter = frappe.db.get_value(
				"POS Counter Session",
				{"counter": self.counter, "status": "Active", "name": ["!=", self.name]},
				"name",
			)
			if duplicate_counter:
				frappe.throw(_("Counter already has an active session: {0}").format(duplicate_counter))

			duplicate_shift = frappe.db.get_value(
				"POS Counter Session",
				{"cashier_shift": self.cashier_shift, "status": "Active", "name": ["!=", self.name]},
				"name",
			)
			if duplicate_shift:
				frappe.throw(_("Cashier shift already has an active counter session: {0}").format(duplicate_shift))
