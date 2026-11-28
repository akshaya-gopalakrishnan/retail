import unittest
from contextlib import ExitStack
from unittest.mock import patch

import frappe
from retail.api import pos_sync


class TestOptionalMasterContext(unittest.TestCase):
    def test_optional_parameters_do_not_select_counter(self):
        for branch, counter in [(None, None), ('BRANCH', None), (None, 'C001')]:
            with self.subTest(branch=branch, counter=counter), ExitStack() as stack:
                stack.enter_context(patch.object(pos_sync, '_assert_pos_user'))
                stack.enter_context(patch.object(pos_sync, '_as_dict', return_value=frappe._dict(
                    branch=branch, counter_code=counter, modified_after='CURSOR')))
                resolve = stack.enter_context(patch.object(pos_sync, '_counter'))
                general = stack.enter_context(patch.object(pos_sync, '_general_pos_master_data', return_value={'status': 'Success'}))
                self.assertEqual(pos_sync.get_pos_master_data(branch, counter), {'status': 'Success'})
                resolve.assert_not_called()
                general.assert_called_once_with(branch, counter, 'CURSOR')

    def test_general_master_has_no_terminal_stock_or_promotions(self):
        item = frappe._dict(item_code='ITEM', current_stock=0, packings=[{'current_stock': 0}])
        with ExitStack() as stack:
            stack.enter_context(patch.object(pos_sync, '_catalog_master_data', return_value={'items': [item], 'packing_details': []}))
            stack.enter_context(patch.object(pos_sync, '_supplier_master_rows', return_value=[{'name': 'SUP'}]))
            stack.enter_context(patch.object(pos_sync, '_pos_payment_modes', return_value=[]))
            stack.enter_context(patch.object(pos_sync, 'get_system_timezone', return_value='Asia/Dubai'))
            stack.enter_context(patch.object(pos_sync, 'now_datetime', return_value='2026-11-28 12:00:00'))
            stack.enter_context(patch.object(pos_sync, 'with_item_identity', side_effect=lambda payload, *a, **kw: payload))
            stack.enter_context(patch.object(frappe, 'get_all', return_value=[]))
            stack.enter_context(patch.object(frappe, 'get_roles', return_value=['System Manager']))
            result = pos_sync._general_pos_master_data()
        self.assertIsNone(result['counter'])
        self.assertIsNone(item.current_stock)
        self.assertIsNone(item.packings[0]['current_stock'])
        self.assertEqual(result['suppliers'], [{'name': 'SUP'}])
        self.assertEqual(result['promo_prices'], [])

    def test_suppliers_include_disabled_changes_for_incremental_sync(self):
        with patch.object(frappe, 'get_all', return_value=[]) as query:
            pos_sync._supplier_master_rows([['modified', '>', 'CURSOR']])
        self.assertEqual(query.call_args.kwargs['filters'], [['modified', '>', 'CURSOR']])
        self.assertIn('disabled', query.call_args.kwargs['fields'])
