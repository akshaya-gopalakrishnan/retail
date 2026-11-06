from unittest import TestCase
from unittest.mock import Mock, patch

import frappe

from retail.sales_order_sales_person import assign_creator, validate


class TestSalesOrderSalesPerson(TestCase):
	def test_creator_identity_overrides_client_values(self):
		doc = frappe._dict(sales_person_id="OTHER", sales_person_name="Other")
		with patch.object(frappe.local, "session", frappe._dict(user="creator@example.com"), create=True), patch(
			"retail.sales_order_sales_person.get_sales_person_identity",
			return_value={"sales_person_id": "SP-1", "sales_person_name": "Ahmed"},
		) as lookup:
			assign_creator(doc)
			lookup.assert_called_once_with("creator@example.com")
		self.assertEqual(doc.sales_person_id, "SP-1")
		self.assertEqual(doc.sales_person_name, "Ahmed")

	def test_draft_name_follows_selected_id(self):
		doc = frappe._dict(docstatus=0, sales_person_id="SP-2", sales_person_name="Old")
		with patch.object(frappe, "db", new=Mock()) as db:
			db.get_value.return_value = frappe._dict(custom_display_name="New Name", sales_person_name="SP-2 - New Name")
			validate(doc)
			db.get_value.assert_called_once_with(
				"Sales Person", {"custom_document_code": "SP-2"},
				["custom_display_name", "sales_person_name"], as_dict=True,
			)
		self.assertEqual(doc.sales_person_name, "New Name")

	def test_submitted_name_is_preserved(self):
		doc = frappe._dict(docstatus=1, sales_person_id="SP-1", sales_person_name="Original")
		with patch.object(frappe, "db", new=Mock()) as db:
			validate(doc)
			db.get_value.assert_not_called()
		self.assertEqual(doc.sales_person_name, "Original")
