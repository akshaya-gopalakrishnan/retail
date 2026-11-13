"""Root provisioning must leave assets writable by the later service user."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from retail import build_asset_manifest as manifest


class TestRuntimeAssetUser(unittest.TestCase):
	def test_root_drops_privileges_before_creating_shared_assets(self):
		order = Mock()
		with (
			patch.object(manifest.os, "geteuid", return_value=0),
			patch.object(manifest.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=1000, pw_gid=0)),
			patch.object(manifest.os, "setgroups", order.groups),
			patch.object(manifest.os, "setgid", order.gid),
			patch.object(manifest.os, "setuid", order.uid),
			patch.object(manifest, "install", order.install),
		):
			manifest.install_runtime("bench")
		self.assertEqual(
			[(call[0], call.args) for call in order.mock_calls],
			[("groups", ([0],)), ("gid", (0,)), ("uid", (1000,)), ("install", ("bench",))],
		)

	def test_service_user_needs_no_privilege_change(self):
		with (
			patch.object(manifest.os, "geteuid", return_value=1000),
			patch.object(manifest.pwd, "getpwnam") as lookup,
			patch.object(manifest, "install", return_value=True) as install,
		):
			manifest.install_runtime("bench")
		lookup.assert_not_called()
		install.assert_called_once_with("bench")

	def test_privilege_failure_stops_before_writing_assets(self):
		with (
			patch.object(manifest.os, "geteuid", return_value=0),
			patch.object(manifest.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=1000, pw_gid=0)),
			patch.object(manifest.os, "setgroups", side_effect=PermissionError),
			patch.object(manifest, "install") as install,
		):
			with self.assertRaises(PermissionError):
				manifest.install_runtime("bench")
		install.assert_not_called()

	def test_missing_snapshot_remains_an_error(self):
		with (
			patch.object(manifest.os, "geteuid", return_value=1000),
			patch.object(manifest, "install", return_value=False),
		):
			with self.assertRaisesRegex(RuntimeError, "snapshot missing"):
				manifest.install_runtime("bench")
