"""Read-only regression tests; all invoice records live in in-memory SQLite."""
import sqlite3
import unittest
from unittest.mock import patch, MagicMock

import frappe
from retail.retail_app.report import profitability
from retail.retail_app.report.daily_transaction_log import daily_transaction_log as log
from retail.retail_app.report.sales_payment_mode_summary import sales_payment_mode_summary as payments
from retail.retail_app.report.item_group_sales_analysis import item_group_sales_analysis as groups


class TestTradingSalesSeparation(unittest.TestCase):
    def setUp(self):
        frappe.local.lang = 'en'
        settings = patch.object(frappe, 'get_system_settings', return_value='UTC')
        settings.start()
        self.addCleanup(settings.stop)
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            create table `tabPOS Invoice` (name text, docstatus int);
            insert into `tabPOS Invoice` values ('BILL',1), ('BILL-RETURN',1), ('BILL-CANCELLED',2);
            create table `tabSales Invoice` (name text, docstatus int, is_pos int,
                is_consolidated int, posting_date text);
            insert into `tabSales Invoice` values
                ('TRADE',1,0,0,'2026-11-10'), ('TRADE-RETURN',1,0,0,'2026-11-10'),
                ('POS',1,1,0,'2026-11-10'), ('POS-CONSOLIDATED',1,0,1,'2026-11-10'),
                ('POS-RETURN',1,1,0,'2026-11-10'), ('CANCELLED',2,0,0,'2026-11-10');
        ''')

    def test_shared_reader_filters_trading_but_preserves_pos_and_other_callers(self):
        def get_list(doctype, filters, **kwargs):
            conditions = ['docstatus = ?']
            values = [filters['docstatus']]
            for flag in ('is_pos', 'is_consolidated'):
                if flag in filters:
                    conditions.append(flag + ' = ?')
                    values.append(filters[flag])
            return [r['name'] for r in self.db.execute(
                'select name from `tab' + doctype + '` where ' + ' and '.join(conditions), values)]

        with patch.object(frappe, 'get_list', side_effect=get_list), \
             patch.object(frappe, 'get_doc', side_effect=lambda dt, name: name), \
             patch.object(profitability, 'invoice_rows', side_effect=lambda doc, **kw: [frappe._dict(invoice_no=doc)]):
            trading = profitability.profitability_rows(trading_only=True)
            self.assertEqual({r.invoice_no for r in trading}, {'TRADE', 'TRADE-RETURN'})
            self.assertEqual(len(profitability.profitability_rows()), 5)
            pos = profitability.profitability_rows(doctype='POS Invoice')
            self.assertEqual({r.invoice_no for r in pos}, {'BILL', 'BILL-RETURN'})

    def test_payment_filter_cannot_be_overridden_by_saved_pos_option(self):
        for include in (0, 1):
            conditions, _ = payments.get_conditions(frappe._dict(include_pos_invoices=include))
            self.assertIn('ifnull(si.is_pos, 0) = 0', conditions)
            self.assertIn('ifnull(si.is_consolidated, 0) = 0', conditions)
            predicate = conditions.split(' and ', 2)[2]
            rows = self.db.execute('select name from `tabSales Invoice` si where ' + predicate)
            self.assertEqual({r['name'] for r in rows}, {'TRADE', 'TRADE-RETURN', 'CANCELLED'})

    def test_log_query_excludes_pos_sales_returns_and_consolidations(self):
        captured = []
        db = MagicMock()
        with patch.dict(frappe.__dict__, db=db):
            db.sql.side_effect = lambda query, *a, **kw: captured.append(query) or []
            log.get_invoice_rows(frappe._dict(from_date='2026-11-10', to_date='2026-11-10'))
        predicate = captured[0].split('where ', 1)[1].split('and posting_date', 1)[0]
        rows = self.db.execute('select name from `tabSales Invoice` where ' + predicate)
        self.assertEqual({r['name'] for r in rows}, {'TRADE', 'TRADE-RETURN', 'CANCELLED'})

    def test_item_groups_ignore_old_combined_and_pos_filters(self):
        for source in ('Both', 'POS Invoice', 'Sales Invoice'):
            filters = groups.get_filters({'sales_source': source})
            self.assertEqual(filters.sales_source, 'Sales Invoice')
            with patch.object(profitability, 'profitability_rows', return_value=[]) as reader:
                groups.get_sales_rows(filters)
            self.assertEqual(reader.call_args.args[1], 'Sales Invoice')
            self.assertTrue(reader.call_args.kwargs['trading_only'])

    def test_trading_summaries_opt_in_without_changing_pos_reader(self):
        from retail.retail_app.report.daily_sales_summary import daily_sales_summary
        from retail.retail_app.report.daily_profit_report import daily_profit_report
        from retail.retail_app.report.counter_performance import counter_performance
        with patch.object(profitability, 'profitability_rows', return_value=[]) as reader, \
             patch.object(profitability, 'report_result', return_value=()), \
             patch.object(daily_profit_report, 'profitability_rows', reader), \
             patch.object(daily_profit_report, 'report_result', return_value=()), \
             patch.object(daily_sales_summary, 'get_columns', return_value=[]), \
             patch.object(counter_performance, 'get_payment_modes', return_value={}), \
             patch('retail.report_transaction_identity.enrich_profitability_rows'):
            daily_sales_summary.execute({})
            daily_profit_report.execute({'company': 'Example'})
            counter_performance.get_data(frappe._dict())
        self.assertEqual(len(reader.call_args_list), 3)
        self.assertTrue(all(c.kwargs.get('trading_only') for c in reader.call_args_list))
