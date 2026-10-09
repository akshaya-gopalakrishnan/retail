from frappe import _

from retail.van_permissions import validate_van_document_access


def validate_van_customer_access(doc, method=None):
	validate_van_document_access(
		doc,
		"Customer",
		_("You are not allowed to create or update Van Customers."),
	)
