import unittest
from unittest.mock import patch
import frappe
from retail.retail_app import retail_dashboard as dashboard
from retail.retail_app.report import profitability


class TestBusinessHomeProfitCards(unittest.TestCase):
    def setUp(self):
        for p in (patch.object(dashboard, '_get_company_filter', side_effect=lambda c: c or 'Company'),
                  patch.object(dashboard, 'get_today', return_value=dashboard.getdate('2026-10-08')),
                  patch.object(frappe, 'format_value', side_effect=lambda v, df: str(v)),
                  patch.object(frappe, 'get_cached_value', return_value='AED')):
            p.start()
            self.addCleanup(p.stop)
        previous = frappe.form_dict
        self.addCleanup(setattr, frappe, "form_dict", previous)
        frappe.form_dict = frappe._dict()

    def test_exact_adapter_equality_at_all_sizes(self):
        for size in (10, 100, 500, 1000):
            for unavailable in (False, True):
                for status in ('Recorded / Posted', 'Stock repost Failed: R', 'Stock repost Queued: R',
                               'Stale or unmatched POS consolidation link: SI'):
                    rows = [frappe._dict(invoice_no=str(i), is_return=i % 3 == 0,
                        gross_sales=110, discount=10, sales_returns=100 if i % 3 == 0 else 0,
                        net_sales=-100 if i % 3 == 0 else 100, vat=5,
                        cost_amount=None if unavailable else 60, source_status=status)
                        for i in range(size)]
                    with self.subTest(size=size, unavailable=unavailable, status=status), patch.object(
                            profitability, 'profitability_rows', return_value=rows):
                        expected = dict(sales=dashboard.get_today_sales(), profit=dashboard.get_profit_number_card(),
                            count=dashboard.get_invoice_count_today(), returns=dashboard.get_return_amount_today())
                        with patch.object(dashboard, 'get_profit_summary', wraps=dashboard.get_profit_summary) as summary:
                            actual = dashboard.get_business_home_profit_cards([{}, {'today_only': True},
                                {'company': 'Company', 'from_date': '2026-10-08', 'to_date': '2026-10-08'}])
                            self.assertEqual(actual, [expected] * 3)
                            self.assertEqual(summary.call_count, 1)

    def test_effective_filters_separate_contexts(self):
        value = frappe._dict(net_sales=12, gross_profit=None, invoice_count=2,
                             return_amount=3, source_status='Stock repost Failed: <R>')
        contexts = [{}, {'branch': 'B'}, {'counter': 'C'}, {'company': 'Other'},
                    {'from_date': '2026-10-01'},
                    {'today_only': True, 'branch': 'B', 'counter': 'C', 'from_date': '2026-10-01'}]
        with patch.object(dashboard, 'get_profit_summary', return_value=value) as summary:
            result = dashboard.get_business_home_profit_cards(contexts)
            self.assertEqual(summary.call_count, 5)
            self.assertEqual(result[0], result[-1])
            self.assertEqual(result[0]['profit'], '<span title="Stock repost Failed: &lt;R&gt;">N/A</span>')
            self.assertEqual(summary.call_args_list[1].kwargs['branch'], 'B')
            self.assertEqual(summary.call_args_list[2].kwargs['counter'], 'C')
            self.assertEqual(summary.call_args_list[3].kwargs['company'], 'Other')

    def test_failure_and_fresh_retry(self):
        with patch.object(dashboard, 'get_profit_summary', side_effect=RuntimeError('failed')):
            with self.assertRaisesRegex(RuntimeError, 'failed'):
                dashboard.get_business_home_profit_cards([{}])
        value = frappe._dict(net_sales=1, gross_profit=1, invoice_count=1, return_amount=0, source_status='Recorded / Posted')
        with patch.object(dashboard, 'get_profit_summary', return_value=value) as summary:
            dashboard.get_business_home_profit_cards([{}])
            dashboard.get_business_home_profit_cards([{}])
            self.assertEqual(summary.call_count, 2)


    def test_invoice_scenario_fixtures_use_existing_calculations(self):
        """Exercise invoice_rows too; only its database inputs are fixtures."""
        import json
        class Invoice(frappe._dict):
            @property
            def items(self):
                return self['items']
        cases = ['normal_sales', 'returns', 'discounts', 'credit_sales', 'multiple_items',
                 'vat_exclusive', 'vat_inclusive', 'pos_linked', 'consolidated_pos',
                 'unavailable_costs', 'failed_repost', 'queued_repost', 'stale_pos_links']
        for case in cases:
            returned = case == 'returns'
            amount = -100 if returned else 100
            count = 2 if case in ('multiple_items', 'consolidated_pos') else 1
            items = [frappe._dict(name=f'I-{i}', idx=i+1, item_code=f'Item-{i}',
                base_net_amount=amount/count, base_net_rate=amount/count, stock_qty=-1 if returned else 1,
                warehouse='W', base_amount=amount/count, discount_amount=10 if case == 'discounts' else 0,
                pos_invoice='POS-1' if case in ('pos_linked', 'consolidated_pos') else None,
                pos_invoice_item=f'PI-{i}') for i in range(count)]
            taxes = [frappe._dict(account_head='VAT', base_tax_amount_after_discount_amount=amount*.05,
                included_in_print_rate=case == 'vat_inclusive',
                item_wise_tax_detail=json.dumps({item.item_code:[5, amount*.05/count] for item in items}))]
            doc = Invoice(doctype='POS Invoice' if case == 'stale_pos_links' else 'Sales Invoice',
                name='Invoice', docstatus=1, company='Company', items=items, taxes=taxes,
                is_return=returned, base_net_total=amount, base_total_taxes_and_charges=amount*.05,
                conversion_rate=1, base_paid_amount=0 if case == 'credit_sales' else amount*1.05,
                outstanding_amount=amount*1.05 if case == 'credit_sales' else 0,
                consolidated_invoice='SI' if case == 'stale_pos_links' else None)
            costs = {item.name: None if case == 'unavailable_costs' else (-60 if returned else 60)/count for item in items}
            reposts = [frappe._dict(name='R', status='Failed' if case == 'failed_repost' else 'Queued')] if case in ('failed_repost','queued_repost') else []
            dimensions = frappe._dict(pos_branch='Branch', pos_counter='Counter', pos_cashier='Cashier')
            with self.subTest(case=case), patch.object(profitability, 'posted_costs', return_value=costs), patch.object(
                    profitability, 'recorded_vat_accounts', return_value={'VAT'}), patch.object(
                    frappe.db, 'exists', return_value=True), patch.object(frappe.db, 'sql', return_value=reposts), patch.object(
                    frappe.db, 'get_value', return_value=dimensions), patch.object(frappe, 'get_all', return_value=[]):
                rows = profitability.invoice_rows(doc)
            self.assertEqual(sum(row.net_sales for row in rows), amount)
            if case in ('pos_linked', 'consolidated_pos'):
                self.assertTrue(all(row.branch == 'Branch' and row.counter == 'Counter' for row in rows))
            for size in (10, 100, 500, 1000):
                expanded = []
                for i in range(size):
                    for row in rows:
                        expanded.append(frappe._dict(row, invoice_no=str(i)))
                with self.subTest(case=case, size=size), patch.object(profitability, 'profitability_rows', return_value=expanded):
                    before = dict(sales=dashboard.get_today_sales(), profit=dashboard.get_profit_number_card(),
                        count=dashboard.get_invoice_count_today(), returns=dashboard.get_return_amount_today())
                    self.assertEqual(dashboard.get_business_home_profit_cards([{}])[0], before)

    def test_filtered_values_match_legacy_at_all_sizes(self):
        for size in (10, 100, 500, 1000):
            rows = [frappe._dict(invoice_no=str(i), is_return=False, net_sales=100, gross_sales=110,
                discount=10, sales_returns=0, vat=5, cost_amount=60, source_status='Recorded / Posted',
                company='Other' if i % 2 else 'Company', branch='B' if i % 3 else 'A',
                counter='C' if i % 4 else 'D') for i in range(size)]
            def filtered(filters, *args, **kwargs):
                return [row for row in rows if all(not filters.get(k) or row[k] == filters[k]
                    for k in ('company', 'branch', 'counter'))]
            for context in ({'branch': 'B'}, {'counter': 'C'}, {'company': 'Other'},
                            {'company': 'Company', 'branch': 'B', 'counter': 'C'}):
                with self.subTest(size=size, context=context), patch.object(profitability, 'profitability_rows', side_effect=filtered):
                    frappe.form_dict = frappe._dict(context)
                    before = dict(sales=dashboard.get_today_sales(), profit=dashboard.get_profit_number_card(),
                        count=dashboard.get_invoice_count_today(), returns=dashboard.get_return_amount_today())
                    full, today_only = dashboard.get_business_home_profit_cards([context, dict(context, today_only=True)])
                    self.assertEqual(dict(sales=full['sales'], profit=full['profit'],
                        count=today_only['count'], returns=today_only['returns']), before)
