import unittest
from unittest.mock import patch
import frappe
from retail.retail_app import retail_dashboard as dashboard


class TestDashboardProfitFilters(unittest.TestCase):
    def test_company_and_date_use_posted_profit(self):
        with patch.object(dashboard, "_get_company_filter", return_value="Test Company"), patch.object(
            dashboard, "get_profit_summary", return_value=frappe._dict(gross_profit=25)
        ) as summary:
            self.assertEqual(dashboard._get_today_gross_profit_from_report("2026-09-16"),25)
            summary.assert_called_once_with("2026-09-16", "Test Company")

    def test_missing_cost_is_not_zero_profit(self):
        with patch.object(dashboard, "_get_company_filter", return_value="Test Company"), patch.object(
            dashboard, "get_profit_summary", return_value=frappe._dict(gross_profit=None)
        ):
            self.assertIsNone(dashboard._get_today_gross_profit_from_report("2026-09-16"))
