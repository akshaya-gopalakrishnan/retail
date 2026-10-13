#!/usr/bin/env python3
"""Create and operate an isolated Retail Docker deployment without shell env drift."""

import argparse
import getpass
import json
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from retail.deployment_setup import validate_license, validate_site


def clean_environment():
	return {
		key: value
		for key, value in os.environ.items()
		if not (
			key.startswith("COMPOSE_")
			or key.startswith("RETAIL_")
			or key
			in {
				"CUSTOM_IMAGE",
				"CUSTOM_TAG",
				"DB_ROOT_PASSWORD",
				"ADMIN_PASSWORD",
				"SITE_NAME",
				"HTTP_PORT",
			}
		)
	}


def compose_config(image, site, port):
	"""All names are project-scoped; runtime services never receive DB root secrets."""
	volumes = [
		"sites:/home/frappe/frappe-bench/sites",
		"logs:/home/frappe/frappe-bench/logs",
		"license-state:/var/lib/celesta",
	]
	logging = {"driver": "json-file", "options": {"max-size": "10m", "max-file": "3"}}

	def app(command, **extra):
		return {
			"image": image,
			"pull_policy": "never",
			"restart": "unless-stopped",
			"working_dir": "/home/frappe/frappe-bench",
			"volumes": volumes,
			"command": ["./env/bin/python", "-m", "retail.deployment_setup", "run", "--", *command],
			"logging": logging,
			**extra,
		}

	services = {
		"db": {
			"image": "mariadb:10.6",
			"restart": "unless-stopped",
			"environment": {"MYSQL_ROOT_PASSWORD_FILE": "/run/secrets/db_root_password"},
			"secrets": ["db_root_password"],
			"volumes": ["db-data:/var/lib/mysql"],
			"command": [
				"--character-set-server=utf8mb4",
				"--collation-server=utf8mb4_unicode_ci",
				"--skip-character-set-client-handshake",
				"--skip-innodb-read-only-compressed",
			],
			"healthcheck": {
				"test": ["CMD", "mysqladmin", "ping", "-h", "localhost"],
				"interval": "5s",
				"timeout": "5s",
				"retries": 30,
			},
			"logging": logging,
		},
		"redis-cache": {"image": "redis:7-alpine", "restart": "unless-stopped", "logging": logging},
		"redis-queue": {
			"image": "redis:7-alpine",
			"restart": "unless-stopped",
			"logging": logging,
			"command": ["redis-server", "--appendonly", "yes"],
			"volumes": ["redis-queue-data:/data"],
		},
	}
	ready = {
		"db": {"condition": "service_healthy"},
		"redis-cache": {"condition": "service_started"},
		"redis-queue": {"condition": "service_started"},
	}
	services["provisioner"] = app(
		["true"],
		profiles=["tools"],
		restart="no",
		secrets=["db_root_password"],
		depends_on=ready,
	)
	services["backend"] = app(
		[
			"./env/bin/gunicorn",
			"--chdir=/home/frappe/frappe-bench/sites",
			"--bind=0.0.0.0:8000",
			"--threads=4",
			"--workers=2",
			"--worker-class=gthread",
			"--worker-tmp-dir=/dev/shm",
			"--timeout=120",
			"frappe.app:application",
		],
		depends_on=ready,
	)
	services["websocket"] = app(
		["node", "/home/frappe/frappe-bench/apps/frappe/socketio.js"], depends_on=ready
	)
	services["queue-short"] = app(["bench", "worker", "--queue", "short,default"], depends_on=ready)
	services["queue-long"] = app(["bench", "worker", "--queue", "long"], depends_on=ready)
	services["scheduler"] = app(["bench", "schedule"], depends_on=ready)
	services["frontend"] = app(
		["nginx-entrypoint.sh"],
		depends_on=["backend", "websocket"],
		environment={
			"BACKEND": "backend:8000",
			"SOCKETIO": "websocket:9000",
			"FRAPPE_SITE_NAME_HEADER": "$$host",
			"UPSTREAM_REAL_IP_ADDRESS": "127.0.0.1",
			"UPSTREAM_REAL_IP_HEADER": "X-Forwarded-For",
			"UPSTREAM_REAL_IP_RECURSIVE": "off",
			"PROXY_READ_TIMEOUT": "120",
			"CLIENT_MAX_BODY_SIZE": "50m",
		},
		ports=[f"127.0.0.1:{port}:8080"],
	)
	return {
		"services": services,
		"volumes": {
			name: {}
			for name in (
				"db-data",
				"sites",
				"logs",
				"license-state",
				"redis-queue-data",
			)
		},
		"secrets": {"db_root_password": {"file": "./secrets/db-root-password"}},
	}


