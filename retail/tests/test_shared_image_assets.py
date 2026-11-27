"""Regression coverage for overlapping old/new Docker frontends."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from retail.build_asset_manifest import IMAGE_MANIFEST_DIRECTORY, install, publish_shared_public


class SharedImageAssets(unittest.TestCase):
	def test_upgrade_and_rollback_preserve_both_images_assets(self):
		with tempfile.TemporaryDirectory() as folder:
			root = Path(folder)
			sites = root / "shared-sites"
			assets = sites / "assets"
			assets.mkdir(parents=True)
			benches = []
			for version in ("OLD", "NEW"):
				bench = root / version
				bench.mkdir()
				(bench / "sites").symlink_to(sites, target_is_directory=True)
				public = bench / "apps/retail/retail/public"
				mapping = {}
				for extension in ("css", "js"):
					path = public / f"dist/{extension}/retail_desk.bundle.{version}.{extension}"
					path.parent.mkdir(parents=True, exist_ok=True)
					path.write_text(f"{version} {extension}")
					mapping[f"retail_desk.bundle.{extension}"] = "/assets/retail/" + path.relative_to(public).as_posix()
				(public / "logo.svg").write_text("logo")
				snapshot = bench / IMAGE_MANIFEST_DIRECTORY
				snapshot.mkdir()
				(snapshot / "assets.json").write_text(json.dumps(mapping))
				(snapshot / "assets-rtl.json").write_text("{}")
				benches.append(bench)
			# Existing installations link public assets into the private image.
			(assets / "retail").symlink_to(benches[0] / "apps/retail/retail/public")
			with patch("retail.build_asset_manifest.clear_runtime_asset_cache"):
				for bench in (benches[1], benches[0]):
					self.assertTrue(install(bench))
					mapping = json.loads((assets / "assets.json").read_text())
					version = bench.name
					self.assertIn(version, mapping["retail_desk.bundle.css"])
					for released in ("OLD", "NEW"):
						for extension in ("css", "js"):
							self.assertTrue((assets / f"retail/dist/{extension}/retail_desk.bundle.{released}.{extension}").is_file())
			# Public files must remain available without either private image tree.
			for bench in benches:
				shutil.rmtree(bench / "apps")
			self.assertTrue((assets / "retail/logo.svg").is_file())
			self.assertTrue((assets / "retail/dist/css/retail_desk.bundle.NEW.css").is_file())
			self.assertTrue((assets / "retail/dist/js/retail_desk.bundle.OLD.js").is_file())

	def test_existing_directory_and_broken_private_link(self):
		for broken_link in (False, True):
			with self.subTest(broken_link=broken_link), tempfile.TemporaryDirectory() as folder:
				root = Path(folder)
				assets = root / "assets"
				assets.mkdir()
				public = root / "public"
				public.mkdir()
				(public / "new.css").write_text("new")
				if broken_link:
					(assets / "retail").symlink_to(root / "missing-image")
				else:
					(assets / "retail").mkdir()
					(assets / "retail/old.css").write_text("old")
				publish_shared_public(assets, "retail", public)
				self.assertEqual((assets / "retail/new.css").read_text(), "new")
				if not broken_link:
					self.assertEqual((assets / "retail/old.css").read_text(), "old")
