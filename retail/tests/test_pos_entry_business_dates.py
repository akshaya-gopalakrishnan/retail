import unittest
from unittest.mock import MagicMock, patch
import frappe
from retail.pos_entry_business_dates import set_business_date

class Entry(frappe._dict):
    def set(self, field, value):
        self[field] = value

class TestEntryBusinessDates(unittest.TestCase):
    def test_closing_inherits_day_preserving_posting_date(self):
        doc = Entry(doctype="POS Closing Entry", pos_opening_entry="opening", posting_date="2026-11-17")
        with patch.object(frappe, "db", MagicMock()) as db:
            db.get_value.return_value = "2026-11-18"
            set_business_date(doc)
        self.assertEqual(str(doc.custom_pos_business_date), "2026-11-18")
        self.assertEqual(doc.posting_date, "2026-11-17")

    def test_payload_date_is_preserved(self):
        doc = Entry(doctype="POS Opening Entry", custom_pos_business_date="2026-11-18", pos_cashier_shift="shift")
        with patch.object(frappe, "db", MagicMock()) as db:
            set_business_date(doc)
        db.get_value.assert_not_called()
        self.assertEqual(doc.custom_pos_business_date, "2026-11-18")
