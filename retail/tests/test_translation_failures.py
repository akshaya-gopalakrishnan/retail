import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import Mock, patch

import frappe
import requests
from frappe.query_builder.builder import MariaDB

from retail import document_codes
from retail.domains.item import arabic_name


class TestTranslationFailures(unittest.TestCase):
	def setUp(self):
		stack = ExitStack()
		self.addCleanup(stack.close)
		stack.enter_context(patch.object(frappe.local, "flags", frappe._dict(in_test=True), create=True))
		self.cache_values = {}
		self.cache = Mock()
		self.cache.get_value.side_effect = self.cache_values.get
		self.cache.set_value.side_effect = lambda key, value, **kw: self.cache_values.update({key: value})
		for name, value in (
			("cache", self.cache),
			("conf", frappe._dict(retail_translation_provider="google")),
			("session", frappe._dict(user="Administrator")),
		):
			stack.enter_context(patch.object(frappe, name, value))

	def test_rate_limit_preserves_saved_names_and_stops_batch_requests(self):
		response = requests.Response()
		response.status_code = 429
		response.headers["Retry-After"] = "120"
		rows = [
			{"packing_name": "Water", "arabic_packing_name": "ماء"},
			{"packing_name": "Water - Box x10"},
			{"packing_name": "Juice - Box x10"},
			{"packing_name": "Water - Box x10"},
		]
		with patch.object(requests, "get", return_value=response) as get, patch.object(
			frappe, "log_error", side_effect=frappe.UniqueValidationError("duplicate EL-214")
		), self.assertLogs(arabic_name.__name__, level="ERROR"):
			arabic_name.fill_arabic_packing_names(rows)
		self.assertEqual(rows[0]["arabic_packing_name"], "ماء")
		self.assertTrue(all(row["arabic_packing_name"] == "" for row in rows[1:]))
		get.assert_called_once()
		self.cache.set_value.assert_any_call(arabic_name.GOOGLE_COOLDOWN_KEY, True, expires_in_sec=120)

	def test_google_success_after_cooldown_expires(self):
		self.cache_values[arabic_name.GOOGLE_COOLDOWN_KEY] = True
		response = Mock(status_code=200)
		response.json.return_value = [[["ماء", "Water"]]]
		with patch.object(requests, "get", return_value=response) as get:
			self.assertTrue(arabic_name._translate_with_google("Water", 8)["error"])
			get.assert_not_called()
			del self.cache_values[arabic_name.GOOGLE_COOLDOWN_KEY]
			self.assertEqual(arabic_name._translate_with_google("Water", 8)["translated_text"], "ماء")

	def test_libretranslate_failure_survives_logging_failure(self):
		frappe.conf.update(retail_translation_provider="libretranslate", retail_translation_url="https://example.invalid")
		with patch.object(requests, "post", side_effect=requests.Timeout), patch.object(
			frappe, "log_error", side_effect=RuntimeError("queue unavailable")
		), self.assertLogs(arabic_name.__name__, level="ERROR"):
			self.assertTrue(arabic_name.translate_item_name_to_arabic("Water")["error"])

	def test_provider_failure_defers_error_log(self):
		with patch.object(requests, "get", side_effect=requests.Timeout), patch.object(frappe, "log_error") as log:
			self.assertTrue(arabic_name._translate_with_google("Water", 8)["error"])
		log.assert_called_once_with(title="Arabic Item Name Translation Failed", defer_insert=True)

	def test_retry_after_defaults_bounds_and_http_date(self):
		for value, expected in (("", 60), ("invalid", 60), ("-1", 60), ("900000", 86400)):
			with self.subTest(value=value):
				self.assertEqual(arabic_name._retry_after_seconds(Mock(headers={"Retry-After": value})), expected)
		future = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=180))
		self.assertIn(arabic_name._retry_after_seconds(Mock(headers={"Retry-After": future})), (178, 179, 180))


class TestDocumentCodeRollback(unittest.TestCase):
	def test_existing_log_codes_are_not_reused_after_series_rollback(self):
		# Model MyISAM records surviving while the transactional counter resets.
		stored = {"EL-214", "EL-215"}
		db = Mock()
		db.exists.side_effect = lambda dt, filters: filters[document_codes.FIELD] in stored
		with patch.object(frappe, "db", db), patch.object(document_codes, "getseries", side_effect=["214", "215", "216"]):
			self.assertEqual(document_codes.next_code("Error Log", "EL"), "EL-216")
		stored.add("EL-216")
		with patch.object(frappe, "db", db), patch.object(document_codes, "getseries", side_effect=["214", "215", "216", "217"]):
			self.assertEqual(document_codes.next_code("Error Log", "EL"), "EL-217")

	def test_backfill_skips_codes_already_held_by_logs(self):
		db = Mock()
		db.exists.side_effect = lambda dt, filters: filters[document_codes.FIELD] in {"EL-214", "EL-216"}
		query = Mock()
		query.select.return_value = query
		query.where.return_value = query
		query.limit.return_value = query
		query.orderby.return_value = query
		query.for_update.return_value = query
		query.run.side_effect = [[("log-a",)], [("log-a",), ("log-b",)]]
		with patch.object(frappe, "db", db), patch.object(frappe, "qb", MariaDB), patch.object(MariaDB, "from_", return_value=query), patch.object(
			document_codes, "getseries", side_effect=["214", "215", "216", "217"]
		):
			self.assertEqual(document_codes.backfill_type("Error Log"), 2)
		db.bulk_update.assert_called_once_with("Error Log", {
			"log-a": {document_codes.FIELD: "EL-215"},
			"log-b": {document_codes.FIELD: "EL-217"},
		}, update_modified=False, chunk_size=500)
