"""Offline refresh regressions, without a database or central server."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import frappe
from retail.licensing import client
from retail.licensing import test_signature


class TestScheduledSync(unittest.TestCase):
    def test_network_failure_retains_token_and_success_stores_signed_denial(self):
        fixture = test_signature.TestSignature()
        fixture.setUp()
        doc = frappe._dict(installation_id="installation-1", verified_issued_at="1000")
        doc.get_password = Mock(return_value="secret")
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        config = {"celesta_license_state_path": str(Path(directory.name) / "state.json"),"celesta_license_public_keys": fixture.keys,
                  "celesta_license_server_url": "https://licenses.example.com"}
        with patch.object(frappe.local, "db", Mock(), create=True), \
                patch.object(frappe, "get_doc", return_value=doc), \
                patch.object(frappe, "conf", config), \
                patch.object(frappe, "logger", return_value=Mock()), \
                patch.object(client, "_alert_refresh_failure"), \
                patch.object(frappe, "throw", side_effect=frappe.ValidationError), \
                patch.object(client.time, "time", return_value=1001), \
                patch.object(client, "_local_time", side_effect=str), \
                patch.object(client.requests, "post") as post:
            post.side_effect = client.requests.ConnectionError("offline")
            self.assertEqual(client.scheduled_sync(), {"status": "unavailable"})
            self.assertEqual(frappe.logger.return_value.warning.call_args.args,
                             ("Scheduled license refresh failed; retained the previous signed license. %s", "Unexpected refresh failure."))
            frappe.db.set_single_value.assert_not_called()
            post.side_effect = None
            response = Mock(status_code=200, content=b"{}")
            post.return_value = response
            response.json.return_value = {"message": {"token": "tampered"}}
            self.assertEqual(client.scheduled_sync(), {"status": "unavailable"})
            self.assertEqual(frappe.logger.return_value.warning.call_args.args,
                             ("Scheduled license refresh failed; retained the previous signed license. %s", "Unexpected refresh failure."))
            frappe.db.set_single_value.assert_not_called()
            fixture.claims["rules"]["status"] = "Revoked"
            fixture.claims["exp"] = 1000
            response.json.return_value = {"message": {"token": fixture.token()}}
            self.assertEqual(client.scheduled_sync(), {"status": "Revoked"})
            values = frappe.db.set_single_value.call_args.args[1]
            self.assertEqual(values["verified_token"], fixture.token())
            self.assertEqual(values["status"], "Revoked")

    def test_hourly_hook_registration(self):
        from retail import hooks
        method = 'retail.licensing.client.scheduled_sync'
        self.assertEqual(hooks.scheduler_events['hourly'].count(method), 1)

    def test_safe_refresh_diagnostics_and_retained_settings(self):
        doc = frappe._dict(installation_id="installation-1", verified_issued_at="1000")
        doc.get_password = Mock(return_value="PRIVATE-KEY")
        def throw(message, exc=frappe.ValidationError):
            raise exc(message)
        config = {"celesta_license_server_url": "https://licenses.example.com",
                  "celesta_license_public_keys": ["test-public-key"]}
        wrong_site = Mock(status_code=417, content=b"{}")
        wrong_site.json.return_value = {"exception": "App celesta_license is not installed PRIVATE-KEY"}
        malformed = Mock(status_code=200, content=b"{}")
        malformed.json.side_effect = ValueError("PRIVATE-KEY")
        invalid = Mock(status_code=200, content=b"{}")
        invalid.json.return_value = {"message": {"token": "PRIVATE-TOKEN"}}
        cases = [(client.requests.Timeout("PRIVATE-KEY"), "timed out"),
                 (client.requests.ConnectionError("PRIVATE-KEY"), "Cannot connect securely"),
                 (wrong_site, "site without celesta_license"),
                 (Mock(status_code=403, content=b"PRIVATE-KEY"), "refused the request"),
                 (Mock(status_code=429, content=b"PRIVATE-KEY"), "rate limit"),
                 (Mock(status_code=302, content=b"PRIVATE-KEY"), "unsuccessful HTTP"),
                 (malformed, "did not return a signed"), (invalid, "failed validation")]
        with patch.object(frappe.local, "db", Mock(), create=True), \
                patch.object(frappe, "get_doc", return_value=doc), \
                patch.object(frappe, "conf", config), patch.object(frappe, "throw", side_effect=throw), \
                patch.object(client, "transition_context", return_value="CL-test"), \
                patch.object(client, "verify_protected", side_effect=ValueError("PRIVATE-TOKEN")), \
                patch.object(client.requests, "post") as post:
            for result, expected in cases:
                with self.subTest(expected=expected):
                    post.side_effect = result if isinstance(result, Exception) else None
                    post.return_value = result
                    with self.assertRaises(client.LicenseRefreshError) as raised:
                        client._sync("verify")
                    self.assertIn(expected, str(raised.exception))
                    self.assertNotIn("PRIVATE", str(raised.exception))
                    frappe.db.set_single_value.assert_not_called()

    def test_expiry_alert_uses_signed_deadline_and_deduplicates(self):
        fixture = test_signature.TestSignature()
        fixture.setUp()
        doc = frappe._dict(installation_id=fixture.claims["sub"], verified_token=fixture.token())
        alert = Mock()
        def get_doc(value):
            return doc if isinstance(value, str) else alert
        with patch.object(frappe.local, "db", Mock(), create=True), \
                patch.object(frappe, "get_doc", side_effect=get_doc), \
                patch.object(frappe, "conf", {"celesta_license_public_keys": fixture.keys}), \
                patch.object(frappe, "get_all", side_effect=[[], ["Administrator"]]), \
                patch.object(client.time, "time", return_value=fixture.claims["exp"] - 3600), \
                patch("frappe.utils.today", return_value="2026-10-09"):
            frappe.db.exists.return_value = False
            client._alert_refresh_failure()
            alert.insert.assert_called_once_with(ignore_permissions=True)
            alert.insert.reset_mock()
            frappe.get_all.side_effect = [[], ["Administrator"]]
            frappe.db.exists.return_value = True
            client._alert_refresh_failure()
            alert.insert.assert_not_called()
            frappe.db.exists.return_value = False
            frappe.get_all.side_effect = [[], ["Administrator"]]
            with patch.object(client.time, "time", return_value=fixture.claims["exp"] + 1):
                client._alert_refresh_failure()
            alert.insert.assert_called_once()
            alert.insert.reset_mock()
            with patch.object(client.time, "time", return_value=fixture.claims["exp"] - 7 * 3600):
                client._alert_refresh_failure()
            alert.insert.assert_not_called()
            doc.verified_token = "tampered"
            client._alert_refresh_failure()
            alert.insert.assert_not_called()
