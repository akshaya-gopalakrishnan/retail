"""Promotion savings change report breakdowns, never completed financial facts."""
import copy
import json
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retail.promotions.history import discounts_by_item_row
from retail.retail_app.report import profitability as reports


class Invoice(frappe._dict):
    @property
    def items(self):
        return self['items']

    def __deepcopy__(self, memo):
        return type(self)({key:copy.deepcopy(self[key], memo) for key in self.keys()})


def sale():
    payload = dict(items=[
        dict(item_code='I-20', barcode='9974337', qty=1, uom='Kg', rate=9,
             amount=9, net_amount=8.57, vat_rate=5, rate_includes_vat=1,
             discount_amount=0, applied_promotions=[dict(promotion_type='52',
                 promotion='10% off on brands', promotion_discount_amount=1)]),
        dict(item_code='I-2', barcode='BC0020289', qty=1, uom='Nos', rate=26.25,
             amount=26.25, net_amount=25, vat_rate=5, rate_includes_vat=1,
             discount_amount=0, applied_promotions=[]),
    ])
    items = [frappe._dict(name='LINE-'+str(idx), idx=idx, item_code=row['item_code'],
        barcode=row['barcode'], qty=row['qty'], stock_qty=row['qty'],
        rate=row['net_amount'], base_net_amount=row['net_amount'],
        base_net_rate=row['net_amount'], discount_amount=0,
        distributed_discount_amount=0, warehouse='Stores', uom=row['uom'])
        for idx, row in enumerate(payload['items'], 1)]
    return Invoice(doctype='POS Invoice', name='POS', docstatus=1, company='Company',
        conversion_rate=1, is_return=0, posting_date='2026-11-07',
        pos_sync_source='Offline POS', custom_pos_completed_payload=json.dumps(payload),
        base_net_total=33.57, base_total_taxes_and_charges=1.68,
        base_paid_amount=35.25, outstanding_amount=0, items=items,
        taxes=[frappe._dict(account_head='VAT', base_tax_amount_after_discount_amount=1.68,
            item_wise_tax_detail=json.dumps({'I-20':[5,.43], 'I-2':[5,1.25]}))])


