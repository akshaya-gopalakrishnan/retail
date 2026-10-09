import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class POSOperatorPrivilege(Document):
	def on_update(self):
		# Refresh every assignment even when only the shared profile changed.
		frappe.db.set_value(
			"Employee", {"pos_operator_privilege": self.name},
			"modified", now_datetime(), update_modified=False,
		)
