import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class VanSession(Document):
	def validate(self):
		self.validate_session()

	def before_update_after_submit(self):
		self.validate_session()

	def on_cancel(self):
		self.status = "Cancelled"

	def validate_session(self):
		self.validate_required_details()
		self.apply_open_close_timestamps()
		self.validate_closing_values()
		self.validate_closing_updates()
		self.validate_single_open_session()

	def validate_required_details(self):
		for fieldname, label in (
			("session_date", _("Session Date")),
			("van", _("Van")),
			("van_warehouse", _("Van Warehouse")),
			("driver", _("Driver")),
		):
			if not self.get(fieldname):
				frappe.throw(_("{0} is required for Van Session.").format(label))

		van_warehouse = frappe.db.get_value("Van Fleet", self.van, "van_warehouse")
		if not van_warehouse:
			frappe.throw(_("Van {0} does not have a warehouse.").format(frappe.bold(self.van)))

		if self.van_warehouse != van_warehouse:
			frappe.throw(
				_("Van Warehouse must match the selected Van {0}.").format(frappe.bold(self.van))
			)

	def apply_open_close_timestamps(self):
		if self.status == "Open" and not self.open_time:
			self.open_time = now_datetime()

		if self.status == "Closed" and not self.close_time:
			self.close_time = now_datetime()

	def validate_closing_values(self):
		if flt(self.opening_cash) < 0:
			frappe.throw(_("Opening Cash cannot be negative."))

		if self.closing_cash is not None and flt(self.closing_cash) < 0:
			frappe.throw(_("Closing Cash cannot be negative."))

		if self.status != "Closed":
			return

		if self.closing_cash in (None, ""):
			frappe.throw(_("Closing Cash is required to close a Van Session."))

		if self.opening_km is not None and self.closing_km is not None:
			if flt(self.closing_km) < flt(self.opening_km):
				frappe.throw(_("Closing KM cannot be less than Opening KM."))

	def validate_closing_updates(self):
		if self.status == "Closed":
			return

		if self.is_new():
			for fieldname, label in self.get_closing_fields():
				value = self.get(fieldname)
				is_blank = not flt(value) if fieldname in ("closing_cash", "closing_km") else value in (None, "")
				if not is_blank:
					frappe.throw(_("{0} can only be set when Van Session status is Closed.").format(label))
			return

		previous = self.get_doc_before_save()
		if not previous:
			return

		for fieldname, label in self.get_closing_fields():
			if fieldname in ("closing_cash", "closing_km"):
				# Frappe stores blank Currency/Float fields as zero when saving.
				changed = flt(self.get(fieldname)) != flt(previous.get(fieldname))
			else:
				changed = self.has_value_changed(fieldname)
			if changed:
				frappe.throw(_("{0} can only be changed when Van Session status is Closed.").format(label))

	def get_closing_fields(self):
		return (
			("closing_cash", _("Closing Cash")),
			("closing_km", _("Closing KM")),
			("close_time", _("Close Time")),
		)

	def validate_single_open_session(self):
		if self.status != "Open":
			return

		open_van_session = self.get_existing_open_session("van", self.van)
		if open_van_session:
			frappe.throw(
				_("Van {0} already has open Van Session {1}.")
				.format(frappe.bold(self.van), frappe.bold(open_van_session))
			)

		open_driver_session = self.get_existing_open_session("driver", self.driver)
		if open_driver_session:
			frappe.throw(
				_("Driver {0} already has open Van Session {1}.")
				.format(frappe.bold(self.driver), frappe.bold(open_driver_session))
			)

	def get_existing_open_session(self, fieldname, value):
		if not value:
			return None

		filters = {
			fieldname: value,
			"status": "Open",
			"docstatus": ["<", 2],
			"name": ["!=", self.name],
		}
		return frappe.db.get_value("Van Session", filters, "name")
