import unittest
from types import SimpleNamespace
from unittest.mock import patch

from retail import report_print_formats as formats


class TestReportPrintFormats(unittest.TestCase):
	def setUp(self):
		translation = patch.object(formats, "_", lambda value: value)
		translation.start()
		self.addCleanup(translation.stop)

	def test_installer_preserves_existing_site_layout(self):
		with patch.object(formats, "frappe") as frappe:
			frappe.db.exists.return_value = True
			formats.ensure_report_print_formats()
			frappe.get_doc.assert_not_called()
			frappe.db.set_value.assert_not_called()

	def test_fresh_install_creates_a_report_editor_copy(self):
		for report_name, format_name in formats.REPORT_FORMATS.copy().items():
			with self.subTest(report_name=report_name), patch.object(formats, "frappe") as frappe, patch.dict(
				formats.REPORT_FORMATS, {report_name: format_name}, clear=True
			):
				frappe.db.exists.side_effect = lambda dt, name: dt == "Report"
				frappe.scrub.side_effect = lambda value: value.lower().replace(" ", "_")
				formats.ensure_report_print_formats()
				data = frappe.get_doc.call_args.args[0]
				self.assertEqual(data["name"], format_name)
				self.assertEqual(data["print_format_for"], "Report")
				self.assertEqual(data["report"], report_name)
				self.assertEqual(data["standard"], "No")
				self.assertEqual(data["print_format_type"], "JS")
				self.assertIn("settings.include_filters", data["html"])
				self.assertNotIn("<style>", data["css"])
				frappe.get_doc.return_value.insert.assert_called_once_with(ignore_permissions=True)

	def test_report_print_access_is_checked_before_reading_a_layout(self):
		with patch.object(formats, "frappe") as frappe, patch.object(formats, "get_report_doc") as get_report:
			get_report.return_value.ref_doctype = "Sales Invoice"
			frappe.has_permission.return_value = False
			frappe.throw.side_effect = PermissionError
			with self.assertRaises(PermissionError):
				formats.get_report_format.__wrapped__("Daily Sales Summary")
			frappe.get_doc.assert_not_called()

	def test_print_access_does_not_expose_another_report_or_disabled_format(self):
		for changes in ({"report": "General Ledger"}, {"disabled": 1}, {"print_format_type": "Jinja"}):
			with self.subTest(changes=changes), patch.object(formats, "frappe") as frappe, patch.object(formats, "get_report_doc"):
				frappe.has_permission.return_value = True
				frappe.throw.side_effect = PermissionError
				frappe.get_doc.return_value = SimpleNamespace(**{
					"disabled": 0, "print_format_for": "Report", "report": "Daily Sales Summary",
					"print_format_type": "JS", "raw_printing": 0, **changes,
				})
				with self.assertRaises(PermissionError):
					formats.get_report_format.__wrapped__("Daily Sales Summary", "Other format")

	def test_print_permission_allows_layout_without_editor_permission(self):
		with patch.object(formats, "frappe") as frappe, patch.object(formats, "get_report_doc"):
			frappe.has_permission.side_effect = lambda dt, permission: permission in ("read", "print")
			frappe.get_doc.return_value = SimpleNamespace(
				name="Daily Sales Summary - A4", disabled=0, print_format_for="Report",
				report="Daily Sales Summary", print_format_type="JS", raw_printing=0,
				html="<p>Company edited layout</p>", css="p {color: blue;}",
			)
			self.assertEqual(formats.get_report_format.__wrapped__("Daily Sales Summary")["html"], "<p>Company edited layout</p>")
