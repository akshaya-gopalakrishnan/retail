"""Database-free regressions for installation into an empty site."""

import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from retail import hooks, install


class TestInstallPortability(unittest.TestCase):
	def test_pos_schema_gate_detects_missing_fresh_install_fields(self):
		import frappe
		from retail.pos_sync_schema import validate

		db = Mock()
		db.has_column.side_effect = lambda dt, field: field != "custom_pos_completed_payload"
		with patch.object(frappe, "db", db):
			with self.assertRaisesRegex(RuntimeError, "POS Invoice.custom_pos_completed_payload"):
				validate()
			db.has_column.side_effect = None
			db.has_column.return_value = True
			self.assertEqual(validate(), {"pos_posting_schema": "OK"})

	def test_pos_posting_schema_is_ensured_on_install_and_migration(self):
		from retail import pos_sync_schema

		self.assertIn("retail.pos_sync_schema.install", hooks.after_sync)
		self.assertIn("retail.pos_sync_schema.install", hooks.after_migrate)
		with patch.object(pos_sync_schema, "create_custom_fields") as create:
			pos_sync_schema.install()
		definitions = {}
		for call in create.call_args_list:
			definitions.update(call.args[0])
		payload = definitions["POS Invoice"][0]
		self.assertEqual(payload["fieldname"], "custom_pos_completed_payload")
		self.assertEqual((payload["fieldtype"], payload["options"]), ("Code", "JSON"))
		self.assertTrue(payload["no_copy"])
		for doctype in ("POS Cashier Shift", "POS Closing Entry", "POS Branch Day Closing"):
			fields = {field["fieldname"]: field for field in definitions[doctype]}
			for suffix in ("credit_sales", "credit_notes_issued", "credit_notes_redeemed",
			               "credit_notes_applied", "credit_notes_unresolved"):
				self.assertEqual(fields["pos_" + suffix]["fieldtype"], "Currency")
				self.assertTrue(fields["pos_" + suffix]["allow_on_submit"])
		self.assertIn("pos_settlement_totals", {
			field["fieldname"] for field in definitions["POS Branch Day Closing"]})

	def test_fixture_dependencies_are_prepared_before_install_setup(self):
		self.assertEqual(hooks.after_install, ["retail.install.prepare_fixture_doctypes"])
		self.assertIn("retail.delegated_access.install", hooks.after_sync)
		self.assertIn("retail.delegated_access.install", hooks.after_migrate)
		for setup in ("retail.loyalty_setup.install", "retail.pos_transaction_display.execute"):
			self.assertIn(setup, hooks.after_sync)
		self.assertLess(
			hooks.after_sync.index("retail.company_bill_format.ensure_company_bill_format_fields"),
			hooks.after_sync.index("retail.editable_print_formats.ensure_editable_print_formats"),
		)
		self.assertEqual(len(hooks.after_sync), len(set(hooks.after_sync)))

	def test_custom_doctypes_are_imported_before_link_fields(self):
		with (
			patch.object(install, "frappe") as frappe,
			patch.object(install, "import_doc") as importer,
			patch("retail.short_codes.install") as naming,
		):
			frappe.get_app_path.return_value = "/fixtures/doctype.json"
			install.prepare_fixture_doctypes()
			frappe.get_app_path.assert_called_once_with("retail", "fixtures", "doctype.json")
			importer.assert_called_once_with("/fixtures/doctype.json")
			naming.assert_called_once_with()

	def test_fixture_exports_do_not_override_installer_owned_numbering(self):
		root = Path(__file__).resolve().parents[1]
		fixtures = json.loads((root / "fixtures/property_setter.json").read_text())
		for fixture in fixtures:
			self.assertFalse(
				fixture.get("field_name") == "naming_series"
				and fixture.get("property") in ("options", "default"),
				fixture["name"],
			)
		filters = next(f for f in hooks.fixtures if isinstance(f, dict) and f.get("dt") == "Property Setter")
		excluded = filters["filters"][0][2]
		from retail.short_codes import PREFIXES

		for doctype in PREFIXES:
			for prop in ("options", "default"):
				self.assertIn(f"{doctype}-naming_series-{prop}", excluded)

	def test_custom_field_dependencies_exist_in_shipped_apps_or_doctype_fixtures(self):
		root = Path(__file__).resolve().parents[1]
		apps = root.parents[1]
		known = {d["name"] for d in json.loads((root / "fixtures/doctype.json").read_text())}
		for app in ("frappe", "erpnext", "hrms", "retail"):
			for path in (apps / app).glob("**/doctype/*/*.json"):
				record = json.loads(path.read_text())
				if isinstance(record, dict) and record.get("name"):
					known.add(record["name"])
		for field in json.loads((root / "fixtures/custom_field.json").read_text()):
			with self.subTest(field=field["name"]):
				self.assertIn(field["dt"], known)
				if field["fieldtype"] in ("Link", "Table", "Table MultiSelect"):
					self.assertIn(field["options"], known)

	def test_workspace_fixture_titles_do_not_shadow_shipped_routes(self):
		retail_path = Path(__file__).resolve().parents[1]
		apps_path = retail_path.parents[1]
		targets = {}
		for app in ("frappe", "erpnext", "hrms", "retail"):
			for kind in ("doctype", "page"):
				for path in (apps_path / app).glob(f"**/{kind}/*/*.json"):
					record = json.loads(path.read_text())
					if isinstance(record, dict) and record.get("name"):
						targets[record["name"].lower().replace(" ", "-")] = record["name"]
		for workspace in json.loads((retail_path / "fixtures/workspace.json").read_text()):
			title = workspace.get("title") or workspace["name"]
			with self.subTest(workspace=workspace["name"]):
				self.assertNotIn(title.lower().replace(" ", "-"), targets)
