import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class ScaleBarcodeFormat(Document):
	def validate(self):
		self.validate_positions()

	def validate_positions(self):
		for fieldname in (
			"total_length",
			"prefix_start",
			"prefix_length",
			"plu_start",
			"plu_length",
			"value_start",
			"value_length",
		):
			if cint(self.get(fieldname)) <= 0:
				frappe.throw(_("{0} must be greater than zero.").format(self.meta.get_label(fieldname)))

		total_length = cint(self.total_length)
		for label, start, length in (
			(_("Prefix"), self.prefix_start, self.prefix_length),
			(_("PLU"), self.plu_start, self.plu_length),
			(_("Value"), self.value_start, self.value_length),
		):
			if cint(start) + cint(length) - 1 > total_length:
				frappe.throw(_("{0} position is outside the barcode length.").format(label))


def ensure_default_scale_barcode_format():
	if frappe.db.exists("Scale Barcode Format", "Prefix 99 - 2-5-5"):
		return

	doc = frappe.get_doc(
		{
			"doctype": "Scale Barcode Format",
			"format_name": "Prefix 99 - 2-5-5",
			"enabled": 1,
			"prefix": "99",
			"total_length": 13,
			"prefix_start": 1,
			"prefix_length": 2,
			"plu_start": 3,
			"plu_length": 5,
			"value_start": 8,
			"value_length": 5,
			"value_type": "WEIGHT",
			"decimal_places": 3,
			"check_digit_enabled": 1,
			"check_digit_method": "EAN13",
		}
	)
	doc.insert(ignore_permissions=True)