def initialize(directory, args):
	validate_site(args.site)
	origin, keys = validate_license(args.license_origin, args.public_key)
	if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", args.project):
		raise ValueError("Project must be a lowercase Compose project name")
	if not 1024 <= args.port <= 65535:
		raise ValueError("Choose a frontend port between 1024 and 65535")
	if directory.exists() and any(directory.iterdir()):
		raise ValueError(
			"Use an empty deployment directory; existing secrets/configuration are never replaced"
		)
	image = json.loads(
		subprocess.check_output(
			["docker", "image", "inspect", args.image],
			env=clean_environment(),
			text=True,
		)
	)[0]
	if image.get("Config", {}).get("Labels", {}).get("it.celestial.retail.image") != "1":
		raise ValueError("Build the image with Retail's tracked Containerfile before provisioning")
	existing = subprocess.check_output(
		[
			"docker",
			"volume",
			"ls",
			"-q",
			"--filter",
			f"label=com.docker.compose.project={args.project}",
		],
		env=clean_environment(),
		text=True,
	).strip()
	if existing:
		raise ValueError("Project already owns volumes; refusing to generate a new database password")
	directory.mkdir(parents=True, exist_ok=True)
	directory.chmod(0o700)
	(directory / "secrets").mkdir(mode=0o700)
	password = directory / "secrets/db-root-password"
	password.write_text(secrets.token_hex(32) + "\n")
	password.chmod(0o600)
	metadata = {
		"project": args.project,
		"site": args.site,
		"image": image["Id"],
		"port": args.port,
		"license_origin": origin,
		"public_keys": keys,
	}
	(directory / "deployment.json").write_text(json.dumps(metadata, indent=2) + "\n")
	(directory / "compose.json").write_text(
		json.dumps(compose_config(image["Id"], args.site, args.port), indent=2) + "\n"
	)
	print(f"Prepared {args.project} for {args.site}; image pinned to {image['Id']}")


def main():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("action", choices=("init", "create-site", "up", "migrate", "status"))
	parser.add_argument("--directory", type=Path, required=True)
	parser.add_argument("--image")
	parser.add_argument("--site")
	parser.add_argument("--project")
	parser.add_argument("--port", type=int, default=8084)
	parser.add_argument("--license-origin")
	parser.add_argument("--public-key", action="append", default=[])
	args = parser.parse_args()
	directory = args.directory.resolve()
	if args.action == "init":
		if not all((args.image, args.site, args.project, args.license_origin)):
			parser.error("init requires --image, --site, --project, --license-origin and --public-key")
		initialize(directory, args)
		return
	config = json.loads((directory / "deployment.json").read_text())
	# Generated JSON holds literal values. Shell exports and unrelated .env files
	# cannot redirect this operation to a different image, password or project.
	prefix = [
		"docker",
		"compose",
		"--project-directory",
		str(directory),
		"--env-file",
		"/dev/null",
		"-p",
		config["project"],
		"-f",
		str(directory / "compose.json"),
	]
	environment = clean_environment()

	def compose(*command, env=None):
		subprocess.run([*prefix, *command], env=env or environment, check=True)

	compose("config", "--quiet")
	if args.action == "create-site":
		admin = getpass.getpass("New site's Administrator password: ")
		if not admin or admin != getpass.getpass("Confirm Administrator password: "):
			raise ValueError("Passwords must be nonempty and match")
		compose("up", "-d", "db", "redis-cache", "redis-queue")
		compose(
			"run",
			"--rm",
			"--user",
			"root",
			"provisioner",
			"./env/bin/python",
			"-m",
			"retail.deployment_setup",
			"prepare-state",
			"--site",
			config["site"],
		)
		command = [
			"run",
			"--rm",
			"-T",
			"--user",
			"root",
			"-e",
			"RETAIL_ADMIN_PASSWORD",
			"provisioner",
			"./env/bin/python",
			"-m",
			"retail.deployment_setup",
			"create-site",
			"--site",
			config["site"],
			"--license-origin",
			config["license_origin"],
		]
		for key in config["public_keys"]:
			command += ["--public-key", key]
		compose(*command, env={**environment, "RETAIL_ADMIN_PASSWORD": admin})
		compose("run", "--rm", "-T", "provisioner", "bench", "--site", config["site"], "migrate")
		compose("run", "--rm", "-T", "provisioner", "bench", "--site", config["site"], "enable-scheduler")
	elif args.action == "migrate":
		compose("run", "--rm", "-T", "provisioner", "bench", "--site", config["site"], "migrate")
	elif args.action == "up":
		compose("up", "-d")
	else:
		compose("ps", "-a")


if __name__ == "__main__":
	try:
		main()
	except (ValueError, OSError, subprocess.CalledProcessError) as error:
		# Do not echo captured configuration or credentials on validation failure.
		raise SystemExit(f"Retail deployment stopped: {type(error).__name__}: {error}")
