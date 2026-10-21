"""Build image assets with HRMS's required compile-time socket configuration."""

import json
import subprocess
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def image_build_configuration(bench):
	"""Supply a missing compile-time default; restore the original file exactly."""
	path = Path(bench) / "sites" / "common_site_config.json"
	original = path.read_bytes() if path.exists() else None
	configuration = json.loads(original) if original is not None else {}
	configuration.setdefault("socketio_port", 9000)
	try:
		path.write_text(json.dumps(configuration) + "\n")
		yield
	finally:
		if original is None:
			path.unlink(missing_ok=True)
		else:
			path.write_bytes(original)


def build(bench):
	with image_build_configuration(bench):
		subprocess.run(
			["bench", "build", "--production", "--apps", "hrms,retail"],
			cwd=bench,
			check=True,
		)


if __name__ == "__main__":
	build(Path.cwd())
