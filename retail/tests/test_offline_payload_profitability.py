"""Raw terminal discounts remain separate from accounting calculations."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import frappe
from retail.retail_app.report import profitability as p
from retail.tests.test_profitability_vat_memo import invoice

class TestOfflinePayloadProfitability(unittest.TestCase):
    def offline(self):
        doc = invoice()
        doc.doctype = 'POS Invoice'
        doc.pos_sync_source = 'Offline POS'
        doc.items[0].qty = 10
        doc.custom_pos_completed_payload = {'items': [dict(item_code='SKU', qty=10,
            amount=50, net_amount=47.62, vat_amount=2.38, vat_rate=5, rate_includes_vat=1,
            discount_amount=50, applied_promotions=[dict(promotion_discount_amount=50)])]}
        return doc

    def test_raw_values_ignore_quantity_vat_and_currency(self):
        doc = self.offline()
        doc.conversion_rate = 2
        for qty in (1, 10, 100):
            doc.items[0].qty = qty
            v = p.offline_payload_values(doc)['ITEM']
            self.assertEqual(v.cashier_discount_amount, 50)
            self.assertEqual(v.promotion_discount_amounts, [50])
        line = doc.custom_pos_completed_payload['items'][0]
        line['discount_amount'] = 0
        line['applied_promotions'] = [dict(promotion_discount_amount=1),dict(promotion_discount_amount=2.5)]
        v = p.offline_payload_values(doc)['ITEM']
        self.assertEqual(v.cashier_discount_amount, 0)
        self.assertEqual(v.promotion_discount_amounts, [1, 2.5])

    def test_rows_and_exact_consolidation(self):
        original = self.offline()
        doc = invoice()
        doc.items[0].pos_invoice = 'POS-125'
        doc.items[0].pos_invoice_item = 'ITEM'
        with patch.object(frappe,'get_doc',return_value=original), patch.object(
                frappe,'db',SimpleNamespace(get_value=lambda *a,**k:None)), patch.object(
                p,'posted_costs',return_value={'ITEM':30}), patch.object(
                p,'recorded_vat_accounts',return_value={'VAT-A'}), patch.object(
                p,'source_status',return_value='Recorded / Posted'), patch.object(
                frappe,'get_system_settings',return_value="Banker's Rounding"):
            row = p.invoice_rows(doc)[0]
        self.assertEqual(row.cashier_discount_amount, 50)
        self.assertEqual(row.promotion_discount_amounts, '50')
        self.assertEqual(row.discount, 50)
        self.assertEqual(row.discount_incl_vat, 50)
        self.assertEqual(row.net_sales, 47.62)
        self.assertAlmostEqual(row.gross_sales, 97.62)
        self.assertAlmostEqual(row.gross_sales - row.discount - row.sales_returns, row.net_sales)
        self.assertAlmostEqual(row.gross_sales_incl_vat, 100)
        doc.items[0].pos_invoice_item = 'OTHER'
        with patch.object(frappe,'get_doc',return_value=original):
            self.assertEqual(p.offline_payload_values(doc), {})

    def test_discount_report_no_quantity_calculation(self):
        from retail.retail_app.report.pos_report_utils import completed_discount_rows
        doc = self.offline()
        row = completed_discount_rows([frappe._dict(completed_payload=doc.custom_pos_completed_payload,
            item_index=1, invoice_no='POS', qty=10)])[0]
        self.assertEqual(row.discount_amount, 50)
        self.assertEqual(row.line_discount_amount, 50)
        self.assertEqual(row.promotion_discount_amount, '50')

    def test_header_totals_are_not_allocated_or_rewritten_into_lines(self):
        doc = self.offline()
        doc.custom_pos_completed_payload.update(grand_total=60, discount_amount=1)
        value = p.offline_payload_values(doc)['ITEM']
        self.assertEqual(value.bill_total, 60)
        self.assertEqual(value.bill_discount, 1)
        self.assertEqual(value.amount, 50)
        self.assertEqual(value.net_sales, 47.62)
        second = frappe._dict(doc.items[0].copy())
        second.update(name='ITEM2', idx=2)
        doc['items'].append(second)
        doc.custom_pos_completed_payload['items'].append(dict(doc.custom_pos_completed_payload['items'][0]))
        values = p.offline_payload_values(doc)
        self.assertEqual(values['ITEM2'].bill_total, 0)
        self.assertEqual(values['ITEM2'].bill_discount, 0)
        self.assertEqual(values['ITEM2'].discount, 50)

    def test_promotion_evidence_is_not_added_to_cashier_discount(self):
        doc = self.offline()
        line = doc.custom_pos_completed_payload['items'][0]
        line['discount_amount'] = 0
        value = p.offline_payload_values(doc)['ITEM']
        self.assertEqual(value.discount, 0)
        self.assertEqual(value.discount_incl_vat, 0)
        self.assertEqual(value.promotion_discount_amounts, [50])
        line['discount_amount'] = 5
        value = p.offline_payload_values(doc)['ITEM']
        self.assertEqual(value.discount, 5)
        self.assertAlmostEqual(value.discount_incl_vat, 5)

    def test_bill_summary_does_not_sum_manual_or_promotion_discounts(self):
        rows = [frappe._dict(invoice_no='POS', item_code=code, is_return=0,
            source_status='Recorded / Posted', net_sales=net, vat=vat,
            gross_sales=amount, discount=0, discount_incl_vat=0,
            gross_sales_incl_vat=amount, net_sales_incl_vat=amount,
            cost_amount=1, sales_returns=0, bill_discount=bill_discount,
            bill_total=bill_total, promotion_discount_amounts=promotion)
            for code,net,vat,amount,bill_discount,bill_total,promotion in [
                ('SALT',8.57,.43,9,1,11.62,'1'),
                ('MASALA',2.5,.12,2.62,0,0,'')]]
        with patch.object(frappe, '_', side_effect=lambda text: text):
            summary = p.aggregate_profitability(rows, ['posting_date'])[0]
            items = p.aggregate_profitability(rows, ['item_code'])
        self.assertEqual(summary.discount, 1)
        self.assertAlmostEqual(summary.gross_sales, 12.07)
        self.assertAlmostEqual(summary.gross_sales - summary.discount - summary.sales_returns, summary.net_sales)
        self.assertEqual(summary.net_sales_incl_vat, 11.62)
        self.assertTrue(all(r.discount == 0 for r in items))
