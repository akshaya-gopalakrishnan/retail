"""Ranked Item Desk searches on disposable SQLite data."""
import re
import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import frappe
from retail.domains.item import desk_search


class TestDeskSearch(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.executescript('''create table tabItem(name text,item_name text,custom_barcode text);
            create table `tabItem Barcode`(parent text, barcode text);
            insert into tabItem values ('P','Pen Drive','BP'),('D','Drive Pen','BD'),
            ('L','Long Pen Drive','BL'),('X','Spending Driven','BX'),('H','Pen Holder','BH');''')
        def sql(query, values=None, as_dict=False, **kw):
            cursor = self.db.execute(re.sub(r'%\((\w+)\)s', r':\1', query), values or {})
            keys = [c[0] for c in cursor.description]
            rows = cursor.fetchall()
            return [frappe._dict(zip(keys, row)) for row in rows] if as_dict else rows
        def native(dt, txt, sf, start, length, filters, as_dict=False):
            codes = filters['name'][1]
            return [frappe._dict(name=c) if as_dict else (c,) for c in codes if c != 'X']
        for p in [patch.object(frappe, 'db', SimpleNamespace(sql=sql)),
                  patch.object(frappe, 'local', SimpleNamespace(flags=frappe._dict(in_test=False))),
                  patch.object(frappe, 'has_permission'),
                  patch.object(frappe, 'session', frappe._dict(user='Administrator')),
                  patch.object(frappe, 'conf', frappe._dict(read_from_replica=False)),
                  patch.object(desk_search, 'get_match_cond', return_value=''),
                  patch.object(desk_search, 'native_item_query', side_effect=native)]:
            p.start()
            self.addCleanup(p.stop)

    def test_dropdown_ranking_paging_and_native_eligibility(self):
        method = desk_search.item_query.__wrapped__
        # Bypass the framework sanitizer (its metadata needs a real site).
        while hasattr(method, '__wrapped__'):
            method = method.__wrapped__
        for text in ['d p', 'dri pe', 'drive pen']:
            rows = method('Item', text, 'name', 0, 20, {})
            self.assertIn(('P',), rows)
            self.assertNotIn(('X',), rows)
        self.assertEqual(method('Item', 'drive pen', 'name', 0, 1, {}), [('D',)])
        self.assertEqual(method('Item', 'drive pen', 'name', 1, 1, {}), [('P',)])

    def test_list_matches_count_and_pagination(self):
        args = frappe._dict(doctype='Item',fields=['name','item_name'],
            filters=[['Item','item_name','like','%drive pen%']],start=0,page_length=1)
        with patch.object(desk_search.reportview, 'get_form_params', side_effect=lambda: frappe._dict(args)), \
             patch.object(desk_search.reportview, 'execute', return_value='select name,item_name from tabItem'):
            result = desk_search.get()
            self.assertEqual(result['values'][0], ['D','Drive Pen'])
            self.assertEqual(desk_search.get_count(), 4)
            args.start = 1
            self.assertEqual(desk_search.get()['values'][0], ['P','Pen Drive'])

    def test_comment_counts_are_added_to_rows_after_sql_generation(self):
        args = frappe._dict(doctype='Item', fields=['name', 'item_name', '_comments'],
            filters=[['Item', 'item_name', 'like', '%drive pen%']],
            start=0, page_length=20, with_comment_count=1)
        def generate(**kwargs):
            self.assertFalse(kwargs['run'])
            self.assertFalse(kwargs['with_comment_count'])
            return '''select name,item_name,'[{"comment":"one"}]' as _comments from tabItem'''
        with patch.object(desk_search.reportview, 'get_form_params', side_effect=lambda: frappe._dict(args)), \
             patch.object(desk_search.reportview, 'execute', side_effect=generate):
            result = desk_search.get()
            self.assertTrue(result['values'])
            index = result['keys'].index('_comment_count')
            self.assertTrue(all(row[index] == 1 for row in result['values']))
            self.assertEqual(desk_search.get_count(), len(result['values']))
