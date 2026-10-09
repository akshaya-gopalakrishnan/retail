import unittest
from unittest.mock import Mock, patch

import frappe

from retail.api import pos_sync
from retail.domains.transactions import vat


class TestPOSVAT(unittest.TestCase):
	def test_inclusive_exclusive_zero_and_missing_template_prices(self):
		for template, percent, inclusive, price, expected in (
			('VAT5', 5, 1, 105, 100),
			('VAT10', 10, 1, 110, 100),
			('VAT5', 5, 0, 100, 100),
			('VAT0', 0, 1, 100, 100),
			(None, 0, 1, 100, 100),
		):
			with self.subTest(template=template, inclusive=inclusive):
				item = frappe._dict(custom_tax=template, custom_sales_rate_includes_vat=inclusive)
				doc = Mock()
				payload = frappe._dict(items=[dict(item_code='ITEM', qty=2, rate=price)])
				with patch.object(pos_sync, '_resolve_item', return_value='ITEM'), patch.object(
					frappe, 'get_cached_doc', return_value=item
				), patch.object(pos_sync, 'get_item_tax_rate', return_value=percent):
					pos_sync._append_invoice_items(doc, payload, frappe._dict())
				row = doc.append.call_args.args[1]
				self.assertAlmostEqual(row['rate'], expected)
				self.assertEqual(row['item_tax_template'], template)

	def test_explicit_price_basis_and_return_discount(self):
		doc = Mock()
		payload = frappe._dict(items=[dict(item_code='ITEM', qty=2, rate=110,
			discount_amount=11, rate_includes_vat=1)])
		with patch.object(pos_sync, '_resolve_item', return_value='ITEM'), patch.object(
			frappe, 'get_cached_doc', return_value=frappe._dict(custom_tax='VAT10', custom_sales_rate_includes_vat=0)
		), patch.object(pos_sync, 'get_item_tax_rate', return_value=10):
			pos_sync._append_invoice_items(doc, payload, frappe._dict(), is_return=True)
		row = doc.append.call_args.args[1]
		self.assertAlmostEqual(row['rate'], 90)
		self.assertAlmostEqual(row['discount_amount'], 10)
		self.assertEqual(row['qty'], -2)

	def test_profile_rate_cannot_tax_items_without_a_template(self):
		doc = Mock(doctype='POS Invoice')
		item = frappe._dict(item_code='NO-TAX', item_tax_template='PROFILE-DEFAULT')
		doc.get.side_effect = lambda key: {'pos_sync_source': 'Offline POS', 'items': [item]}.get(key)
		groups = {'VAT': dict(account_head='VAT', description='Sales Tax [VAT]', rate=5)}
		with patch.object(frappe, 'get_cached_value', return_value=None), patch.object(
			vat, '_get_transaction_vat_groups', return_value=groups
		), patch.object(vat, '_apply_item_vat_tax_rates'):
			vat.prepare_external_pos_taxes(doc)
		self.assertIsNone(item.item_tax_template)
		self.assertIsNone(doc.taxes_and_charges)
		self.assertEqual(doc.append.call_args.args[1]['rate'], 0)

	def test_vat_mismatch_does_not_block_or_override_invoice_taxes(self):
		doc = frappe._dict(total_taxes_and_charges=4.88)
		pos_sync._validate_vat(doc, frappe._dict(vat_amount=4.881))
		pos_sync._validate_vat(doc, frappe._dict(vat_amount=5.12))
		self.assertEqual(doc.total_taxes_and_charges, 4.88)

	def test_vat_metadata_is_still_required(self):
		doc = frappe._dict(total_taxes_and_charges=0)
		with patch.object(pos_sync, '_', side_effect=lambda value: value), patch.object(
			frappe, 'throw', side_effect=frappe.ValidationError
		):
			with self.assertRaises(frappe.ValidationError):
				pos_sync._validate_vat(doc, frappe._dict())
