from frappe.model.document import Document

from retail.restaurant.defaults import single_branch
from retail.restaurant.naming import next_numeric_id


class RestaurantTable(Document):
	def autoname(self):
		self.name = next_numeric_id(self.doctype)

	def before_validate(self):
		if not self.branch:
			self.branch = single_branch()
