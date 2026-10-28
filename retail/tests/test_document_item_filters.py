"""Native list/count integration using synthetic rows and rolled-back writes."""

import unittest
from unittest.mock import patch
from uuid import uuid4

import frappe

from retail import document_item_filters as filters


class TestDocumentItemFilters(unittest.TestCase):
	def setUp(self):
		self.user = frappe.session.user
		frappe.set_user("Administrator")
		self.form = frappe.local.form_dict
		self.token = "retail-filter-test-" + uuid4().hex
		frappe.db.savepoint("item_filter_test")

	def tearDown(self):
		frappe.db.rollback(save_point="item_filter_test")
		frappe.local.form_dict = self.form
		frappe.flags[filters.FLAG] = None
		frappe.set_user(self.user)

	def insert(self, doctype, suffix, **values):
		doc = frappe.get_doc(dict(doctype=doctype, name=self.token + suffix, **values))
		doc.db_insert()
		return doc.name

	def request(self, parent, criteria, count=False):
		frappe.local.form_dict = frappe._dict(
			doctype=parent, fields=["name"], filters=[["name", "like", self.token + "%"]],
			order_by="name asc", start=0, page_length=20, retail_item_filters=criteria,
		)
		return filters.get_count() if count else filters.get()

	def rows(self, result):
		if not result:
			return set()
		return {row[result["keys"].index("name")] for row in result["values"]}

	def test_all_five_lists_match_items_without_duplicate_parents(self):
		for index, (parent, child) in enumerate(filters.DOCTYPES.items()):
			name = self.insert(parent, f"-parent-{index}")
			for row in range(2):
				self.insert(child, f"-row-{index}-{row}", parent=name, parenttype=parent,
					parentfield="items", item_code="FILTER-ITEM")
			self.assertEqual(self.rows(self.request(parent, {"item_code": "FILTER-ITEM"})), {name})
			self.assertEqual(self.request(parent, {"item_code": "FILTER-ITEM"}, count=True), 1)
			self.assertEqual(self.rows(self.request(parent, {"item_code": "OTHER"})), set())
			# Parent permission conditions must constrain both native queries.
			with patch("frappe.model.db_query.DatabaseQuery.get_permission_query_conditions", return_value="1=0"):
				self.assertEqual(self.rows(self.request(parent, {"item_code": "FILTER-ITEM"})), set())
				self.assertEqual(self.request(parent, {"item_code": "FILTER-ITEM"}, count=True), 0)

	def test_legacy_and_bundle_serials_batches_and_same_item_row(self):
		for index, (parent, child) in enumerate(filters.DOCTYPES.items()):
			if parent == "Purchase Order":
				continue
			legacy = self.insert(parent, f"-legacy-{index}")
			bundled = self.insert(parent, f"-bundled-{index}")
			bundle = self.token + f"-bundle-{index}"
			self.insert("Serial and Batch Entry", f"-entry-{index}", parent=bundle,
				parenttype="Serial and Batch Bundle", parentfield="entries", serial_no="SER-1", batch_no="BATCH-1")
			self.insert(child, f"-legacy-row-{index}", parent=legacy, parenttype=parent,
				parentfield="items", item_code="ITEM-A", serial_no="SER-1\r\nSER-10", batch_no="BATCH-1")
			self.insert(child, f"-bundle-row-{index}", parent=bundled, parenttype=parent,
				parentfield="items", item_code="ITEM-A", serial_and_batch_bundle=bundle)
			self.insert(child, f"-different-row-{index}", parent=bundled, parenttype=parent,
				parentfield="items", item_code="ITEM-B", batch_no="BATCH-2")
			for criteria in ({"serial_no": "SER-1"}, {"batch_no": "BATCH-1"},
				{"item_code": "ITEM-A", "serial_no": "SER-1", "batch_no": "BATCH-1"}):
				self.assertEqual(self.rows(self.request(parent, criteria)), {legacy, bundled})
				self.assertEqual(self.request(parent, criteria, count=True), 2)
			self.assertEqual(self.rows(self.request(parent, {"serial_no": "SER"})), set())
			self.assertEqual(self.rows(self.request(parent, {"item_code": "ITEM-B", "serial_no": "SER-1"})), set())
			self.assertEqual(self.rows(self.request(parent, {"batch_no": "x' OR 1=1 --"})), set())

	def test_invalid_input_and_missing_permissions_are_rejected(self):
		for doctype, criteria in (("Item", {}), ("Sales Invoice", {"unknown": "x"}),
			("Sales Invoice", {"serial_no": ["x"]})):
			with self.assertRaises(frappe.ValidationError):
				filters.normalize(doctype, criteria)
		with self.assertRaises(frappe.PermissionError):
			filters.normalize("Purchase Order", {"serial_no": "SER-1"})
		with patch.object(filters.frappe, "has_permission", side_effect=frappe.PermissionError):
			with self.assertRaises(frappe.PermissionError):
				self.request("Sales Invoice", {"item_code": "ITEM-A"})
		self.assertIsNone(frappe.flags.get(filters.FLAG))

	def test_conditions_only_apply_in_the_targeted_request(self):
		self.assertEqual(filters.query_conditions(doctype="Sales Invoice"), "")
		frappe.flags[filters.FLAG] = ("Sales Invoice", {"item_code": "ITEM-A"})
		self.assertEqual(filters.query_conditions(doctype="Purchase Invoice"), "")
