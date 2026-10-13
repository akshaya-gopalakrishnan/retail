#!/usr/bin/env bash
# Exercise an image in a disposable, isolated Compose project before promotion.
set -Eeuo pipefail

validation_image=${1:?Usage: bash validate_fresh_install.sh IMAGE}
docker image inspect "$validation_image" >/dev/null
validation_directory=$(mktemp -d /tmp/retail-install-validation.XXXXXXXX)
validation_suffix=${validation_directory##*.}
validation_project="retail-install-check-${validation_suffix,,}"
export RETAIL_VALIDATION_IMAGE="$validation_image"
export RETAIL_VALIDATION_DIRECTORY="$validation_directory"
umask 077

python3 - <<'PY'
import json
import os
import secrets
from pathlib import Path

services = {
    "db": {
        "image": "mariadb:10.6",
        "environment": {"MYSQL_ROOT_PASSWORD": secrets.token_hex(32)},
        "command": ["--character-set-server=utf8mb4", "--collation-server=utf8mb4_unicode_ci"],
        "volumes": ["db-data:/var/lib/mysql"],
        "healthcheck": {
            "test": ["CMD-SHELL", 'mysqladmin ping -h localhost -p"$${MYSQL_ROOT_PASSWORD}"'],
            "interval": "5s", "timeout": "5s", "retries": 30,
        },
    },
    "redis-cache": {"image": "redis:7-alpine"},
    "redis-queue": {"image": "redis:7-alpine"},
}
services["checker"] = {
    "image": os.environ["RETAIL_VALIDATION_IMAGE"],
    "pull_policy": "never",
    "working_dir": "/home/frappe/frappe-bench",
    "volumes": ["sites:/home/frappe/frappe-bench/sites", "logs:/home/frappe/frappe-bench/logs"],
    "environment": {
        "VALIDATION_DB_PASSWORD": services["db"]["environment"]["MYSQL_ROOT_PASSWORD"],
        "VALIDATION_ADMIN_PASSWORD": secrets.token_hex(32),
    },
    "depends_on": {
        "db": {"condition": "service_healthy"},
        "redis-cache": {"condition": "service_started"},
        "redis-queue": {"condition": "service_started"},
    },
}
services["backend"] = {
    "image": os.environ["RETAIL_VALIDATION_IMAGE"], "pull_policy": "never",
    "volumes": services["checker"]["volumes"],
    "command": ["./env/bin/python", "-m", "retail.deployment_setup", "run", "--",
                "./env/bin/gunicorn", "--chdir=/home/frappe/frappe-bench/sites",
                "--bind=0.0.0.0:8000", "--workers=1", "--threads=4", "--worker-class=gthread",
                "frappe.app:application"],
}
services["websocket"] = {
    "image": os.environ["RETAIL_VALIDATION_IMAGE"], "pull_policy": "never",
    "volumes": services["checker"]["volumes"],
    "command": ["node", "/home/frappe/frappe-bench/apps/frappe/socketio.js"],
}
services["frontend"] = {
    "image": os.environ["RETAIL_VALIDATION_IMAGE"], "pull_policy": "never",
    "volumes": services["checker"]["volumes"], "command": ["nginx-entrypoint.sh"],
    "environment": {"BACKEND": "backend:8000", "SOCKETIO": "websocket:9000",
                    "FRAPPE_SITE_NAME_HEADER": "retail-test.localhost",
                    "UPSTREAM_REAL_IP_ADDRESS": "127.0.0.1",
                    "UPSTREAM_REAL_IP_HEADER": "X-Forwarded-For", "UPSTREAM_REAL_IP_RECURSIVE": "off"},
    "depends_on": ["backend", "websocket"],
}
config = {"services": services, "volumes": {name: {} for name in ("db-data", "sites", "logs")}}
Path(os.environ["RETAIL_VALIDATION_DIRECTORY"], "compose.json").write_text(json.dumps(config))
PY

validation_compose() {
    docker compose --project-directory "$validation_directory" \
        -p "$validation_project" -f "$validation_directory/compose.json" "$@"
}

validation_failed() {
    echo "Validation failed. Production was not changed."
    echo "Retained test project: $validation_project"
    echo "Configuration: $validation_directory/compose.json (contains disposable test passwords)"
}
trap validation_failed ERR

validation_compose run --rm checker bash -lc '
    set -e
    ./env/bin/python -m unittest retail.tests.test_install_portability \
        retail.tests.test_deployment_setup retail.tests.test_recovered_pos_display \
        retail.tests.test_editable_print_portability
    bench set-config -g db_host db
    bench set-config -g db_port 3306
    bench set-config -g redis_cache redis://redis-cache:6379
    bench set-config -g redis_queue redis://redis-queue:6379
    bench set-config -g redis_socketio redis://redis-queue:6379
    bench set-config -g socketio_port 9000
    bench new-site retail-test.localhost --db-host db \
        --db-root-password "$VALIDATION_DB_PASSWORD" \
        --admin-password "$VALIDATION_ADMIN_PASSWORD" \
        --mariadb-user-host-login-scope "%" \
        --install-app erpnext --install-app hrms --install-app retail
    bench --site retail-test.localhost migrate
    bench --site retail-test.localhost migrate
'

# A new container must be able to use the persisted site and validate its schema.
validation_compose run --rm -T checker ./env/bin/python <<'PY'
import json
import os
import frappe
from frappe.core.doctype.doctype.doctype import validate_fields_for_doctype

os.chdir("/home/frappe/frappe-bench/sites")
frappe.init(site="retail-test.localhost", sites_path=".")
frappe.connect()
try:
    assert set(("frappe", "erpnext", "hrms", "retail")) <= set(frappe.get_installed_apps())
    assert frappe.db.exists("DocType", "Counter")
    assert frappe.db.has_column("POS Invoice", "external_pos_reference")
    with open(frappe.get_app_path("retail", "fixtures", "custom_field.json")) as source:
        doctypes = {field["dt"] for field in json.load(source)}
    for doctype in sorted(doctypes):
        validate_fields_for_doctype(doctype)
    for doctype, title in (
        ("Manufacturing BOM", "Manufacturing BOM"),
        ("Manufacturing Production Plan", "Manufacturing Production Plan"),
        ("Manufacturing Quality Inspection", "Manufacturing Quality Inspection"),
    ):
        assert frappe.db.get_value("Workspace", doctype, "title") == title
    print(f"Fresh installation, repeated migration, and {len(doctypes)} schemas validated.")
finally:
    frappe.destroy()
PY

validation_compose up -d backend websocket frontend
validation_compose run --rm -T checker ./env/bin/python <<'PY'
import http.cookiejar
import json
import os
import time
import urllib.parse
import urllib.request
import frappe
from frappe.utils import get_assets_json

os.chdir("/home/frappe/frappe-bench/sites")
frappe.init(site="retail-test.localhost", sites_path=".")
frappe.connect()
try:
    mappings = get_assets_json()
finally:
    frappe.destroy()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def fetch(path, data=None):
    request = urllib.request.Request("http://frontend" + path, data=data,
                                     headers={"Host": "retail-test.localhost"})
    return opener.open(request, timeout=30)
for attempt in range(30):
    try:
        with fetch("/login") as response:
            assert response.status == 200
        break
    except Exception:
        if attempt == 29:
            raise
        time.sleep(1)
login = urllib.parse.urlencode({"usr": "Administrator", "pwd": os.environ["VALIDATION_ADMIN_PASSWORD"]}).encode()
with fetch("/api/method/login", login) as response:
    assert response.status == 200
with fetch("/app") as response:
    html = response.read().decode()
for key in ("retail_desk.bundle.css", "retail_desk.bundle.js", "rtl_retail_desk.bundle.css"):
    path = mappings[key]
    with fetch(path) as response:
        assert response.status == 200
        content = response.read()
        if key.endswith(".css"):
            assert "text/css" in response.headers["Content-Type"]
            assert b"--retail-brand-primary" in content
        else:
            assert "javascript" in response.headers["Content-Type"]
    if not key.startswith("rtl_"):
        assert path in html, f"Desk omitted {key}"
print("Desk HTML and LTR/RTL Retail CSS/JS served correctly through the frontend.")
PY

# These volumes belong exclusively to the randomly named disposable test project.
validation_compose down --volumes
rm "$validation_directory/compose.json"
rmdir "$validation_directory"
echo "PASS: $validation_image is eligible for installation testing on INAYA."
