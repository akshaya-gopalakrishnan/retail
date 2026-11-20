"""Read-only regression checks for business-day membership."""
import unittest
from unittest.mock import MagicMock, patch
import frappe
from frappe.utils import getdate
from retail.patches import cashier_shift_business_date as migration
from retail.retail_app.doctype.pos_branch_day_closing import pos_branch_day_closing as day
from retail.retail_app.doctype.pos_branch_day_closing.pos_branch_day_closing import _get_cashier_shifts

class TestCashierShiftBusinessDate(unittest.TestCase):
    def test_closing_selects_business_date_and_legacy_opening_date(self):
        selected = frappe._dict(name='selected', opening_time='2026-11-17 10:00:00')
        legacy = frappe._dict(name='legacy', opening_time='2026-11-18 09:00:00')
        with patch.object(frappe, 'db', MagicMock()) as db:
            db.get_values.side_effect = [[selected], [legacy]]
            self.assertEqual(_get_cashier_shifts('Branch', '2026-11-18'), [selected, legacy])
        self.assertEqual(db.get_values.call_args_list[0].kwargs['filters'],
                         {'branch': 'Branch', 'business_date': getdate('2026-11-18')})
        filters = db.get_values.call_args_list[1].kwargs['filters']
        self.assertEqual(filters['business_date'], ['is', 'not set'])
        self.assertEqual(filters['opening_time'][1][0], '2026-11-18 00:00:00')

    def test_day_totals_and_active_sessions_use_selected_shifts(self):
        class Closing(frappe._dict):
            def set(self, key, value):
                self[key] = value
            def append(self, key, value):
                self.setdefault(key, []).append(frappe._dict(value))
        shift = frappe._dict(name='selected', cashier_employee='E', cashier_name='Cashier',
            status='Closed', opening_time='2026-11-17 10:00:00', closing_time=None,
            opening_amount=10, cash_in_amount=5, cash_out_amount=2,
            expected_cash=113, closing_amount=110, variance=-3)
        for shifts in ([shift], []):
            closing = Closing(branch='Branch', business_date='2026-11-18')
            with patch.object(day, '_get_cashier_shifts', return_value=shifts), patch.object(
                day, '_get_sales_by_shift', return_value={'selected': {'sales_total': 100, 'invoice_count': 2}}
            ), patch.object(day, '_get_counter_summary', return_value=[]), patch.object(frappe, 'db', MagicMock()) as db:
                db.count.return_value = 0
                day.POSBranchDayClosing.refresh_summaries(closing)
                if shifts:
                    self.assertEqual((closing.total_sales, closing.total_invoice_count,
                        closing.total_expected_cash, closing.total_variance), (100, 2, 113, -3))
                    self.assertEqual(db.count.call_args.args[1],
                        {'branch': 'Branch', 'status': 'Active', 'cashier_shift': ['in', ['selected']]})
                else:
                    db.count.assert_not_called()
                    self.assertEqual((closing.total_sales, closing.total_invoice_count), (0, 0))
                self.assertEqual(closing.active_counter_session_count, 0)

    def test_log_recovery_legacy_fallback_and_existing_date(self):
        shifts = [frappe._dict(name='new', branch='Branch', business_date=None, opening_time='2026-11-17 09:24:46', external_open_reference='open'),
                  frappe._dict(name='legacy', branch='Branch', business_date=None, opening_time='2026-11-16 09:00:00', external_open_reference=None),
                  frappe._dict(name='saved', business_date='2026-11-15')]
        log = frappe._dict(request_json='{"payload":{"branch":"Branch","business_date":"2026-11-18"}}')
        with patch.object(frappe, 'reload_doc'), patch.object(frappe, 'get_all', side_effect=[shifts, [log]]), patch.object(frappe, 'db', MagicMock()) as db:
            migration.execute()
        write = db.set_value
        self.assertEqual(write.call_count, 2)
        self.assertEqual(write.call_args_list[0].args[-1], getdate('2026-11-18'))
        self.assertEqual(write.call_args_list[1].args[-1], getdate('2026-11-16'))
        self.assertTrue(all(c.kwargs == {'update_modified': False} for c in write.call_args_list))
