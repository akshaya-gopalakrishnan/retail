"""Regression checks for transaction identity without changing stock/accounting."""
import json
import unittest
from unittest.mock import patch
import frappe
from retail.transaction_identity import FIELDS, SNAPSHOT, IdentityLookup, append_columns, columns, resolve, snapshot_document
from retail.retail_app.report.profitability import aggregate_profitability


class TestTransactionIdentity(unittest.TestCase):
    def setUp(self):
        translate = patch('retail.transaction_identity._', side_effect=lambda value: value)
        translate.start()
        self.addCleanup(translate.stop)
        self.item = frappe._dict(item_name='Masala', stock_uom='Nos', custom_retail_packing_detail=[
            frappe._dict(barcode='SIX', uom='Pack', conversion_factor=6, packing_name='Masala six'),
            frappe._dict(barcode='FOUR', uom='Pack', conversion_factor=4, packing_name='Masala four')])
        self.line = frappe._dict(name='ROW6', parent='SI', idx=2, item_code='ITEM', item_name='Masala',
            barcode='SIX', uom='Pack', qty=2, stock_qty=12, conversion_factor=6, warehouse='WH')

    def lookup(self, lines=None):
        lookup = IdentityLookup(set())
        lookup.lines = {('Sales Invoice', 'SI'): lines or [self.line]}
        lookup.items = {'ITEM': self.item}
        return lookup

    def test_exact_barcode_and_factor(self):
        values = resolve(self.line, self.item)
        self.assertEqual([values[k] for k in FIELDS[:5]], ['Pack', 'SIX', 'Masala six', 2, 6])
        self.assertEqual(self.line.qty, 2)

    def test_unknown_barcode_never_selects_other_packing(self):
        values = resolve({**self.line, 'barcode': 'UNKNOWN'}, self.item)
        self.assertEqual(values[FIELDS[1]], 'UNKNOWN')
        self.assertEqual(values[FIELDS[2]], 'Masala')
        self.assertIn('not verified', values[FIELDS[5]])

    def test_missing_barcode_is_not_filled_from_master(self):
        values = resolve({**self.line, 'barcode': None}, self.item)
        self.assertEqual(values[FIELDS[1]], 'Not recorded')
        self.assertEqual(values[FIELDS[2]], 'Masala six')
        self.assertIn('current Item setup', values[FIELDS[5]])

    def test_duplicate_packing_match_is_not_guessed(self):
        self.item.custom_retail_packing_detail.append(self.item.custom_retail_packing_detail[0])
        self.assertEqual(resolve(self.line, self.item)[FIELDS[2]], 'Masala')

    def test_saved_snapshot_survives_item_rename(self):
        values = resolve(self.line, self.item)
        self.line[SNAPSHOT] = json.dumps(dict(version=1, **values))
        self.item.custom_retail_packing_detail[0].packing_name = 'Renamed'
        self.line.uom = 'Changed'
        self.assertEqual(resolve(self.line, self.item), values)

    def test_payload_can_supply_missing_barcode(self):
        values = resolve({**self.line, 'barcode': None}, self.item, {'barcode': 'SIX'})
        self.assertEqual(values[FIELDS[1]], 'SIX')

    def test_same_item_different_lines_remain_distinct(self):
        second = frappe._dict({**self.line, 'name': 'ROW4', 'idx': 1, 'barcode': 'FOUR', 'conversion_factor': 4})
        rows = [frappe._dict(item_code='ITEM', voucher_detail_no='ROW4'),
                frappe._dict(item_code='ITEM', voucher_detail_no='ROW6')]
        self.lookup([second, self.line]).enrich(rows, lambda r: ('Sales Invoice', 'SI'))
        self.assertEqual([r[FIELDS[1]] for r in rows], ['FOUR', 'SIX'])

    def test_sle_split_uses_only_movement_share(self):
        rows = [frappe._dict(item_code='ITEM', voucher_detail_no='ROW6', actual_qty=-6, qty_after_transaction=10),
                frappe._dict(item_code='ITEM', voucher_detail_no='ROW6', actual_qty=-6, qty_after_transaction=4)]
        before = [dict(r) for r in rows]
        self.lookup().enrich(rows, lambda r: ('Sales Invoice', 'SI'))
        self.assertEqual([r[FIELDS[3]] for r in rows], [1, 1])
        self.assertTrue(all(r['retail_packing_breakdown'].startswith('1 Pack') for r in rows))
        for row, original in zip(rows, before):
            self.assertEqual({k: row[k] for k in original}, original)

    def test_return_preserves_sign(self):
        row = frappe._dict(item_code='ITEM', voucher_detail_no='ROW6', actual_qty=6)
        self.lookup().enrich([row], lambda r: ('Sales Invoice', 'SI'))
        self.assertEqual(row[FIELDS[3]], -1)

    def test_mixed_packing_row_has_breakdown(self):
        piece = frappe._dict({**self.line, 'name': 'ROW1', 'barcode': 'ONE', 'uom': 'Nos', 'conversion_factor': 1, 'qty': 3})
        row = frappe._dict(item_code='ITEM')
        self.lookup([piece, self.line]).enrich([row], lambda r: ('Sales Invoice', 'SI'))
        self.assertIsNone(row[FIELDS[0]])
        self.assertIsNone(row[FIELDS[3]])
        self.assertIn('3 Nos', row.retail_packing_breakdown)
        self.assertIn('2 Pack', row.retail_packing_breakdown)

    def test_grouped_profitability_preserves_totals_and_grouping(self):
        rows = []
        for qty, barcode, factor in [(2, 'SIX', 6), (3, 'FOUR', 4)]:
            identity = resolve({**self.line, 'qty': qty, 'barcode': barcode, 'conversion_factor': factor}, self.item)
            rows.append(frappe._dict(dict(identity, item_code='ITEM', net_sales=20, cost_amount=10,
                invoice_no=barcode, is_return=0, source_status='Recorded / Posted')))
        with patch('frappe._', side_effect=lambda v: v):
            grouped = aggregate_profitability(rows, ['item_code'])
        self.assertEqual(len(grouped), 1)
        self.assertEqual((grouped[0].net_sales, grouped[0].cost_amount, grouped[0].gross_profit), (40, 20, 20))
        self.assertIn('2 Pack | SIX', grouped[0].retail_packing_breakdown)
        self.assertIn('3 Pack | FOUR', grouped[0].retail_packing_breakdown)

    def test_total_rows_not_enriched(self):
        row = frappe._dict(item_code='ITEM', is_total_row=1)
        self.lookup().enrich([row], lambda r: ('Sales Invoice', 'SI'))
        self.assertNotIn(FIELDS[0], row)

    def test_columns_additive_and_idempotent(self):
        existing = [dict(fieldname='qty', label='Qty')]
        output = append_columns(existing, columns())
        self.assertEqual(existing, [dict(fieldname='qty', label='Qty')])
        self.assertEqual(append_columns(output, columns()), output)

    def test_snapshot_only_updates_custom_field(self):
        class Line(frappe._dict):
            def set(self, key, value):
                self[key] = value
        line = Line(self.line)
        line.meta = frappe._dict(has_field=lambda field: field == SNAPSHOT)
        doc = frappe._dict({'items': [line]})
        before = dict(line)
        with patch('frappe.get_cached_doc', return_value=self.item):
            snapshot_document(doc)
        self.assertEqual({k: line[k] for k in before}, before)
        self.assertEqual(json.loads(line[SNAPSHOT])[FIELDS[2]], 'Masala six')

    def test_consolidated_return_uses_original_packing_with_return_quantity(self):
        original = self.lookup()
        original.lines = {('POS Invoice', 'POS'): [self.line]}
        lookup = self.lookup()
        lookup.pos_lookup = original
        consolidated = frappe._dict(self.line)
        consolidated.update(pos_invoice='POS', pos_invoice_item='ROW6', barcode=None,
                            uom='Nos', conversion_factor=1, qty=-6, stock_qty=-6)
        values = lookup.values(('Sales Invoice', 'SI'), consolidated)
        self.assertEqual(values[FIELDS[0]], 'Pack')
        self.assertEqual(values[FIELDS[1]], 'SIX')
        self.assertEqual(values[FIELDS[3]], -1)

    def test_ledger_repeated_item_uses_running_balance_to_find_exact_line(self):
        from retail.report_transaction_identity import enrich_stock_ledger
        entries = [frappe._dict(posting_datetime='2026-10-15 12:00:00', item_code='ITEM',
            warehouse='WH', voucher_type='Sales Invoice', voucher_no='SI',
            voucher_detail_no=detail, actual_qty=-6, stock_value_difference=-10,
            qty_after_transaction=balance) for detail,balance in [('ROW4',12),('ROW6',6)]]
        rows = [frappe._dict({**e, 'date': e.posting_datetime}) for e in reversed(entries)]
        for row in rows:
            row.pop('voucher_detail_no')
        with patch('retail.report_transaction_identity.frappe.get_all',return_value=entries), patch(
                'retail.report_transaction_identity.enrich_movements') as enrich:
            enrich_stock_ledger(rows)
        self.assertEqual([r.retail_source_detail for r in rows], ['ROW6','ROW4'])
        self.assertEqual(enrich.call_count,1)

    def test_segregated_batch_passes_split_qty_without_changing_existing_fields(self):
        from retail.report_transaction_identity import enrich_stock_ledger
        entry=frappe._dict(posting_datetime='2026-10-15 12:00:00', item_code='ITEM',
            warehouse='WH', voucher_type='Sales Invoice', voucher_no='SI',
            voucher_detail_no='ROW6', actual_qty=-12, stock_value_difference=-20,
            qty_after_transaction=6,serial_and_batch_bundle='BUNDLE')
        row=frappe._dict({**entry,'date':entry.posting_datetime,'qty':-3,'qty_after_transaction':15})
        row.pop('voucher_detail_no')
        original=dict(row)
        def enrich(rows):
            self.assertEqual(rows[0]['actual_qty'],-3)
            rows[0][FIELDS[3]]=0.5
        with patch('retail.report_transaction_identity.frappe.get_all',return_value=[entry]),patch(
                'retail.report_transaction_identity.enrich_movements',side_effect=enrich):
            enrich_stock_ledger([row])
        self.assertEqual(row[FIELDS[3]],0.5)
        self.assertTrue(all(row[k]==v for k,v in original.items()))

    def test_new_display_quantities_and_factors_are_not_summed_in_totals(self):
        from frappe.desk.query_report import add_total_row
        with patch('frappe.desk.query_report._',side_effect=lambda v:v):
            cols=append_columns([dict(fieldname='item_code',fieldtype='Data')],columns())
            rows=[frappe._dict(item_code='ITEM',**resolve(self.line,self.item))]
            add_total_row(rows,cols)
        self.assertEqual(rows[-1][next(i for i,c in enumerate(cols) if c['fieldname']==FIELDS[3])],'')
        self.assertEqual(rows[-1][next(i for i,c in enumerate(cols) if c['fieldname']==FIELDS[4])],'')

    def test_malformed_historical_payload_does_not_break_identity_resolution(self):
        from retail.transaction_identity import payload_items
        for value in ('not json', '[]', '{"items":{}}', '{"items":"wrong"}'):
            self.assertEqual(payload_items(value),[])
        self.assertEqual(payload_items('{"items":[null,{"barcode":"SIX"}]}'),[{}, {'barcode':'SIX'}])

    def test_margin_report_uses_combined_movement_qty_without_altering_legacy_fields(self):
        from retail.report_transaction_identity import enrich_report
        row=frappe._dict(voucher_type='Sales Invoice',voucher_no='SI',voucher_detail_no='ROW6',
                        actual_qty=-6,qty_in=0,qty_out=12,item_code='ITEM')
        before=dict(row)
        def enrich(rows):
            self.lookup().enrich(rows,lambda r:('Sales Invoice','SI'))
        with patch('retail.report_transaction_identity.enrich_movements',side_effect=enrich):
            result=enrich_report('Margin By Movement',([], [row]))
        self.assertEqual(result[1][0][FIELDS[3]],2)
        self.assertTrue(all(row[k]==v for k,v in before.items()))

    def test_unknown_quantity_remains_unknown_in_breakdown(self):
        from retail.transaction_identity import packing_breakdown
        values=resolve({**self.line,'qty':None},self.item)
        self.assertTrue(packing_breakdown([values]).startswith('? Pack'))
