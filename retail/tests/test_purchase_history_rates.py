"""Execute purchase-summary SQL against a disposable in-memory database."""
import re
import sqlite3
import unittest
from unittest.mock import Mock, patch

import frappe
from retail.domains.item import average_purchase_rate as history, vat_pricing, rate_audit


class TestPurchaseHistoryRates(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(':memory:')
        self.connection.row_factory = sqlite3.Row
        self.addCleanup(self.connection.close)
        self.connection.execute('create table tabItem (name text, item_name text)')
        self.connection.execute("insert into tabItem values ('SKU', 'Product')")
        for parent, child in [('Purchase Receipt', 'Purchase Receipt Item'),
                              ('Purchase Invoice', 'Purchase Invoice Item')]:
            self.connection.execute(f'''create table `tab{parent}` (name text, docstatus integer,
                is_return integer, update_stock integer, posting_date text, posting_time text, creation text)''')
            self.connection.execute(f'''create table `tab{child}` (parent text, item_code text,
                stock_qty real, base_net_amount real, idx integer, purchase_receipt text, is_free_item integer)''')
        self.db = Mock(sql=self.sql)
        self.db.has_column.return_value = True
        db_patch = patch.object(frappe, 'db', self.db)
        db_patch.start()
        self.addCleanup(db_patch.stop)

    def sql(self, query, params, **kwargs):
        query = re.sub(r'%\((\w+)\)s', r':\1', query)
        return [frappe._dict(dict(row)) for row in self.connection.execute(query, params)]

    def purchase(self, name, amount, qty, date='2026-11-01', time='10:00:00',
                 invoice=False, status=1, update_stock=1, receipt='', is_return=0):
        parent, child = ('Purchase Invoice', 'Purchase Invoice Item') if invoice else (
            'Purchase Receipt', 'Purchase Receipt Item')
        self.connection.execute(f'insert into `tab{parent}` values (?,?,?,?,?,?,?)',
            (name, status, is_return, update_stock, date, time, '2026-11-11'))
        self.connection.execute(f'insert into `tab{child}` values (?,?,?,?,?,?,?)',
            (name, 'SKU', qty, amount, 1, receipt, 0))

    def test_no_purchases_ignores_manual_and_previous_average_fallback(self):
        self.assertEqual(history.get_average_purchase_rate('SKU', fallback_rate=38), 0)
        self.assertEqual(history.get_average_purchase_rate_for_item_name('Product', 38), 0)
        self.assertEqual(history.get_purchase_history_rates('SKU')['last_purchase_rate'], 0)

    def test_weighted_whole_purchase_average_stock_units_and_latest_posting(self):
        self.purchase('PR-1', 100, 10)
        self.purchase('PI-1', 60, 20, date='2026-11-03', invoice=True)
        self.purchase('BACKDATED', 40, 10, date='2026-10-01')
        rates = history.get_purchase_history_rates('SKU')
        self.assertEqual(rates['custom_average_purchase_rate'], 5)
        self.assertEqual(rates['last_purchase_rate'], 3)

    def test_drafts_cancellations_returns_and_non_stock_or_receipt_invoices_excluded(self):
        self.purchase('GOOD', 50, 10)
        for name, opts in [('DRAFT', {'status': 0}), ('CANCELLED', {'status': 2}),
                           ('RETURN', {'is_return': 1}), ('BILL', {'invoice': True, 'update_stock': 0}),
                           ('LINKED', {'invoice': True, 'receipt': 'GOOD'})]:
            self.purchase(name, 900, 10, date='2026-11-09', **opts)
        self.assertEqual(history.get_purchase_history_rates('SKU'),
            {'last_purchase_rate': 5, 'custom_average_purchase_rate': 5})

    def test_free_quantities_count_in_average_but_do_not_replace_last_paid_rate(self):
        self.purchase('PR', 100, 10)
        self.connection.execute("insert into `tabPurchase Receipt Item` values ('PR','SKU',2,0,2,'',1)")
        rates = history.get_purchase_history_rates('SKU')
        self.assertAlmostEqual(rates['custom_average_purchase_rate'], 100 / 12)
        self.assertEqual(rates['last_purchase_rate'], 10)

    def test_cancelling_latest_restores_previous_and_last_cancel_returns_zero(self):
        self.purchase('OLD', 10, 10)
        self.purchase('NEW', 30, 10, time='11:00:00')
        self.assertEqual(history.get_purchase_history_rates('SKU')['last_purchase_rate'], 3)
        self.connection.execute("update `tabPurchase Receipt` set docstatus=2 where name='NEW'")
        self.assertEqual(history.get_purchase_history_rates('SKU')['last_purchase_rate'], 1)
        self.connection.execute('update `tabPurchase Receipt` set docstatus=2')
        self.assertEqual(history.get_purchase_history_rates('SKU'),
            {'last_purchase_rate': 0, 'custom_average_purchase_rate': 0})

    def test_item_save_overwrites_stale_or_client_supplied_history_not_maintained_price(self):
        doc = Mock(name='Item')
        doc.name = 'SKU'
        doc.is_new.return_value = False
        doc.meta.has_field.return_value = True
        vat_pricing._sync_last_purchase_rate_from_item_master(doc)
        self.assertEqual(dict(call.args for call in doc.set.call_args_list),
            {'last_purchase_rate': 0, 'custom_average_purchase_rate': 0})
        self.db.set_value.assert_not_called()

    def test_item_and_price_average_sync_never_uses_old_average(self):
        doc = Mock()
        doc.name = 'SKU'
        doc.get.return_value = 38
        with patch.object(frappe, 'get_all', return_value=['PRICE']), patch.object(
            frappe, 'clear_document_cache'):
            history.sync_average_purchase_rate_from_item(doc)
        self.assertEqual(self.db.set_value.call_args_list[0].args[2],
            {'last_purchase_rate': 0, 'custom_average_purchase_rate': 0})
        self.assertEqual(self.db.set_value.call_args_list[1].args[3], 0)
        doc.get.assert_not_called()

    def test_rate_manager_changes_only_maintained_fields(self):
        with patch.object(frappe, 'get_system_settings', return_value="Banker's Rounding"):
            values = rate_audit._get_item_update_values('Purchase',
                {'net': 10, 'gross': 10.5, 'vat': .5})
        self.assertNotIn('last_purchase_rate', values)
        self.assertNotIn('custom_average_purchase_rate', values)
        self.assertEqual(values['custom_purchase_net_rate'], 10)
