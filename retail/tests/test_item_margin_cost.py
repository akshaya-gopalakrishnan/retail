import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace

import frappe
from retail.domains.item import margin_cost, vat_pricing


class ItemValues(frappe._dict):
	def set(self, key, value):
		self[key] = value


class TestItemMarginCost(unittest.TestCase):
	def setUp(self):
		self.db_patch = patch.object(frappe, "db", SimpleNamespace(sql=Mock()))
		self.db_patch.start()
		self.addCleanup(self.db_patch.stop)

	def test_zero_purchase_entry_uses_stock_value_per_unit(self):
		doc = ItemValues(name="Finished", custom_purchase_rate_entry=0,
			custom_purchase_net_rate=0, standard_rate=7.14, custom_sales_net_rate=7.14)
		with patch.object(frappe.defaults, "get_user_default", return_value="DAB"), \
			patch.object(frappe, "get_list", return_value=["DAB", "Other"]), \
			patch.object(frappe.db, "sql", return_value=[frappe._dict(value=1773.37, qty=248)]) as sql, \
			patch.object(frappe, "get_system_settings", return_value="Banker's Rounding"):
			vat_pricing._update_margin(doc)
			self.assertAlmostEqual(doc.custom_margin, -0.01)
			self.assertLess(doc.custom_margin_, 0)
			self.assertEqual(sql.call_args.args[1], ("Finished", ("DAB",)))

	def test_maintained_purchase_cost_remains_authoritative(self):
		with patch.object(frappe.db, "sql") as sql:
			result = margin_cost.get_margin_cost(ItemValues(name="Bought", custom_purchase_net_rate=4))
			self.assertEqual(result["cost"], 4)
			sql.assert_not_called()

	def test_missing_cost_does_not_use_selling_rate(self):
		doc = ItemValues(__islocal=1, standard_rate=7.14)
		vat_pricing._update_margin(doc)
		self.assertIsNone(doc.custom_margin)
		self.assertIsNone(doc.custom_margin_)

	def test_disallowed_default_company_is_not_queried(self):
		with patch.object(frappe.defaults, "get_user_default", return_value="Other"), \
			patch.object(frappe, "get_list", return_value=["DAB"]), \
			patch.object(frappe.db, "sql") as sql:
			self.assertIsNone(margin_cost.get_margin_cost(ItemValues(name="Finished"))["cost"])
			sql.assert_not_called()

	def test_weighted_stock_cost_uses_value_not_average_of_rates(self):
		with patch.object(frappe.defaults, "get_user_default", return_value=None), \
			patch.object(frappe, "get_list", return_value=["DAB"]), \
			patch.object(frappe.db, "sql", return_value=[frappe._dict(value=100, qty=30)]):
			self.assertAlmostEqual(margin_cost.get_margin_cost(ItemValues(name="Finished"))["cost"], 100 / 30)
