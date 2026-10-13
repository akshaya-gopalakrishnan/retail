"""Container-side setup used by Retail's repository-owned Docker deployment."""

import argparse
import base64
import json
import os
import pwd
import re
from pathlib import Path
from urllib.parse import urlsplit


def validate_site(site):
	if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*[a-z0-9]", site) or ".." in site:
		raise ValueError("Use a lowercase hostname for the site")
	return site


def validate_license(origin, public_keys):
	parsed = urlsplit(origin)
	if (
		parsed.scheme != "https"
		or not parsed.hostname
		or parsed.username
		or parsed.password
		or parsed.query
		or parsed.fragment
		or parsed.path not in ("", "/")
	):
		raise ValueError("License origin must be an HTTPS origin without credentials or a path")
	if not public_keys:
		raise ValueError("At least one trusted license public key is required")
	for key in public_keys:
		if len(base64.b64decode(key, validate=True)) != 32:
			raise ValueError("License public keys must encode 32 bytes")
	return origin.rstrip("/"), list(public_keys)


def prepare_state(site):
	"""Prepare a shared private directory without replacing existing state."""
	user = pwd.getpwnam("frappe")
	path = Path("/var/lib/celesta") / validate_site(site)
	path.mkdir(parents=True, exist_ok=True)
	if path.is_symlink():
		raise ValueError("License state directory cannot be a symlink")
	os.chown(path, user.pw_uid, user.pw_gid)
	path.chmod(0o700)


def create_site(site, origin, public_keys):
	# Compose's local secrets are bind-mounted files and may belong to a host UID
	# other than frappe. Read only the provisioning secret as root, then create
	# every site file as the bench service user.
	root_password = Path("/run/secrets/db_root_password").read_text().strip()
	if os.geteuid() == 0:
		service_user = pwd.getpwnam("frappe")
		os.setgroups([service_user.pw_gid])
		os.setgid(service_user.pw_gid)
		os.setuid(service_user.pw_uid)
	import frappe
	from frappe.installer import _new_site, update_site_config

	validate_site(site)
	origin, public_keys = validate_license(origin, public_keys)
	bench = Path("/home/frappe/frappe-bench")
	os.chdir(bench / "sites")
	if Path(site).exists():
		raise ValueError("Site already exists; use migrate or diagnose it, never overwrite it")
	password = os.environ.get("RETAIL_ADMIN_PASSWORD")
	if not password:
		raise ValueError("Administrator password is required")
	configuration = Path("common_site_config.json")
	common = json.loads(configuration.read_text()) if configuration.exists() else {}
	common.update(
		{
			"db_host": "db",
			"db_port": 3306,
			"redis_cache": "redis://redis-cache:6379",
			"redis_queue": "redis://redis-queue:6379",
			"redis_socketio": "redis://redis-queue:6379",
			"socketio_port": 9000,
		}
	)
	configuration.write_text(json.dumps(common, indent=2) + "\n")
	try:
		frappe.init(site=site, new_site=True)
		_new_site(
			db_name=None,
			site=site,
			db_root_username="root",
			db_root_password=root_password,
			admin_password=password,
			db_type="mariadb",
			db_host="db",
			mariadb_user_host_login_scope="%",
			install_apps=["erpnext", "hrms", "retail"],
		)
		update_site_config("celesta_license_server_url", origin)
		update_site_config("celesta_license_public_keys", public_keys)
		update_site_config("celesta_license_state_path", f"/var/lib/celesta/{site}/license-state.json")
		update_site_config("host_name", f"https://{site}")
	finally:
		frappe.destroy()


def main():
	parser = argparse.ArgumentParser()
	subparsers = parser.add_subparsers(dest="action", required=True)
	prepare = subparsers.add_parser("prepare-state")
	prepare.add_argument("--site", required=True)
	create = subparsers.add_parser("create-site")
	create.add_argument("--site", required=True)
	create.add_argument("--license-origin", required=True)
	create.add_argument("--public-key", action="append", required=True)
	run = subparsers.add_parser("run")
	run.add_argument("command", nargs=argparse.REMAINDER)
	args = parser.parse_args()
	if args.action == "prepare-state":
		prepare_state(args.site)
	elif args.action == "create-site":
		create_site(args.site, args.license_origin, args.public_key)
	else:
		from retail.build_asset_manifest import install

		install(Path("/home/frappe/frappe-bench"))
		command = args.command
		if command and command[0] == "--":
			command = command[1:]
		if not command:
			parser.error("run requires a command after --")
		os.execvp(command[0], command)


if __name__ == "__main__":
	main()
