import unittest
from unittest.mock import patch

import frappe

from retail.api import pos_sync


class TestPOSMasterCompatibility(unittest.TestCase):
	def test_bill_format_uses_requested_company_and_preserves_print_text(self):
		company = frappe._dict(
			custom_bill_address="Building 1\nDubai",
			custom_bill_phone="+971 050 000 0000",
			custom_bill_email="billing@example.com",
			custom_bill_tax_id="001234567890",
			**{f"custom_bill_{prefix}{i}": f"{prefix.upper()} line {i}" for prefix in ("h", "f") for i in range(1, 6)},
		)
		with patch.object(pos_sync.frappe, "get_doc", return_value=company) as get_doc:
			result = pos_sync._company_bill_format("Counter Company")
		get_doc.assert_called_once_with("Company", "Counter Company")
		self.assertEqual(result, {
			"address": "Building 1\nDubai",
			"phone_number": "+971 050 000 0000",
			"email_id": "billing@example.com",
			"tax_id": "001234567890",
			**{f"{prefix}{i}": f"{prefix.upper()} line {i}" for prefix in ("h", "f") for i in range(1, 6)},
		})

	def test_bill_format_blanks_clear_previous_values_without_general_contact_fallback(self):
		company = frappe._dict(custom_bill_h1=None, custom_bill_f1="", phone_no="General phone", email="general@example.com", tax_id="General tax")
		with patch.object(pos_sync.frappe, "get_doc", return_value=company):
			result = pos_sync._company_bill_format("Counter Company")
		self.assertEqual(len(result), 14)
		self.assertTrue(all(value == "" for value in result.values()))

	def test_tax_aliases_and_display_rates_share_item_owned_template(self):
		item = frappe._dict(item_code="ITEM", sales_vat_template="VAT5", purchase_vat_template="VAT10")
		with patch.object(pos_sync, "get_item_tax_rate", side_effect=lambda name: {"VAT5": 5, "VAT10": 10}.get(name, 0)):
			pos_sync._apply_item_tax_fields([item])
		self.assertEqual(item.item_tax_template, "VAT5")
		self.assertEqual(item.tax_rate, 5)
		self.assertEqual(item.sales_vat_rate, "5%")
		self.assertEqual(item.purchase_vat_rate, "10%")
		packing = frappe._dict(item_code="ITEM")
		pos_sync._apply_packing_tax_fields(packing, {"ITEM": item})
		self.assertEqual(packing.tax_rate, 5)
		self.assertEqual(packing.sales_vat_rate, "5%")

	def test_no_sales_template_matches_zero_tax_invoice_behavior(self):
		item = frappe._dict(item_code="UNTAXED")
		with patch.object(pos_sync, "get_item_tax_rate", return_value=0):
			pos_sync._apply_item_tax_fields([item])
		self.assertIsNone(item.item_tax_template)
		self.assertEqual(item.tax_rate, 0)
		self.assertEqual(item.is_taxable, 0)

	def test_stock_fields_preserve_base_and_packing_quantities(self):
		packing = frappe._dict(item_code="ITEM", conversion_factor=6)
		item = frappe._dict(item_code="ITEM", packings=[packing])
		stock = frappe._dict(actual_qty=24, reserved_qty=2, projected_qty=30, stock_value=240, modified="2026-09-16")
		with patch.object(pos_sync, "_warehouse_stock_by_item", return_value={"ITEM": stock}):
			pos_sync._apply_current_stock_to_items([item], "Warehouse")
		self.assertEqual(item.current_stock, 24)
		self.assertEqual(item.actual_qty, 24)
		self.assertEqual(packing.current_stock, 4)
		self.assertEqual(packing.actual_qty, 24)
		self.assertEqual(item.reserved_qty, 2)
