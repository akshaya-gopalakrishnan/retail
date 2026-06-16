import frappe
from frappe import _
from frappe.model.document import Document


class POSBranchCounter(Document):
	def autoname(self):
		self.name = f"{self.branch}-{self.counter_code}"

	def validate(self):
		if not self.branch:
			frappe.throw(_("Branch is required."))
		if not self.counter_code:
			frappe.throw(_("Counter Code is required."))
		if not self.company:
			frappe.throw(_("Company is required."))
		if not self.warehouse:
			frappe.throw(_("Warehouse is required."))
		if not self.cost_center:
			frappe.throw(_("Cost Center is required."))

		duplicate = frappe.db.get_value(
			"POS Branch Counter",
			{
				"branch": self.branch,
				"counter_code": self.counter_code,
				"name": ["!=", self.name],
			},
			"name",
		)
		if duplicate:
			frappe.throw(_("Counter Code must be unique within a branch."))
