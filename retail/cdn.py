"""Optional release-matched CDN routing, entirely through app extension hooks."""

import hashlib
import json
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

import frappe
from frappe.utils import get_assets_json
from frappe.utils.jinja_globals import include_script as local_script
from frappe.utils.jinja_globals import include_style as local_style


def asset_urls():
    if hasattr(frappe.local, "retail_cdn_urls"):
        return frappe.local.retail_cdn_urls
    frappe.local.retail_cdn_urls = {}
    base = frappe.conf.get("retail_cdn_url") or ""
    if not isinstance(base, str):
        return {}
    base = base.rstrip("/")
    manifest_path = frappe.conf.get("retail_cdn_manifest")
    if not base or not manifest_path:
        return {}
    try:
        parsed = urlsplit(base)
    except ValueError:
        return {}
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment or parsed.username is not None or any(ord(c) < 33 for c in base):
        return {}
    try:
        manifest = json.loads(Path(manifest_path).read_text())
        if not isinstance(manifest, dict):
            return {}
        bundles = get_assets_json()
        # Refuse stale release configuration after a build or an upgrade.
        if manifest.get("bundles") != bundles:
            return {}
        files = manifest["files"]
        if not isinstance(files, dict):
            return {}
        if not all(path in files for path in bundles.values()):
            return {}
        frappe.local.retail_cdn_urls = {
            path: base + path for path in bundles.values()
            if path.startswith("/assets/") and ".." not in path.split("/")
        }
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    return frappe.local.retail_cdn_urls


def include_script(path, preload=True):
    from frappe.utils.jinja_globals import bundled_asset

    local = bundled_asset(path)
    remote = asset_urls().get(local)
    if not remote:
        return local_script(path, preload=preload)
    if preload:
        frappe.local.preload_assets["script"].append(remote)
    identifier = "retail-cdn-" + hashlib.sha256(local.encode()).hexdigest()[:16]
    # A parser-blocking local retry preserves ordering before the next bundle.
    fallback = '<script type="text/javascript" src="' + escape(local, quote=True) + '"></script>'
    encoded = json.dumps(fallback).replace("</", "<\\/")
    return (
        f'<script id="{identifier}" src="{escape(remote, quote=True)}" '
        'onerror="this.dataset.failed=\'1\'"></script>'
        f'<script>if(document.getElementById("{identifier}").dataset.failed)'
        f'{{document.write({encoded});}}</script>'
    )


def include_style(path, rtl=None, preload=True):
    from frappe.utils.jinja_globals import bundled_asset

    local = bundled_asset(path, rtl=rtl)
    remote = asset_urls().get(local)
    if not remote:
        return local_style(path, rtl=rtl, preload=preload)
    if preload:
        frappe.local.preload_assets["style"].append(remote)
    retry = "this.onerror=null;this.href=" + json.dumps(local)
    return f'<link rel="stylesheet" href="{escape(remote, quote=True)}" onerror="{escape(retry, quote=True)}">'


def update_website_context(context):
    urls = asset_urls()
    boot = context.get("boot")
    if not urls or not boot or not boot.get("assets_json"):
        return
    context.boot = dict(boot)
    context.boot["retail_cdn_local_assets"] = {remote: local for local, remote in urls.items()}
    context.boot["assets_json"] = {name: urls.get(path, path) for name, path in boot["assets_json"].items()}
