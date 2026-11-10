"""Execute packing search SQL on disposable in-memory data, never a hosted site."""
import re
import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe
from retail.domains.purchase import packing_search as search


class TestPackingSearchPagination(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.addCleanup(self.db.close)
        self.db.executescript('''
            create table tabItem (name text, item_name text, custom_barcode text,
                stock_uom text, disabled int, is_purchase_item int, has_variants int, modified text);
            create table `tabRetail Packing Detail` (name text, parent text, parenttype text,
                packing_name text, barcode text, uom text, packing_uom text,
                conversion_factor real, disabled int);
        ''')
        self.db.executemany('insert into tabItem values (?,?,?,?,0,1,0,?)', [
            (f'SKU{i:03}', 'Search Item', f'BAR{i:03}', 'Nos', '2026-11-10') for i in range(250)])
        self.calls = []
        def sql(query, values, **kwargs):
            self.calls.append(dict(values))
            query = re.sub(r'%\((\w+)\)s', r':\1', query)
            return [frappe._dict(dict(row)) for row in self.db.execute(query, values)]
        self.allowed = lambda code: True
        def native(dt, txt, **kwargs):
            codes = kwargs['filters']['name'][1]
            return [[code] for code in codes if self.allowed(code)]
        patches = [patch.object(frappe, 'db', SimpleNamespace(sql=sql)),
                   patch.object(frappe, 'local', SimpleNamespace(flags=frappe._dict(in_test=False))),
                   patch.object(frappe, 'has_permission'),
                   patch.object(search, 'get_match_cond', return_value=''),
                   patch.object(search, 'search_widget', side_effect=native)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_broad_search_stops_after_first_batch_and_all_pages_remain_reachable(self):
        first = search.search('Search', page_length=21)
        self.assertEqual([r.item_code for r in first], [f'SKU{i:03}' for i in range(21)])
        self.assertEqual(len(self.calls), 1)
        second = search.search('Search', start=20, page_length=21)
        self.assertEqual(second[0].item_code, 'SKU020')
        last = search.search('Search', start=240, page_length=20)
        self.assertEqual(len(last), 10)
        self.assertEqual(last[-1].item_code, 'SKU249')

    def test_paging_counts_only_permission_allowed_parents(self):
        self.allowed = lambda code: int(code[3:]) % 2 == 0
        result = search.search('Search', start=20, page_length=20)
        self.assertEqual([r.item_code for r in result], [f'SKU{i:03}' for i in range(40, 80, 2)])

    def test_empty_recent_list_stays_five_and_requested_size_is_capped(self):
        self.assertEqual(len(search.search('', page_length=500)), 5)
        self.assertEqual(len(search.search('Search', page_length=500)), 50)

    def test_packing_identity_factor_and_barcode_survive_pagination(self):
        self.db.execute('insert into `tabRetail Packing Detail` values (?,?,?,?,?,?,?,?,?)',
                        ('PACK', 'SKU000', 'Item', 'Search Item Box', 'PACKBAR', 'Box-36', 'Box', 36, 0))
        result = search.search('PACKBAR', page_length=20)
        self.assertEqual(len(result), 1)
        self.assertEqual((result[0].packing_id, result[0].uom, result[0].conversion_factor), ('PACK', 'Box-36', 36))

    def test_item_read_permission_is_required(self):
        with patch.object(frappe, 'has_permission', side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                search.search('Search')
        self.assertFalse(self.calls)
