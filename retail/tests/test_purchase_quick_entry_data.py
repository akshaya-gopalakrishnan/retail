"""Read bundling must preserve native permissions, zero rates and lookup arguments."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe
from retail.domains.purchase import quick_entry as api


class TestPurchaseQuickEntryData(unittest.TestCase):
    def setUp(self):
        patches = [patch.object(frappe, 'local', SimpleNamespace(flags=frappe._dict(in_test=False))),
                   patch.object(api, 'get_document', return_value=frappe._dict(
                       name='SKU', stock_uom='Nos', purchase_uom='Box-10')),
                   patch.object(api, 'get_transaction_item_vat_rate', return_value=0),
                   patch.object(api, 'get_item_selling_vat_rate', return_value=5),
                   patch.object(api, 'get_standard_selling_rate', side_effect=lambda code, uom=None: {'Nos': 2, 'Box-10': 20, 'Box-36': 72}[uom])]
        self.mocks = [p.start() for p in patches]
        for p in patches:
            self.addCleanup(p.stop)

    def test_bundle_matches_native_reads_for_pr_pi_and_each_uom(self):
        for parent in ('Purchase Receipt', 'Purchase Invoice'):
            result = api.item_data('SKU', parent, uom='Box-36', item_tax_template='ZERO')
            self.assertEqual(result['item']['name'], 'SKU')
            vat = result['lookups'][0]
            self.assertEqual(vat['message'], 0)
            self.assertEqual(vat['args']['child_doctype'], parent + ' Item')
            self.assertEqual(vat['args']['item_tax_template'], 'ZERO')
            rates = {r['args'].get('uom'): r['message'] for r in result['lookups'] if 'get_standard_selling_rate' in r['method']}
            self.assertEqual(rates, {None: 2, 'Nos': 2, 'Box-10': 20, 'Box-36': 72})
        self.assertEqual(self.mocks[-1].call_count, 6)

    def test_denied_item_read_stops_before_all_price_reads(self):
        self.mocks[1].side_effect = PermissionError('denied')
        with self.assertRaises(PermissionError):
            api.item_data('SKU', 'Purchase Receipt')
        for mock in self.mocks[2:]:
            mock.assert_not_called()

    def test_non_purchase_context_is_rejected_before_item_read(self):
        with patch.object(frappe, 'throw', side_effect=ValueError):
            with self.assertRaises(ValueError):
                api.item_data('SKU', 'Sales Invoice')
        self.mocks[1].assert_not_called()

    def test_same_stock_purchase_and_requested_uom_are_queried_once(self):
        self.mocks[1].return_value = frappe._dict(name='SKU', stock_uom='Nos', purchase_uom='Nos')
        api.item_data('SKU', 'Purchase Invoice', uom='Nos')
        self.mocks[-1].assert_called_once_with('SKU', uom='Nos')
