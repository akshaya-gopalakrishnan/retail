"""Regression checks for deployment mistakes seen during INAYA provisioning."""

import argparse
import base64
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from retail import deployment_setup
from retail.deployment_setup import validate_license, validate_site

spec = importlib.util.spec_from_file_location(
	"retail_deployment_manager", Path(__file__).resolve().parents[2] / "deployment/docker/manage.py"
)
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)


class TestDeploymentSetup(unittest.TestCase):
	def test_license_directory_uses_numeric_service_group_and_preserves_state(self):
		with tempfile.TemporaryDirectory() as folder:
			root = Path(folder)
			state_directory = root / "inaya.example.com"
			state_directory.mkdir()
			state = state_directory / "license-state.json"
			state.write_text("existing rollback floors")
			with (
				patch.object(deployment_setup, "Path", return_value=root),
				patch.object(
					deployment_setup.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=1000, pw_gid=0)
				),
				patch.object(deployment_setup.os, "chown") as chown,
			):
				deployment_setup.prepare_state("inaya.example.com")
			chown.assert_called_once_with(state_directory, 1000, 0)
			self.assertEqual(state_directory.stat().st_mode & 0o777, 0o700)
			self.assertEqual(state.read_text(), "existing rollback floors")

	def test_foreign_shell_settings_cannot_choose_image_password_or_project(self):
		with patch.dict(
			os.environ,
			{
				"CUSTOM_IMAGE": "celesta-license",
				"CUSTOM_TAG": "old",
				"DB_ROOT_PASSWORD": "wrong",
				"COMPOSE_FILE": "foreign.yml",
				"COMPOSE_ENV_FILES": "foreign.env",
				"COMPOSE_PROJECT_NAME": "retail-staging",
				"RETAIL_ADMIN_PASSWORD": "wrong",
			},
		):
			result = manager.clean_environment()
		for key in (
			"CUSTOM_IMAGE",
			"CUSTOM_TAG",
			"DB_ROOT_PASSWORD",
			"COMPOSE_FILE",
			"COMPOSE_ENV_FILES",
			"COMPOSE_PROJECT_NAME",
			"RETAIL_ADMIN_PASSWORD",
		):
			self.assertNotIn(key, result)

	def test_production_config_is_scoped_and_runtime_has_no_database_root_secret(self):
		config = manager.compose_config("sha256:candidate", "inaya.example.com", 8084)
		for name, service in config["services"].items():
			if name not in ("db", "redis-cache", "redis-queue"):
				self.assertEqual(service["image"], "sha256:candidate")
			if name not in ("db", "provisioner"):
				self.assertNotIn("secrets", service)
		self.assertEqual(config["services"]["frontend"]["ports"], ["127.0.0.1:8084:8080"])
		for volume in config["volumes"].values():
			self.assertFalse(volume.get("external"))
			self.assertNotIn("name", volume)

	def test_trust_configuration_must_be_explicit_and_valid(self):
		key = base64.b64encode(bytes(32)).decode()
		self.assertEqual(
			validate_license("https://license.example.com/", [key]), ("https://license.example.com", [key])
		)
		for origin, keys in (
			("http://license.example.com", [key]),
			("https://license.example.com/path", [key]),
			("https://user:secret@license.example.com", [key]),
			("https://license.example.com", []),
			("https://license.example.com", ["invalid"]),
		):
			with self.subTest(origin=origin), self.assertRaises(ValueError):
				validate_license(origin, keys)
		with self.assertRaises(ValueError):
			validate_site("../retail-staging")

	def test_initialization_never_overwrites_existing_configuration(self):
		with tempfile.TemporaryDirectory() as folder:
			directory = Path(folder)
			original = directory / "deployment.json"
			original.write_text("existing")
			args = argparse.Namespace(
				site="inaya.example.com",
				license_origin="https://license.example.com",
				public_key=[base64.b64encode(bytes(32)).decode()],
				project="retail-production",
				port=8084,
				image="candidate",
			)
			with self.assertRaisesRegex(ValueError, "empty deployment directory"):
				manager.initialize(directory, args)
			self.assertEqual(original.read_text(), "existing")

	def test_wrong_image_is_rejected_before_any_secret_is_generated(self):
		with tempfile.TemporaryDirectory() as folder:
			directory = Path(folder) / "production"
			args = argparse.Namespace(
				site="inaya.example.com",
				license_origin="https://license.example.com",
				public_key=[base64.b64encode(bytes(32)).decode()],
				project="retail-production",
				port=8084,
				image="celesta-license:old",
			)
			with patch.object(
				manager.subprocess,
				"check_output",
				return_value=json.dumps([{"Id": "sha256:wrong", "Config": {"Labels": {}}}]),
			):
				with self.assertRaisesRegex(ValueError, "tracked Containerfile"):
					manager.initialize(directory, args)
			self.assertFalse(directory.exists())

	def test_secret_is_readable_in_containers_but_protected_by_private_host_directories(self):
		with tempfile.TemporaryDirectory() as folder:
			directory = Path(folder) / "production"
			args = argparse.Namespace(
				site="first.example.com",
				license_origin="https://license.example.com",
				public_key=[base64.b64encode(bytes(32)).decode()],
				project="retail-production",
				port=8084,
				image="candidate",
			)
			with patch.object(
				manager.subprocess,
				"check_output",
				side_effect=[
					json.dumps(
						[{"Id": "sha256:verified", "Config": {"Labels": {"it.celestial.retail.image": "1"}}}]
					),
					"",
				],
			):
				manager.initialize(directory, args)
			self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
			self.assertEqual((directory / "secrets").stat().st_mode & 0o777, 0o700)
			self.assertEqual((directory / "secrets/db-root-password").stat().st_mode & 0o777, 0o444)
			config = json.loads((directory / "compose.json").read_text())
			self.assertEqual(config["services"]["backend"]["image"], "sha256:verified")
			self.assertNotIn("MYSQL_ROOT_PASSWORD", config["services"]["db"]["environment"])

	def test_additional_customer_uses_its_own_site_without_reinitializing_stack(self):
		with tempfile.TemporaryDirectory() as folder:
			directory = Path(folder)
			config = {
				"project": "retail-production",
				"site": "first.example.com",
				"sites": ["first.example.com"],
				"license_origin": "https://license.example.com",
				"public_keys": [base64.b64encode(bytes(32)).decode()],
			}
			(directory / "deployment.json").write_text(json.dumps(config))
			with (
				patch.object(
					manager.sys,
					"argv",
					["manage.py", "create-site", "--directory", folder, "--site", "second.example.com"],
				),
				patch.object(manager.getpass, "getpass", side_effect=["admin-password", "admin-password"]),
				patch.object(manager.subprocess, "run") as runner,
			):
				manager.main()
			commands = [call.args[0] for call in runner.call_args_list]
			targets = [command[command.index("--site") + 1] for command in commands if "--site" in command]
			self.assertEqual(targets, ["second.example.com"] * 4)
			updated = json.loads((directory / "deployment.json").read_text())
			self.assertEqual(updated["sites"], ["first.example.com", "second.example.com"])
			self.assertEqual(updated["site"], "first.example.com")
