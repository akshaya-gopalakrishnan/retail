import unittest
from retail.domains.sales.bill_number import format_number, print_layout


class TestBillNumber(unittest.TestCase):
    def test_branch_free_format_and_unbounded_width(self):
        self.assertEqual(format_number('N', '2026-12-31', True, 80), 'N2610080')
        self.assertEqual(format_number('ABC', '2027-01-01', False, 81), 'ABC2700081')
        self.assertEqual(format_number('N', '2027-01-01', True, 100000), 'N27100100000')
        self.assertEqual(format_number('N', '2026-01-01', False, 1), 'N2600001')

    def test_print_upgrade_is_narrow_and_repeatable(self):
        source = '<td class="detail-value">{{ doc.name }}</td><div>{{ doc.customer_name }}</div>'
        patched = print_layout(source)
        self.assertIn('doc.get("custom_bill_number") or doc.name', patched)
        self.assertIn('{{ doc.customer_name }}', patched)
        self.assertEqual(print_layout(patched), patched)
