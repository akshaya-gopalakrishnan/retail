"""Preserve app bundle mappings in Docker images after a selective build."""

import fcntl
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

IMAGE_MANIFEST_DIRECTORY = ".retail-image-assets"


def clear_runtime_asset_cache(bench):
	"""Invalidate Frappe's bench-wide mappings even before a site is selected."""
	import frappe
	from redis import Redis

	configuration = frappe.get_common_site_config(str(Path(bench) / "sites"))
	url = os.environ.get("FRAPPE_REDIS_CACHE") or configuration.get("redis_cache")
	if not url:
		return  # First provisioning starts before common_site_config is written.
	# Do not start serving pages with an earlier image's cached bundle hashes.
	with Redis.from_url(url, socket_connect_timeout=5, socket_timeout=5) as cache:
		cache.delete("assets_json")


def clean_rtl_manifest(data):
	"""RTL is merged last by Frappe; unprefixed keys can shadow LTR/JS."""
	return {key: value for key, value in data.items() if key.startswith("rtl_")}


def repair(assets):
	assets = Path(assets)
	for filename, folders, prefix in (
		("assets.json", ("css", "js"), ""),
		("assets-rtl.json", ("css-rtl",), "rtl_"),
	):
		manifest = assets / filename
		data = json.loads(manifest.read_text()) if manifest.exists() else {}
		if prefix:
			data = clean_rtl_manifest(data)
		candidates = {}
		for app in ("retail", "hrms"):
			for folder in folders:
				for path in sorted((assets / app / "dist" / folder).glob("*")):
					match = re.fullmatch(r"(.+\.bundle)\.[^.]+\.(css|js)", path.name)
					if match:
						key = prefix + match.group(1) + "." + match.group(2)
						candidates.setdefault(key, []).append(
							"/assets/" + path.relative_to(assets).as_posix()
						)
		for key, paths in candidates.items():
			# esbuild knows which hash it just built. Never replace that mapping
			# with a lexicographically later file left over from a previous build.
			current = data.get(key)
			if current in paths:
				continue
			if len(paths) != 1:
				raise RuntimeError(f"Ambiguous bundle mapping for {key}; rebuild clean app assets")
			data[key] = paths[0]
		manifest.write_text(json.dumps(data, indent=2) + "\n")
	data = json.loads((assets / "assets.json").read_text())
	for key in ("retail_desk.bundle.css", "retail_desk.bundle.js"):
		if key not in data or not (assets / data[key].removeprefix("/assets/")).is_file():
			raise RuntimeError(f"Missing required bundle: {key}")


def snapshot(bench):
	"""Bake the same core/app mappings for every new container and site volume."""
	bench = Path(bench)
	destination = bench / IMAGE_MANIFEST_DIRECTORY
	destination.mkdir(exist_ok=True)
	baked = bench / "assets"
	for filename in ("assets.json", "assets-rtl.json"):
		path = bench / "sites/assets" / filename
		data = {}
		if (baked / filename).is_file():
			data.update(json.loads((baked / filename).read_text()))
		data.update(json.loads(path.read_text()))
		if filename == "assets-rtl.json":
			data = clean_rtl_manifest(data)
		content = json.dumps(data, indent=2) + "\n"
		(destination / filename).write_text(content)
		path.write_text(content)
		if baked.is_dir():
			(baked / filename).write_text(content)


def install(bench=None):
	"""Refresh mounted assets after migration in repository-built Docker images."""
	if bench is None:
		import frappe

		bench = Path(frappe.get_app_path("retail")).parents[2]
	bench = Path(bench)
	source = bench / IMAGE_MANIFEST_DIRECTORY
	if not source.is_dir():
		return False  # Ordinary development benches do not use image snapshots.
	sites = bench / "sites"
	sites.mkdir(parents=True, exist_ok=True)
	# Lock outside assets: an older image may have made assets a shared symlink.
	with (sites / ".retail-manifest.lock").open("a") as lock:
		fcntl.flock(lock, fcntl.LOCK_EX)
		assets = sites / "assets"
		if assets.is_symlink():
			previous = assets.resolve()
			copied = Path(tempfile.mkdtemp(dir=sites, prefix=".retail-assets-"))
			if previous.is_dir():
				shutil.copytree(previous, copied, dirs_exist_ok=True, symlinks=True)
			copied.chmod(0o775)
			assets.unlink()
			copied.replace(assets)
		assets.mkdir(parents=True, exist_ok=True)
		return _install_image_assets(bench, source, assets)


def _install_image_assets(bench, source, assets):
	for app in ("frappe", "erpnext", "retail", "hrms"):
		public = bench / "apps" / app / app / "public"
		if not public.is_dir():
			continue
		destination = assets / app
		if destination.is_symlink() and destination.resolve() != public.resolve():
			destination.unlink()
			destination.symlink_to(public, target_is_directory=True)
		elif not destination.exists():
			destination.symlink_to(public, target_is_directory=True)
		elif destination.resolve() != public.resolve():
			# Some deployments keep public assets as directories in the volume.
			# Preserve older hashed files for browsers with an earlier page open.
			shutil.copytree(public, destination, dirs_exist_ok=True)
	for filename in ("assets.json", "assets-rtl.json"):
		path = assets / filename
		data = json.loads(path.read_text()) if path.exists() else {}
		data.update(json.loads((source / filename).read_text()))
		if filename == "assets-rtl.json":
			data = clean_rtl_manifest(data)
		with tempfile.NamedTemporaryFile(
			mode="w", dir=path.parent, prefix=path.name + ".", delete=False
		) as handle:
			handle.write(json.dumps(data, indent=2) + "\n")
			handle.flush()
			temporary = Path(handle.name)
		temporary.chmod(0o644)
		temporary.replace(path)
	# Snapshot mappings choose the build's hashes, rather than an arbitrary
	# old file that may still exist in the persistent volume.
	data = json.loads((assets / "assets.json").read_text())
	for key in ("retail_desk.bundle.css", "retail_desk.bundle.js"):
		if key not in data or not (assets / data[key].removeprefix("/assets/")).is_file():
			raise RuntimeError(f"Missing deployed bundle: {key}")
	if bench is not None:
		import frappe

		if getattr(frappe.local, "site", None):
			from frappe.cache_manager import clear_global_cache

			clear_global_cache()
		else:
			clear_runtime_asset_cache(bench)
	return True


if __name__ == "__main__":
	import argparse

	parser = argparse.ArgumentParser()
	parser.add_argument("--install-runtime", action="store_true")
	args = parser.parse_args()
	bench = Path.cwd()
	if args.install_runtime:
		if not install(bench):
			raise RuntimeError("Retail image asset snapshot missing; rebuild with the tracked Containerfile")
	else:
		repair(bench / "sites/assets")
		snapshot(bench)
