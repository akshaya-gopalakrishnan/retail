import unittest
from datetime import datetime
from unittest.mock import Mock, patch

import frappe
from retail.retail_app.doctype.van_session import van_session


class TestVanSessionClosing(unittest.TestCase):
	def setUp(self):
		translation = patch.object(van_session, "_", side_effect=lambda text: text)
		translation.start()
		self.addCleanup(translation.stop)
		throw = patch.object(frappe, "throw", side_effect=lambda message: self.fail_validation(message))
		throw.start()
		self.addCleanup(throw.stop)

	@staticmethod
	def fail_validation(message):
		raise frappe.ValidationError(message)

	def session(self, previous=None, **values):
		# Closing validation only needs document fields; do not connect to a site.
		doc = object.__new__(van_session.VanSession)
		doc.__dict__.update(
			doctype="Van Session",
			name="SESSION-TEST",
			__islocal=1 if previous is None else 0,
			status="Open",
			opening_cash=0,
			opening_km=100,
			closing_cash=None,
			closing_km=None,
			close_time=None,
			_doc_before_save=previous,
		)
		doc.__dict__.update(values)
		return doc

	def test_new_open_session_accepts_empty_or_zero_numeric_defaults(self):
		for value in (None, "", 0, 0.0, "0", "0.00"):
			with self.subTest(value=value):
				self.session(closing_cash=value, closing_km=value).validate_closing_updates()

	def test_new_open_session_rejects_nonzero_closing_values(self):
		for fieldname in ("closing_cash", "closing_km"):
			for value in (1, -1, 0.25):
				with self.subTest(field=fieldname, value=value):
					with self.assertRaisesRegex(frappe.ValidationError, "can only be set"):
						self.session(**{fieldname: value}).validate_closing_updates()

	def test_saved_numeric_defaults_match_unsaved_blank_values(self):
		for old_value, new_value in ((0, None), (None, 0), (0, ""), ("", 0), (0.0, "0.00")):
			for docstatus in (0, 1):
				with self.subTest(old=old_value, new=new_value, docstatus=docstatus):
					previous = self.session(closing_cash=old_value, closing_km=old_value)
					self.session(
						previous=previous,
						docstatus=docstatus,
						closing_cash=new_value,
						closing_km=new_value,
					).validate_closing_updates()

	def test_frappe_serialization_of_blank_numeric_fields_does_not_block_submission(self):
		fields = {
			"closing_cash": frappe._dict(fieldtype="Currency"),
			"closing_km": frappe._dict(fieldtype="Float"),
		}
		doc = self.session()
		doc.meta = Mock()
		doc.meta.get_valid_columns.return_value = list(fields)
		doc.meta.get_field.side_effect = fields.get
		saved_values = doc.get_valid_dict()
		self.assertEqual(saved_values, {"closing_cash": 0.0, "closing_km": 0.0})
		doc.__dict__.update(__islocal=0, docstatus=1, _doc_before_save=self.session(**saved_values))
		doc.validate_closing_updates()

	def test_open_session_rejects_actual_numeric_changes(self):
		for fieldname in ("closing_cash", "closing_km"):
			for old_value, new_value in ((0, 1), (None, 0.25), (10, 11), (10, 0), (10, None)):
				with self.subTest(field=fieldname, old=old_value, new=new_value):
					previous = self.session(**{fieldname: old_value})
					with self.assertRaisesRegex(frappe.ValidationError, "can only be changed"):
						self.session(previous=previous, **{fieldname: new_value}).validate_closing_updates()

	def test_existing_unchanged_numeric_values_remain_unchanged(self):
		previous = self.session(closing_cash=10.0, closing_km=150.0)
		self.session(previous=previous, closing_cash="10.00", closing_km=150).validate_closing_updates()

	def test_open_session_rejects_setting_or_changing_close_time(self):
		timestamp = datetime(2026, 9, 10, 12)
		with self.assertRaisesRegex(frappe.ValidationError, "Close Time can only be set"):
			self.session(close_time=timestamp).validate_closing_updates()
		for old_value, new_value in ((None, timestamp), (str(timestamp), None), (timestamp, datetime(2026, 9, 10, 13))):
			with self.subTest(old=old_value, new=new_value):
				previous = self.session(close_time=old_value)
				with self.assertRaisesRegex(frappe.ValidationError, "Close Time can only be changed"):
					self.session(previous=previous, close_time=new_value).validate_closing_updates()

	def test_existing_close_time_keeps_frappe_datetime_comparison(self):
		previous = self.session(close_time=datetime(2026, 9, 10, 12))
		self.session(previous=previous, close_time="2026-09-10 12:00:00").validate_closing_updates()

	def test_closed_session_requires_closing_cash(self):
		for value in (None, ""):
			with self.subTest(value=value), self.assertRaisesRegex(frappe.ValidationError, "Closing Cash is required"):
				self.session(status="Closed", closing_cash=value).validate_closing_values()

	def test_closing_session_allows_zero_cash_and_valid_closing_values(self):
		for cash in (0, 25):
			with self.subTest(cash=cash):
				doc = self.session(previous=self.session(), status="Closed", closing_cash=cash, closing_km=125)
				doc.validate_closing_values()
				doc.validate_closing_updates()

	def test_closing_still_rejects_negative_cash_or_backwards_distance(self):
		for values, message in (
			({"closing_cash": -1, "closing_km": 125}, "Closing Cash cannot be negative"),
			({"closing_cash": 0, "closing_km": 99}, "Closing KM cannot be less than Opening KM"),
		):
			with self.subTest(values=values), self.assertRaisesRegex(frappe.ValidationError, message):
				self.session(status="Closed", **values).validate_closing_values()


if __name__ == "__main__":
	unittest.main()
