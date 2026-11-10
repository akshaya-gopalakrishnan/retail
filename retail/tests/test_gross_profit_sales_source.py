import sqlite3
import unittest
from unittest.mock import patch

import frappe
from pypika import Query, Table
from retail.core_compat.gross_profit import sales_source_condition


class TestGrossProfitSalesSource(unittest.TestCase):
    def test_default_pos_combined_and_returns(self):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.executescript('''
            create table invoices (name text, is_pos int, is_consolidated int,
                docstatus int, is_return int, amount real);
            insert into invoices values
                ('TRADE',0,0,1,0,100), ('TRADE-RETURN',0,0,1,1,-10),
                ('LEGACY-POS',1,0,1,0,20), ('CLOSED-POS',1,1,1,0,30),
                ('CONSOLIDATED',0,1,1,0,40), ('POS-RETURN',1,1,1,1,-5),
                ('CANCELLED',1,1,2,0,1000);
        ''')
        invoice = Table('invoices')
        expected = {
            None: ({'TRADE', 'TRADE-RETURN'}, 90),
            'Trading Sales': ({'TRADE', 'TRADE-RETURN'}, 90),
            'POS Sales': ({'LEGACY-POS', 'CLOSED-POS', 'CONSOLIDATED', 'POS-RETURN'}, 85),
            'Trading + POS Sales': ({'TRADE', 'TRADE-RETURN', 'LEGACY-POS', 'CLOSED-POS', 'CONSOLIDATED', 'POS-RETURN'}, 175),
        }
        for source, (names, total) in expected.items():
            with self.subTest(source=source):
                query = Query.from_(invoice).select(invoice.name, invoice.amount).where(invoice.docstatus == 1)
                condition = sales_source_condition({'sales_source': source}, invoice)
                if condition is not None:
                    query = query.where(condition)
                rows = db.execute(query.get_sql()).fetchall()
                self.assertEqual({r[0] for r in rows}, names)
                self.assertEqual(sum(r[1] for r in rows), total)
                returns = db.execute(query.where(invoice.is_return == 1).get_sql()).fetchall()
                self.assertEqual({r[0] for r in returns}, {name for name in names if name.endswith('RETURN')})

    def test_invalid_source_is_rejected(self):
        with patch('retail.core_compat.gross_profit._', side_effect=lambda text: text), \
             patch.object(frappe, 'throw', side_effect=ValueError):
            with self.assertRaises(ValueError):
                sales_source_condition({'sales_source': 'unexpected'}, Table('invoices'))
