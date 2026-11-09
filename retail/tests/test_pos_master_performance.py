"""Compatibility and query-count checks for master download optimizations."""
import unittest
from itertools import product
from unittest.mock import Mock, patch

import frappe
from retail.api import pos_sync
from retail.pos_item_identity import with_item_identity
from retail import pos_settlements


class TestPOSMasterPerformance(unittest.TestCase):
    def test_master_promo_loader_skips_only_discarded_additional_payload(self):
        counter = frappe._dict(branch='B', name='COUNTER', counter_code='C', warehouse='W')
        with patch.object(pos_sync, '_pos_promotion_payload', return_value=({}, counter, None)), patch.object(
            pos_sync, '_get_promotion_docs', return_value=[]
        ), patch.object(pos_sync, '_additional_pos_promotions', return_value={'pricing_rules': ['RULE']}) as extra:
            lean = pos_sync._get_pos_promo_prices('B', 'C', include_additional=False)
            extra.assert_not_called()
            full = pos_sync.get_pos_promo_prices('B', 'C')
            extra.assert_called_once_with(counter, None)
        self.assertEqual(lean['promotions'], full['promotions'])
        self.assertNotIn('pricing_rules', lean)
        self.assertEqual(full['pricing_rules'], ['RULE'])

    def test_bulk_credit_limits_match_native_fallbacks(self):
        # Native behavior treats numeric zero as fallback and respects group
        # bypass, while the separately exposed bypass flag remains unchanged.
        for own, group, bypass, company in product((None, 0, 100, -10), (None, 0, 200), (0, 1), (0, 300)):
            with self.subTest(own=own, group=group, bypass=bypass, company=company):
                customer = frappe._dict(name='C', customer_group='G', custom_sales_person=None)
                own_row = frappe._dict(parent='C', credit_limit=own, bypass_credit_limit_check=1) if own is not None else None
                group_row = frappe._dict(parent='G', credit_limit=group, bypass_credit_limit_check=bypass) if group is not None else None
                def query(dt, **kw):
                    if dt == 'Customer':
                        return [customer]
                    if dt == 'Customer Credit Limit':
                        row = own_row if kw['filters']['parenttype'] == 'Customer' else group_row
                        return [row] if row else []
                    return []
                def cached(dt, name, field):
                    return company if dt == 'Company' else 'G'
                with patch.object(frappe.db, 'get_value', return_value=own), patch.object(
                    frappe.db, 'get_values', return_value=[group_row] if group_row else []
                ), patch.object(frappe, 'get_cached_value', side_effect=cached):
                    expected = pos_sync.get_credit_limit('C', 'CO')
                with patch.object(frappe, 'get_all', side_effect=query), patch.object(
                    frappe, 'get_cached_value', side_effect=cached
                ), patch.object(pos_sync, 'get_credit_limit', side_effect=AssertionError('per-customer query')), patch.object(
                    pos_sync, 'add_credit_note_snapshots'
                ), patch('retail.customer_promotions.add_customer_promotions'):
                    result = pos_sync._customer_master_rows('CO')[0]
                self.assertEqual(result.credit_limit, expected)
                self.assertEqual(result.is_credit_customer, int(expected > 0))
                detail = own_row or group_row
                self.assertEqual(result.bypass_credit_limit_check, int(detail.bypass_credit_limit_check) if detail else 0)

    def test_shared_stock_snapshot_keeps_fields_without_requery(self):
        stock = {'I': frappe._dict(actual_qty=24, reserved_qty=2, projected_qty=30, stock_value=240, modified='NOW')}
        nested = frappe._dict(item_code='I', conversion_factor=6)
        item = frappe._dict(item_code='I', packings=[nested])
        flat = frappe._dict(item_code='I', conversion_factor=6)
        with patch.object(pos_sync, '_warehouse_stock_by_item') as query:
            pos_sync._apply_current_stock_to_items([item], 'W', stock)
            pos_sync._apply_current_stock_to_packings([flat], 'W', stock)
            query.assert_not_called()
        self.assertEqual((item.actual_qty, item.current_stock, item.reserved_qty, item.projected_qty, item.stock_value), (24, 24, 2, 30, 240))
        self.assertEqual((nested.actual_qty, nested.current_stock, flat.actual_qty, flat.current_stock), (24, 4, 24, 4))
        with patch.object(pos_sync, '_warehouse_stock_by_item') as query:
            pos_sync._apply_current_stock_to_items([item], 'W', {})
            query.assert_not_called()
        self.assertEqual(item.current_stock, 0)

    def test_purchase_and_sales_tax_templates_are_read_once(self):
        items = [frappe._dict(item_code=str(i), sales_vat_template='VAT', purchase_vat_template='VAT') for i in range(100)]
        with patch.object(pos_sync, 'get_item_tax_rate', return_value=5) as query:
            pos_sync._apply_item_tax_fields(items)
        query.assert_called_once_with('VAT')
        self.assertTrue(all(item.sales_vat_rate == item.purchase_vat_rate == '5%' for item in items))

    def test_known_identity_preserves_packing_and_queries_unknown_items(self):
        known = frappe._dict(item_code='I', item_name='Known', barcode='BASE', has_serial_no=1, serial_numbers=['S'])
        packing = dict(item_code='I', barcode='PACK', serial_no='CHOSEN')
        unknown = dict(item_code='J')
        with patch.object(frappe, 'get_all', return_value=[frappe._dict(item_code='J', item_name='Other', barcode='OTHER', has_serial_no=0)]) as query:
            with_item_identity({'rows': [packing, unknown]}, 'W', known_items=[known])
        self.assertEqual(query.call_count, 1)
        self.assertEqual(query.call_args.kwargs['filters'], {'name': ['in', ['J']]})
        self.assertEqual((packing['barcode'], packing['serial_no'], packing['serial_numbers']), ('PACK', 'CHOSEN', ['S']))
        self.assertEqual(unknown['barcode'], 'OTHER')

    def test_bulk_settlement_summaries_equal_existing_individual_summary(self):
        allocations = [frappe._dict(customer=customer, settlement_type=kind, requested_amount=10,
            applied_amount=4, unresolved_amount=6, status='Pending')
            for customer in ('A', 'B') for kind in (*pos_settlements.SUMMARY_FIELDS, 'Unknown')]
        with patch.object(frappe, 'get_all', return_value=allocations[:5]):
            expected = pos_settlements.summary({'company': 'CO', 'customer': 'A'})
        def query(dt, **kw):
            if dt == 'Customer':
                return [frappe._dict(name=name) for name in ('A', 'B')]
            return allocations
        rows = [dict(name=name, unused_credit_note_amount=20, unused_credit_notes=[]) for name in ('A', 'B')]
        with patch.object(frappe, 'get_all', side_effect=query) as queries, patch(
            'retail.customer_balances._CustomerReceivables', return_value=Mock(total_row_map={})
        ), patch.object(
            pos_settlements, 'summary', side_effect=AssertionError('per-customer summary')
        ):
            pos_settlements.add_customer_summaries(rows, 'CO', 'name')
        self.assertEqual(queries.call_count, 2)
        for row in rows:
            self.assertEqual({field: row[field] for field in expected}, expected)
            self.assertEqual(row['available_credit'], 20)
