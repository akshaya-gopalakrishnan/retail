import unittest
from unittest.mock import MagicMock, patch

import frappe

from retail.retail_app.page.retail_item_family_l import retail_item_family_l as page
from retail.retail_app.report.item_family_list import item_family_list as report


class TestItemFamilyPagination(unittest.TestCase):
	def setUp(self):
		flags_patch = patch.object(frappe.local, "flags", frappe._dict(in_test=True), create=True)
		flags_patch.start()
		self.addCleanup(flags_patch.stop)
		db_patch = patch.object(frappe, "db", MagicMock())
		db_patch.start()
		self.addCleanup(db_patch.stop)
	def test_page_lookahead_does_not_split_family_or_fetch_next_item_details(self):
		items = [frappe._dict(name=name) for name in ("A", "B", "C")]
		rows = [frappe._dict(item_code=name, idx=idx) for name, idx in
			[("A", 1), ("A", 2), ("B", None)]]
		with patch.object(frappe, "has_permission"), patch.object(frappe.db, "sql", return_value=items), \
			patch.object(page, "get_data", return_value=rows) as get_data:
			result = page.get_rows(page_length=2)
			self.assertTrue(result["has_more"])
			self.assertEqual([family["item_code"] for family in result["families"]], ["A", "B"])
			self.assertEqual(len(result["families"][0]["packings"]), 2)
			self.assertEqual(get_data.call_args.kwargs["item_codes"], ["A", "B"])

	def test_page_bounds_and_filter_are_applied_before_detail_loading(self):
		with patch.object(frappe, "has_permission"), patch.object(frappe.db, "sql", return_value=[]) as sql, \
			patch.object(page, "get_data", return_value=[]) as get_data:
			result = page.get_rows(filters={"barcode": "123"}, start=-5, page_length=10000)
			self.assertEqual(sql.call_args.args[1]["start"], 0)
			self.assertEqual(sql.call_args.args[1]["limit"], 101)
			self.assertEqual(sql.call_args.args[1]["barcode"], "%123%")
			self.assertFalse(result["has_more"])
			get_data.assert_called_once_with(frappe._dict(barcode="123"), item_codes=[])

	def test_stock_aggregation_is_restricted_to_page_items(self):
		with patch.object(frappe.db, "sql", return_value=[]) as sql:
			report.get_data(frappe._dict(), item_codes=["A", "B"])
			query, values = sql.call_args.args
			self.assertIn("where item_code in %(page_item_codes)s", query)
			self.assertIn("and item_code in %(page_item_codes)s", query)
			self.assertIn("and item.name in %(page_item_codes)s", query)
			self.assertEqual(values["page_item_codes"], ("A", "B"))
		with patch.object(frappe.db, "sql") as sql:
			self.assertEqual(report.get_data(frappe._dict(), item_codes=[]), [])
			sql.assert_not_called()

	def test_existing_unpaginated_response_is_preserved(self):
		with patch.object(frappe, "has_permission"), patch.object(page, "get_data", return_value=[]) as get_data:
			self.assertEqual(page.get_rows(), [])
			get_data.assert_called_once_with(frappe._dict())
