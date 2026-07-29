import frappe
from frappe.model.document import Document


class RetailPackingDetail(Document):
	def validate(self):
		if not self.packing_code:
			self.packing_code = make_packing_code(self.parent, self.uom, self.idx)
		item_name = get_item_display_name(self.parent)
		if not self.packing_name or is_auto_packing_name(self.packing_name, item_name, self.uom):
			self.packing_name = make_packing_name(item_name, self.uom, self.conversion_factor)


def make_packing_code(item_code, uom, idx=None):
	parts = [item_code, uom]
	if not item_code or not uom:
		parts.append(idx)
	return "-".join(str(part).strip().replace(" ", "-").upper() for part in parts if part)


def make_packing_name(item_name, uom, conversion_factor=None):
	parts = [str(item_name or "").strip()]
	uom_text = str(uom or "").strip()
	if uom_text:
		if conversion_factor:
			parts.append(f"{uom_text} x{format_conversion_factor(conversion_factor)}")
		else:
			parts.append(uom_text)
	return " - ".join(part for part in parts if part)


def is_auto_packing_name(packing_name, item_name, uom):
	packing_name = str(packing_name or "").strip()
	item_name = str(item_name or "").strip()
	uom = str(uom or "").strip()
	if not packing_name or not item_name or not uom:
		return False

	prefix = f"{item_name} - {uom}"
	return packing_name == prefix or packing_name.startswith(f"{prefix} x")


def format_conversion_factor(value):
	value = float(value or 0)
	if value.is_integer():
		return str(int(value))
	return str(value)


def get_item_display_name(item_code):
	if not item_code:
		return ""
	return frappe.db.get_value("Item", item_code, "item_name") or item_code
