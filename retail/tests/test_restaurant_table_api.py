import unittest
from unittest.mock import patch

import frappe
from retail.api import pos_sync


class TestRestaurantTableAPI(unittest.TestCase):
    def test_snapshot_includes_disabled_rows_and_maps_only_contract_fields(self):
        table = frappe._dict(name="7", table_name="T07", branch="Other Branch", table_location="2", seating_capacity=6,
            enabled=0, owner="creator@example.com", creation="2026-11-17 10:00:00",
            modified_by="editor@example.com", modified="2026-11-17 11:00:00")
        with patch.object(pos_sync.frappe, "get_all", side_effect=[
            [frappe._dict(name="2", location_name="Second Floor")], [table]
        ]) as query:
            rows = pos_sync._restaurant_table_rows()
        self.assertEqual(rows, [{"table_id": "7", "table_name": "T07", "branch": "Other Branch", "table_location": "Second Floor",
            "seating_capacity": 6, "is_active": False, "is_deleted": False,
            "created_by": "creator@example.com", "created_on": "2026-11-17 10:00:00",
            "modified_by": "editor@example.com", "modified_on": "2026-11-17 11:00:00"}])
        self.assertNotIn("filters", query.call_args.kwargs)
        self.assertEqual(query.call_args.kwargs["limit_page_length"], 0)

    def test_empty_snapshot_is_an_empty_list(self):
        with patch.object(pos_sync.frappe, "get_all", side_effect=[[], []]):
            self.assertEqual(pos_sync._restaurant_table_rows(), [])

    def test_download_requires_pos_user_and_valid_counter_before_reading(self):
        with patch.object(pos_sync, "_assert_pos_user", side_effect=frappe.PermissionError), \
             patch.object(pos_sync, "_restaurant_table_rows") as rows:
            with self.assertRaises(frappe.PermissionError):
                pos_sync.get_pos_tables("branch", "counter")
            rows.assert_not_called()
        with patch.object(pos_sync, "_assert_pos_user"), \
             patch.object(pos_sync, "_as_dict", return_value={"branch": "B", "counter_code": "C"}), \
             patch.object(pos_sync, "_counter", side_effect=frappe.PermissionError), \
             patch.object(pos_sync, "_restaurant_table_rows") as rows:
            with self.assertRaises(frappe.PermissionError):
                pos_sync.get_pos_tables("B", "C")
            rows.assert_not_called()

    def test_success_uses_same_counter_and_standard_response_envelope(self):
        with patch.object(pos_sync, "_assert_pos_user"), \
             patch.object(pos_sync, "_as_dict", return_value={"branch": "B", "counter_code": "C"}), \
             patch.object(pos_sync, "_counter") as counter, \
             patch.object(pos_sync, "_restaurant_table_rows", return_value=[]) as rows, \
             patch.object(pos_sync, "now_datetime", return_value="2026-11-17 14:30:00"):
            result = pos_sync.get_pos_tables("B", "C")
        counter.assert_called_once_with("B", "C")
        rows.assert_called_once_with()
        self.assertEqual(result["status"], "Success")
        self.assertEqual(result["tables"], [])
        self.assertIn("server_time", result)


class TestRestaurantBranchDefaults(unittest.TestCase):
    def test_default_exists_only_for_exactly_one_site_branch(self):
        from retail.restaurant import defaults
        for branches, expected in [([], None), (["Only"], "Only"), (["A", "B"], None)]:
            with self.subTest(branches=branches), patch.object(defaults.frappe, "get_all", return_value=branches):
                self.assertEqual(defaults.single_branch(), expected)

    def test_missing_branch_defaults_but_explicit_branch_is_preserved(self):
        from retail.restaurant.doctype.restaurant_table import restaurant_table
        empty = frappe._dict(branch=None)
        explicit = frappe._dict(branch="Selected Branch")
        with patch.object(restaurant_table, "single_branch", return_value="Only") as default:
            restaurant_table.RestaurantTable.before_validate(empty)
            self.assertEqual(empty.branch, "Only")
            default.reset_mock()
            restaurant_table.RestaurantTable.before_validate(explicit)
            default.assert_not_called()
            self.assertEqual(explicit.branch, "Selected Branch")