class TestReportPromotionDiscounts(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(frappe, 'get_system_settings',
            return_value="Banker's Rounding (legacy)"))

    def rows(self, doc, costs=None):
        with patch.object(reports, 'posted_costs', return_value=costs or {'LINE-1':5.10, 'LINE-2':18.18}), patch.object(
                reports, 'recorded_vat_accounts', return_value={'VAT'}), patch.object(
                reports, 'source_status', return_value='Recorded / Posted'):
            return reports.invoice_rows(doc)

    def test_existing_payload_corrects_header_items_and_totals_without_mutation(self):
        doc = sale()
        before = copy.deepcopy(doc)
        header = reports.invoice_profitability(doc, {'LINE-1':5.10, 'LINE-2':18.18}, vat_accounts={'VAT'})
        rows = self.rows(doc)
        self.assertAlmostEqual(header.gross_sales, 34.52)
        self.assertAlmostEqual(header.discount, .95)
        self.assertEqual((rows[0].gross_sales, rows[0].discount, rows[0].net_sales, rows[0].vat),
                         (9.52, .95, 8.57, .43))
        self.assertEqual((rows[1].gross_sales, rows[1].discount), (25, 0))
        total = reports.profitability_total(rows, 'invoice_no')
        for result in (header, total):
            self.assertAlmostEqual(result.net_sales, 33.57)
            self.assertAlmostEqual(result.vat, 1.68)
            self.assertAlmostEqual(result.cost_amount, 23.28)
            self.assertAlmostEqual(result.gross_profit, 10.29)
            self.assertAlmostEqual(result.gross_sales-result.discount-result.sales_returns, result.net_sales)
        self.assertEqual(doc, before)

    def test_line_total_not_multiplied_by_quantity_and_offers_count_once(self):
        payload = json.loads(sale().custom_pos_completed_payload)
        item = payload['items'][0]
        item['qty'] = 3
        first = item['applied_promotions'][0]
        first['promotion_discount_amount'] = 3.15
        item['applied_promotions'] += [dict(first), dict(promotion_type='52',
            promotion='Second offer', promotion_discount_amount=1.05)]
        self.assertEqual(discounts_by_item_row(payload), {1:4})

    def test_exclusive_vat_and_legacy_header_evidence(self):
        payload = json.loads(sale().custom_pos_completed_payload)
        payload['items'][0]['rate_includes_vat'] = 0
        self.assertEqual(discounts_by_item_row(payload), {1:1})
        payload['applied_promotions'] = [dict(promotion_type='Promo Price', promotion='Legacy',
            item_code='I-20', discount_amount=2)]
        self.assertEqual(discounts_by_item_row(payload), {1:2})
        payload['applied_promotions'] = []
        self.assertEqual(discounts_by_item_row(payload), {})

    def test_manual_discount_is_preserved_and_company_currency_converts_once(self):
        doc = sale()
        doc.conversion_rate = 2
        doc.items[0].discount_amount = .5
        for item in doc.items:
            item.base_net_amount *= 2
        doc.base_net_total *= 2
        doc.base_total_taxes_and_charges *= 2
        doc.taxes[0].base_tax_amount_after_discount_amount *= 2
        result = reports.invoice_profitability(doc, {'LINE-1':10.20, 'LINE-2':36.36}, vat_accounts={'VAT'})
        self.assertAlmostEqual(result.discount, 2.9)  # (.50 manual + .95 promotion) * 2
        self.assertAlmostEqual(result.gross_sales, doc.base_net_total+2.9)

    def test_separate_financial_and_promotion_discounts_on_same_line_are_added(self):
        doc = sale()
        payload = json.loads(doc.custom_pos_completed_payload)
        payload['items'][0].update(rate=10, amount=10, discount_amount=1)
        doc.custom_pos_completed_payload = json.dumps(payload)
        doc.items[0].discount_amount = 1
        result = reports.invoice_profitability(doc, {'LINE-1':5.10, 'LINE-2':18.18}, vat_accounts={'VAT'})
        row = self.rows(doc)[0]
        self.assertAlmostEqual(row.gross_sales, 10.52)
        self.assertAlmostEqual(row.discount, 1.95)
        self.assertEqual(row.net_sales, 8.57)
        self.assertAlmostEqual(result.discount, 1.95)
        self.assertAlmostEqual(result.gross_sales, 35.52)

    def test_return_keeps_existing_sales_return_and_profit_signs(self):
        doc = sale()
        doc.is_return = 1
        for item in doc.items:
            item.qty *= -1
            item.stock_qty *= -1
            item.base_net_amount *= -1
        doc.base_net_total *= -1
        doc.base_total_taxes_and_charges *= -1
        doc.taxes[0].base_tax_amount_after_discount_amount *= -1
        result = reports.invoice_profitability(doc, {'LINE-1':-5.10, 'LINE-2':-18.18}, vat_accounts={'VAT'})
        self.assertEqual((result.gross_sales, result.discount, result.sales_returns), (0,0,33.57))
        rows = self.rows(doc, {'LINE-1':-5.10, 'LINE-2':-18.18})
        self.assertTrue(all(r.gross_sales == r.discount == 0 for r in rows))
        self.assertAlmostEqual(result.gross_profit, -10.29)

    def test_missing_invalid_or_ambiguous_evidence_never_infers_current_prices(self):
        payload = json.loads(sale().custom_pos_completed_payload)
        for value in (None, 'bad', float('nan'), float('inf')):
            payload['items'][0]['applied_promotions'][0]['promotion_discount_amount'] = value
            self.assertFalse(discounts_by_item_row(payload))
        payload['items'].append(copy.deepcopy(payload['items'][0]))
        payload['applied_promotions'] = [dict(promotion_type='Promo Price', promotion='Ambiguous',
            item_code='I-20', discount_amount=1)]
        self.assertFalse(discounts_by_item_row(payload))
        for value in ('broken JSON', '{}', '[]'):
            doc = sale()
            doc.custom_pos_completed_payload = value
            self.assertFalse(reports.invoice_promotion_discounts(doc))

    def test_repeated_item_codes_match_saved_position_without_crossing_lines(self):
        doc = sale()
        payload = json.loads(doc.custom_pos_completed_payload)
        payload['items'][1]['item_code'] = doc.items[1].item_code = 'I-20'
        payload['items'][1]['applied_promotions'] = [dict(promotion_type='52',
            promotion='Other packing', promotion_discount_amount=2.10)]
        doc.custom_pos_completed_payload = json.dumps(payload)
        self.assertEqual(reports.invoice_promotion_discounts(doc), {'LINE-1':.95, 'LINE-2':2})
        doc.items[0].item_code = 'DIFFERENT'
        self.assertEqual(reports.invoice_promotion_discounts(doc), {'LINE-2':2})

    def test_consolidated_sales_invoice_uses_exact_original_pos_item_links(self):
        original = sale()
        doc = copy.deepcopy(original)
        doc.doctype = 'Sales Invoice'
        doc.name = 'CONSOLIDATED'
        for idx, item in enumerate(doc.items, 1):
            item.pos_invoice, item.pos_invoice_item = original.name, item.name
            item.name = 'CONSOLIDATED-'+str(idx)
        with patch.object(frappe, 'get_doc', return_value=original) as lookup, patch.object(
                frappe, 'db', SimpleNamespace(get_value=lambda *args, **kwargs: None)):
            rows = self.rows(doc, {'CONSOLIDATED-1':5.10, 'CONSOLIDATED-2':18.18})
        lookup.assert_called_once_with('POS Invoice', 'POS')
        self.assertEqual((rows[0].gross_sales, rows[0].discount), (9.52,.95))
        self.assertEqual((rows[1].gross_sales, rows[1].discount), (25,0))

    def test_native_sales_and_pos_without_evidence_keep_their_discount(self):
        for doctype in ('Sales Invoice', 'POS Invoice'):
            doc = sale()
            doc.doctype = doctype
            doc.custom_pos_completed_payload = '{}'
            doc.items[0].discount_amount = 2
            result = reports.invoice_profitability(doc, {'LINE-1':5.10, 'LINE-2':18.18}, vat_accounts={'VAT'})
            self.assertEqual(result.discount, 2)
            self.assertAlmostEqual(result.gross_sales, 35.57)

    def test_grouping_and_filtering_keep_only_selected_item_savings(self):
        rows = self.rows(sale())
        for fields in (['invoice_no'], ['item_code'], ['warehouse'], ['posting_date']):
            grouped = reports.aggregate_profitability(rows, fields)
            self.assertAlmostEqual(sum(r.discount for r in grouped), .95)
            self.assertAlmostEqual(sum(r.gross_sales for r in grouped), 34.52)
            self.assertAlmostEqual(sum(r.net_sales for r in grouped), 33.57)
        filtered = reports.profitability_total([rows[0]], 'item_code')
        self.assertEqual((filtered.gross_sales, filtered.discount, filtered.net_sales), (9.52,.95,8.57))
