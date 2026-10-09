import json
import unittest
from unittest.mock import patch

import frappe
from retail import cdn


class TestSharedCDN(unittest.TestCase):
    def setUp(self):
        self.assets = {"test.bundle.js": "/assets/retail/dist/js/test.bundle.ABC.js"}
        self.manifest = {"bundles": self.assets, "files": {next(iter(self.assets.values())): "digest"}}
        self.config = patch.dict(frappe.conf, {
            "retail_cdn_url": "https://assets.example.com/release",
            "retail_cdn_manifest": "/unused/manifest.json",
        })
        self.config.start()
        if hasattr(frappe.local, "retail_cdn_urls"):
            del frappe.local.retail_cdn_urls

    def tearDown(self):
        self.config.stop()
        if hasattr(frappe.local, "retail_cdn_urls"):
            del frappe.local.retail_cdn_urls

    def urls(self):
        with patch.object(cdn, "get_assets_json", return_value=self.assets), patch(
            "retail.cdn.Path.read_text", return_value=json.dumps(self.manifest)
        ):
            return cdn.asset_urls()

    def test_only_matching_published_bundles_are_routed(self):
        result = self.urls()
        local = next(iter(self.assets.values()))
        self.assertEqual(result, {local: "https://assets.example.com/release" + local})
        self.assertNotIn("/api/method/login", result)
        self.assertNotIn("/private/files/invoice.pdf", result)

    def test_upgrade_mismatch_uses_local_assets(self):
        self.manifest["bundles"] = {"test.bundle.js": "/assets/retail/old.js"}
        self.assertEqual(self.urls(), {})

    def test_malformed_manifest_uses_local_assets(self):
        self.manifest = []
        self.assertEqual(self.urls(), {})

    def test_malformed_url_uses_local_assets(self):
        frappe.conf.retail_cdn_url = "https://[invalid"
        self.assertEqual(self.urls(), {})

    def test_incomplete_release_and_non_https_use_local_assets(self):
        self.manifest["files"] = {}
        self.assertEqual(self.urls(), {})
        del frappe.local.retail_cdn_urls
        frappe.conf.retail_cdn_url = "http://assets.example.com/release"
        self.assertEqual(self.urls(), {})

    def test_boot_mapping_is_copied_and_local_urls_are_retained(self):
        urls = self.urls()
        original = {"assets_json": self.assets.copy()}
        context = frappe._dict(boot=original)
        cdn.update_website_context(context)
        self.assertEqual(original["assets_json"], self.assets)
        remote = next(iter(urls.values()))
        self.assertEqual(context.boot["assets_json"]["test.bundle.js"], remote)
        self.assertEqual(context.boot["retail_cdn_local_assets"][remote], self.assets["test.bundle.js"])

    def test_initial_script_keeps_parser_order_and_local_fallback(self):
        self.urls()
        local = self.assets["test.bundle.js"]
        with patch("frappe.utils.jinja_globals.bundled_asset", return_value=local):
            html = cdn.include_script("test.bundle.js", preload=False)
        self.assertIn('https://assets.example.com/release/assets/', html)
        self.assertIn('document.write(', html)
        self.assertIn(local, html)
        self.assertNotIn('async', html)
