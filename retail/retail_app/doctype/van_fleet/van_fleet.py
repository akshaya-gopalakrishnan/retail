import frappe
from frappe import _
from frappe.model.document import Document


class VanFleet(Document):
	def validate(self):
		if self.vehicle_status not in ("Inactive", "Maintenance") or self.is_new():
			return
		# Check on every save, including fleets already in an inconsistent state.
		sessions = self._open_sessions()
		if sessions:
			frappe.throw(
				_("Close the open Van Session(s) {0} before setting Vehicle Status to {1}.").format(
					", ".join(frappe.utils.get_link_to_form("Van Session", name) for name in sessions),
					frappe.utils.escape_html(self.vehicle_status),
				),
				title=_("Open Van Session"),
			)

	def _open_sessions(self):
		return frappe.get_all(
			"Van Session", filters={"van": self.name, "status": "Open", "docstatus": ["<", 2]},
			pluck="name", order_by="creation asc",
		)

	@frappe.whitelist()
	def get_open_sessions(self):
		self.check_permission("write")
		return self._open_sessions() if not self.is_new() else []
