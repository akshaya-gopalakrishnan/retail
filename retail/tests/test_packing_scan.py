import unittest
from unittest.mock import patch, MagicMock

import frappe
from retail.domains.item import packing_scan


class TestPackingScan(unittest.TestCase):
	def setUp(self):
		frappe.local.flags = frappe._dict(in_test=True)

	def test_exact_uom_uses_standard_conversion_prices_and_pricing_rules(self):
		for doctype in ["Sales Invoice", "Purchase Invoice", "Purchase Receipt", "Delivery Note"]:
			for factor in [21, 50, 100]:
				with self.subTest(doctype=doctype, factor=factor):
					packing = frappe._dict(parent="I-43", uom=f"Box-{factor}",
						conversion_factor=factor, disabled=0)
					args = dict(doctype=doctype, item_code="I-43", barcode="123",
						uom=packing.uom, conversion_factor=999)
					result = {"rate": 87, "discount_amount": 13, "pricing_rules": "rule"}
					with patch.object(packing_scan, "resolve_packing", return_value=packing), patch.object(
						packing_scan, "standard_item_details", return_value=result
					) as standard:
						self.assertIs(packing_scan.get_item_details(args), result)
						passed = standard.call_args.args[0]
						self.assertEqual(passed.uom, packing.uom)
						self.assertNotIn("conversion_factor", passed)
						self.assertNotIn("ignore_pricing_rule", passed)

	def test_nonpacking_keeps_standard_behavior(self):
		with patch.object(packing_scan, 'standard_item_details', return_value={'rate': 42}) as standard:
			self.assertEqual(packing_scan.get_item_details({'doctype': 'Sales Invoice'}), {'rate': 42})
			standard.assert_called_once()

	def test_ambiguous_and_disabled_barcodes_rejected(self):
		for rows in [[frappe._dict(), frappe._dict()], [frappe._dict(parent='I-43', disabled=1)]]:
			with patch.object(frappe, 'get_all', return_value=rows), patch.object(frappe, 'get_doc'), patch.object(
				frappe, 'throw', side_effect=ValueError
			):
				with self.assertRaises(ValueError):
					packing_scan.resolve_packing('123')
