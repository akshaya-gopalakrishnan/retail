import json
import tempfile
import unittest
from pathlib import Path

from retail.build_image_assets import image_build_configuration


class TestImageBuildConfiguration(unittest.TestCase):
	def test_missing_key_and_existing_port_are_preserved_after_build(self):
		for config in ({}, {"socketio_port": 9100, "redis_cache": "redis://cache:6379"}):
			with self.subTest(config=config), tempfile.TemporaryDirectory() as folder:
				path = Path(folder) / "sites" / "common_site_config.json"
				path.parent.mkdir()
				original = json.dumps(config, indent=4).encode()
				path.write_bytes(original)
				with image_build_configuration(folder):
					self.assertEqual(json.loads(path.read_text()), {"socketio_port": 9000, **config})
				self.assertEqual(path.read_bytes(), original)

	def test_failure_restores_existing_or_absent_file(self):
		for original in (None, b'{"other": true}\n'):
			with self.subTest(original=original), tempfile.TemporaryDirectory() as folder:
				path = Path(folder) / "sites" / "common_site_config.json"
				path.parent.mkdir()
				if original is not None:
					path.write_bytes(original)
				with self.assertRaisesRegex(RuntimeError, "build failed"):
					with image_build_configuration(folder):
						self.assertEqual(json.loads(path.read_text())["socketio_port"], 9000)
						raise RuntimeError("build failed")
				self.assertEqual(path.read_bytes() if path.exists() else None, original)
