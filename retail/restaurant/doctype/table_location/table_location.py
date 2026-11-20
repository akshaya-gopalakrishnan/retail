from frappe.model.document import Document

from retail.restaurant.naming import next_numeric_id


class TableLocation(Document):
	def autoname(self):
		self.name = next_numeric_id(self.doctype)
