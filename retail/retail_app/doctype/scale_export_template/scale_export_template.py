import frappe
from frappe import _
from frappe.model.document import Document


class ScaleExportTemplate(Document):
	def validate(self):
		if not self.columns:
			frappe.throw(_("Add at least one export column."))
