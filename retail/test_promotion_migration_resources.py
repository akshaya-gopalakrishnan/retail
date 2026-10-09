import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import frappe
from jinja2 import Environment, FileSystemLoader, meta

from retail.patches import sync_promotions_workspace as migration


class TestPromotionMigrationResources(unittest.TestCase):
	def test_patch_loads_bundled_documents_and_can_run_twice(self):
		"""Exercise the resource reads that previously stopped site upgrades."""
		records = {}

		def new_doc(doctype):
			doc = Mock()
			doc.data = {}
			doc.update.side_effect = doc.data.update
			doc.save.side_effect = lambda: records.__setitem__((doctype, doc.data["name"]), doc)
			return doc

		def exists(doctype, name):
			if doctype == "DocType":
				return name
			return name if (doctype, name) in records else None

		database = Mock()
		database.exists.side_effect = exists
		with (
			patch.object(frappe, "db", database),
			patch.object(frappe, "new_doc", side_effect=new_doc),
			patch.object(frappe, "get_doc", side_effect=lambda doctype, name: records[(doctype, name)]),
			patch.object(frappe, "clear_cache"),
		):
			migration.execute()
			first_documents = dict(records)
			migration.execute()

		self.assertEqual(set(records), {(doctype, name) for _, _, doctype, name in migration.DOCS})
		for key, doc in records.items():
			with self.subTest(document=key):
				self.assertIs(doc, first_documents[key])
				self.assertEqual(doc.save.call_count, 2)
				self.assertEqual(doc.data["doctype"], key[0])
				if key[0] == "Dashboard Chart":
					self.assertEqual(doc.data["is_standard"], 0)

	def test_print_formats_include_only_bundled_templates(self):
		"""A restored format must also carry any template it needs to print."""
		app_path = Path(migration.__file__).resolve().parents[2]
		environment = Environment(loader=FileSystemLoader(app_path))
		checked = set()

		def check_template(source):
			parsed = environment.parse(source)
			environment.from_string(source)
			for name in meta.find_referenced_templates(parsed):
				self.assertIsNotNone(name, "Print template dependencies must be resolvable at build time")
				if name in checked:
					continue
				checked.add(name)
				dependency, _, _ = environment.loader.get_source(environment, name)
				check_template(dependency)

		for folder, name, doctype, _ in migration.DOCS:
			if doctype != "Print Format":
				continue
			with self.subTest(print_format=name):
				path = app_path / "retail" / "retail_app" / folder / name / f"{name}.json"
				data = json.loads(path.read_text())
				self.assertTrue(data["html"].strip())
				check_template(data["html"])
