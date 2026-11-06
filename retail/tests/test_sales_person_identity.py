from unittest import TestCase
from unittest.mock import patch

import frappe

from retail.sales_person_identity import before_naming


class TestSalesPersonIdentity(TestCase):
	def test_duplicate_display_names_have_distinct_native_names(self):
		for code in ("SP-1", "SP-2"):
			doc = frappe._dict(custom_document_code=code, custom_display_name="Ahmed")
			before_naming(doc)
			self.assertEqual(doc.sales_person_name, code + " - Ahmed")
			self.assertEqual(doc.custom_display_name, "Ahmed")

	def test_tree_and_legacy_creation_input(self):
		doc = frappe._dict(custom_document_code="SP-3", sales_person_name="Ahmed")
		before_naming(doc)
		self.assertEqual(doc.custom_display_name, "Ahmed")
		self.assertEqual(doc.sales_person_name, "SP-3 - Ahmed")

	def test_code_generated_when_missing(self):
		doc = frappe._dict(custom_display_name="Ahmed")
		with patch("retail.sales_person_identity.assign", side_effect=lambda d: d.update(custom_document_code="SP-4")):
			before_naming(doc)
		self.assertEqual(doc.sales_person_name, "SP-4 - Ahmed")
