import unittest
from retail.pos_invoice_layout import HEADER, SUMMARY, BASE_TOTALS, SYNC, field_order


class TestPOSInvoiceLayout(unittest.TestCase):
    def test_order_is_complete_and_repeatable(self):
        original = list(dict.fromkeys(HEADER + ['accounting_dimensions_section', 'project',
            'dimension_col_break', 'cost_center', 'items_section', 'items', 'site_custom_field'] +
            SUMMARY + ['more_info', 'debit_to', 'sales_team_section_break'] + BASE_TOTALS + SYNC))
        arranged = field_order(original)
        self.assertCountEqual(arranged, original)
        self.assertEqual(len(arranged), len(set(arranged)))
        self.assertEqual(field_order(arranged), arranged)
        self.assertEqual(arranged[-len(SYNC):], SYNC)
        self.assertLess(arranged.index('company'), arranged.index('pos_sync_section'))
        self.assertLess(arranged.index('items'), arranged.index('totals'))
        self.assertLess(arranged.index('site_custom_field'), arranged.index('totals'))

    def test_optional_fields_can_be_absent(self):
        original = ['customer_section', 'company', 'customer', 'items_section', 'items',
                    'totals', 'grand_total', 'pos_sync_section', 'external_pos_reference']
        result = field_order(original)
        self.assertCountEqual(result, original)
        self.assertEqual(field_order(result), result)

    def test_base_totals_remain_available_without_commission_section(self):
        original = ['customer_section', 'company', 'items_section', 'items',
                    'totals', 'base_grand_total', 'grand_total', 'pos_sync_section']
        self.assertCountEqual(field_order(original), original)
