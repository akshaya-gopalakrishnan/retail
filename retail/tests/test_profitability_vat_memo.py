"""Exact row/status equality for calculation-local VAT memoization."""
import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import frappe
from retail.retail_app.report import profitability as p


class FixtureInvoice(frappe._dict):
    @property
    def items(self):
        return self['items']


def invoice(company='A'):
    return FixtureInvoice(doctype='Sales Invoice', name='SALE', company=company,
        docstatus=1, posting_date='2026-10-08', conversion_rate=1, is_return=0,
        update_stock=1, branch='BR', custom_counter='COUNTER', base_net_total=100,
        base_total_taxes_and_charges=5, base_paid_amount=105, outstanding_amount=0,
        items=[frappe._dict(name='ITEM', idx=1, item_code='SKU', warehouse='WH',
            qty=1, stock_qty=1, rate=100, base_net_rate=100, base_net_amount=100)],
        taxes=[frappe._dict(account_head='VAT-'+company,
            base_tax_amount_after_discount_amount=5,
            item_wise_tax_detail=json.dumps({'SKU': [5, 5]}))])


class TestVatMemo(unittest.TestCase):
    def calculate(self, docs, filters=None, memo=True, costs=None, pending=(), gl=70, linked=('ITEM',)):
        original = p.invoice_rows
        def get_all(doctype, **kwargs):
            if doctype == 'Account':
                c = kwargs['filters']['company']
                return [] if c == 'EMPTY' else ['VAT-'+c]
            return list(linked)
        def sql(query, *args, **kwargs):
            return list(pending) if 'tabRepost Item Valuation' in query else [(gl,)]
        with patch.object(frappe, 'get_list', side_effect=lambda dt, **kw: [n for n, d in enumerate(docs) if not kw['filters'].get('company') or d.company == kw['filters']['company']]), patch.object(
                frappe, 'get_doc', side_effect=lambda dt, n: docs[n]), patch.object(
                frappe, 'get_meta', return_value=SimpleNamespace(has_field=lambda f: True)), patch.object(
                frappe, 'get_all', side_effect=get_all), patch.object(frappe, 'db',
                SimpleNamespace(sql=sql, exists=lambda *a, **k: True)), patch.object(
                p, 'posted_costs', side_effect=lambda d: costs if costs is not None else {i.name: 70/len(d.items) for i in d.items}), patch.object(
                p, 'recorded_vat_accounts', wraps=p.recorded_vat_accounts) as vat, patch.object(
                p, 'invoice_rows', side_effect=lambda d, **kw: original(d, **kw) if memo else original(d)):
            rows = p.profitability_rows(dict(from_date='2026-10-08', to_date='2026-10-08', **(filters or {})), doctype=docs[0].doctype)
            return rows, [c.args[0] for c in vat.call_args_list]

    def test_exact_equality_scenarios(self):
        names = ('normal sale', 'return', 'discount', 'multiple items', 'VAT exclusive',
            'VAT inclusive', 'credit sale', 'POS', 'consolidation', 'stale link',
            'missing cost', 'failed repost', 'queued/in-progress repost', 'valuation repost',
            'stock/GL discrepancy', 'branch filter', 'counter filter', 'company filter')
        for name in names:
            d, options, filters = invoice(), {}, {}
            if name == 'VAT inclusive': d.taxes[0].included_in_print_rate = 1
            if name == 'credit sale': d.base_paid_amount, d.outstanding_amount = 0, 105
            if name == 'discount': d.items[0].discount_amount = 10
            if name == 'return':
                d.is_return, d.base_net_total = 1, -100
                d.items[0].qty = d.items[0].stock_qty = -1
                d.items[0].base_net_amount = -100
                d.taxes[0].base_tax_amount_after_discount_amount = d.base_total_taxes_and_charges = -5
                d.taxes[0].item_wise_tax_detail = json.dumps({'SKU': [5, -5]})
                options.update(costs={'ITEM': -70}, gl=-70)
            if name == 'multiple items':
                d.items.append(copy.deepcopy(d.items[0]))
                d.items[1].name, d.items[1].idx = 'ITEM2', 2
                for i in d.items: i.base_net_amount = 50
            if name in ('POS', 'consolidation', 'stale link'):
                d.doctype, d.pos_branch, d.pos_counter = 'POS Invoice', 'BR', 'COUNTER'
                if name != 'POS': d.consolidated_invoice = 'CONSOLIDATED'
                if name == 'stale link': options['linked'] = ()
            if name == 'missing cost': options['costs'] = {}
            if name in ('failed repost', 'queued/in-progress repost'):
                statuses = ['Failed'] if name == 'failed repost' else ['Queued', 'In Progress']
                options['pending'] = [frappe._dict(name=s, status=s) for s in statuses]
            if name == 'valuation repost': options.update(costs={'ITEM': 80}, gl=80)
            if name == 'stock/GL discrepancy': options['gl'] = 90
            if name.endswith(' filter'):
                key = name.split()[0]
                filters[key] = {'branch': 'BR', 'counter': 'COUNTER', 'company': 'A'}[key]
            with self.subTest(scenario=name):
                before, calls_before = self.calculate([d, d], filters, memo=False, **options)
                after, calls_after = self.calculate([d, d], filters, **options)
                self.assertTrue(before)
                self.assertEqual(before, after)
                self.assertEqual((calls_before, calls_after), (['A', 'A'], ['A']))
                self.assertEqual(self.calculate([d], filters, **options)[1], ['A'])
                if name.endswith(' filter'):
                    self.assertEqual(self.calculate([d], {key: 'OTHER'}, **options)[0], [])

    def test_multiple_companies_and_empty_results(self):
        docs = [invoice(c) for c in ('A', 'B', 'EMPTY', 'A', 'B', 'EMPTY')]
        before, calls_before = self.calculate(docs, memo=False)
        after, calls_after = self.calculate(docs)
        self.assertEqual(before, after)
        self.assertEqual(calls_after, ['A', 'B', 'EMPTY'])
        self.assertEqual(len(calls_before), 6)
        self.assertEqual([r.vat for r in after], [5, 5, 0, 5, 5, 0])

    def test_unexpected_memo_retains_lookup(self):
        with patch.object(p, 'posted_costs', return_value={'ITEM': 70}), patch.object(
                p, 'source_status', return_value='Recorded / Posted'), patch.object(
                p, 'recorded_vat_accounts', return_value={'VAT-A'}) as lookup:
            before = p.invoice_rows(invoice())
            self.assertEqual(before, p.invoice_rows(invoice(), vat_accounts_by_company=object()))
            self.assertEqual(lookup.call_count, 2)

    def test_failed_lookup_is_not_cached(self):
        memo = {}
        with patch.object(p, 'posted_costs', return_value={'ITEM': 70}), patch.object(
                p, 'source_status', return_value='Recorded / Posted'), patch.object(
                p, 'recorded_vat_accounts', side_effect=[RuntimeError('lookup failed'), {'VAT-A'}]) as lookup:
            with self.assertRaisesRegex(RuntimeError, 'lookup failed'):
                p.invoice_rows(invoice(), vat_accounts_by_company=memo)
            self.assertEqual(memo, {})
            self.assertEqual(p.invoice_rows(invoice(), vat_accounts_by_company=memo)[0].vat, 5)
            self.assertEqual(lookup.call_count, 2)
