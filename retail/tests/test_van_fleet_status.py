from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from retail.retail_app.doctype.van_fleet.van_fleet import VanFleet


class TestVanFleetStatus(TestCase):
	def setUp(self):
		translation = patch("retail.retail_app.doctype.van_fleet.van_fleet._", side_effect=lambda text: text)
		translation.start()
		self.addCleanup(translation.stop)

	def test_unavailable_fleet_cannot_have_open_sessions(self):
		for status in ("Inactive", "Maintenance"):
			fleet = Mock(vehicle_status=status)
			fleet.is_new.return_value = False
			fleet._open_sessions.return_value = ["VSS-8", "VSS-9"]
			with self.subTest(status=status), patch.object(frappe, "throw") as fail, patch(
				"frappe.utils.get_link_to_form", side_effect=lambda doctype, name: name
			):
				VanFleet.validate(fleet)
				message = fail.call_args.args[0]
				self.assertIn("VSS-8", message)
				self.assertIn("VSS-9", message)
				self.assertIn(status, message)
				fleet.db_set.assert_not_called()

	def test_no_open_session_allows_unavailable_status(self):
		for status in ("Inactive", "Maintenance"):
			fleet = Mock(vehicle_status=status)
			fleet.is_new.return_value = False
			fleet._open_sessions.return_value = []
			with self.subTest(status=status), patch.object(frappe, "throw") as fail:
				VanFleet.validate(fleet)
				fail.assert_not_called()

	def test_active_or_new_fleet_needs_no_session_check(self):
		for status, is_new in (("Active", False), ("Maintenance", True)):
			fleet = Mock(vehicle_status=status)
			fleet.is_new.return_value = is_new
			VanFleet.validate(fleet)
			fleet._open_sessions.assert_not_called()

	def test_session_lookup_excludes_closed_and_cancelled_records(self):
		fleet = Mock()
		fleet.name = "RG1234"
		with patch.object(frappe, "get_all", return_value=["VSS-8"]) as query:
			self.assertEqual(VanFleet._open_sessions(fleet), ["VSS-8"])
		self.assertEqual(query.call_args.kwargs["filters"], {
			"van": "RG1234", "status": "Open", "docstatus": ["<", 2],
		})

	def test_popup_lookup_requires_write_access(self):
		fleet = Mock()
		fleet.check_permission.side_effect = frappe.PermissionError
		with self.assertRaises(frappe.PermissionError):
			VanFleet.get_open_sessions.__wrapped__(fleet)
		fleet.check_permission.assert_called_once_with("write")
		fleet._open_sessions.assert_not_called()
