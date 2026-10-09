import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.website.page_renderers.template_page import TemplatePage

from retail.website_performance import WebsiteScriptPage


class TestWebsiteScriptPage(unittest.TestCase):
    def test_other_pages_and_app_overrides_use_standard_renderer(self):
        with patch.object(TemplatePage, "set_template_path"):
            for path, app in [("login", "frappe"), ("website_script.js", "retail")]:
                page = WebsiteScriptPage(path)
                page.app = app
                self.assertFalse(page.can_render())

    def test_context_does_not_build_workspace_navigation(self):
        with patch.object(TemplatePage, "set_template_path"), patch(
            "frappe.get_cached_doc", return_value=SimpleNamespace(enable_view_tracking=1)
        ), patch("frappe.apps.get_apps", side_effect=AssertionError("Desk boot was requested")):
            page = WebsiteScriptPage("website_script.js")
            page.init_context()
            self.assertEqual(page.context.enable_view_tracking, 1)
            self.assertNotIn("boot", page.context)

    def test_standard_controller_and_template_are_retained(self):
        # With a live site initialized, verify actual standard output for custom
        # JS and both states of view tracking without saving settings.
        from frappe.www import website_script

        for tracking in (0, 1):
            with self.subTest(tracking=tracking), patch(
                "frappe.get_cached_doc", return_value=SimpleNamespace(enable_view_tracking=tracking)
            ), patch("frappe.db.get_single_value", return_value="window.retailScriptTest = true;"), patch(
                "frappe.www.website_script.get_active_theme", return_value=frappe._dict(js="window.retailThemeTest = true;")
            ):
                page = WebsiteScriptPage("website_script.js")
                page.init_context()
                website_script.get_context(page.context)
                rendered = frappe.render_template("www/website_script.js", page.context)
                self.assertIn("window.retailScriptTest = true;", rendered)
                self.assertIn("window.retailThemeTest = true;", rendered)
                self.assertEqual("make_view_log" in rendered, bool(tracking))

    def test_analytics_settings_are_preserved(self):
        from frappe.www import website_script

        with patch.dict(frappe.conf, {"developer_mode": 0}), patch(
            "frappe.db.get_single_value", return_value=""
        ), patch("frappe.www.website_script.get_active_theme", return_value=None), patch(
            "frappe.www.website_script.get_setting",
            side_effect=lambda field: "UA-TEST-1" if field == "google_analytics_id" else 1,
        ):
            context = frappe._dict(enable_view_tracking=0)
            website_script.get_context(context)
            rendered = frappe.render_template("www/website_script.js", context)
            self.assertIn("UA-TEST-1", rendered)
            self.assertIn("anonymizeIp", rendered)


class TestDeskEntryPage(unittest.TestCase):
    def test_website_settings_match_standard_except_discarded_website_boot(self):
        from retail.guest_entry import get_entry_settings
        from frappe.website.doctype.website_settings.website_settings import get_website_settings
        with patch('frappe.website.doctype.website_settings.website_settings.get_boot_data', return_value={'discarded': True}):
            expected = get_website_settings()
        expected.pop('boot')
        with patch('frappe.apps.get_apps', side_effect=AssertionError('Duplicate Desk discovery')):
            self.assertEqual(get_entry_settings(), expected)

    def test_renderer_only_handles_authenticated_native_desk_get_and_head(self):
        from retail.website_performance import DeskEntryPage
        from werkzeug.wrappers import Request
        from werkzeug.test import EnvironBuilder
        with patch.object(frappe.local, 'session', new=frappe._dict(user='Administrator')):
            for path, method, match in [('/app','GET',True),('/app/business-home','HEAD',True),('/app','POST',False),('/application','GET',False),('/login','GET',False)]:
                with patch.object(frappe.local, 'request', new=Request(EnvironBuilder(path=path,method=method).get_environ()),create=True):
                    self.assertEqual(DeskEntryPage._matches('app'),match)
                    self.assertFalse(DeskEntryPage._matches('login'))
        with patch.object(frappe.local, 'session', new=frappe._dict(user='Guest')), patch.object(frappe.local,'request',new=Request(EnvironBuilder(path='/app').get_environ()),create=True):
            self.assertFalse(DeskEntryPage._matches('app'))

    def test_installed_app_template_override_remains_standard(self):
        from retail.website_performance import DeskEntryPage
        from werkzeug.wrappers import Request
        from werkzeug.test import EnvironBuilder
        with patch.object(frappe.local, 'request', new=Request(EnvironBuilder(path='/app').get_environ()),create=True), patch.object(TemplatePage,'set_template_path'):
            page = DeskEntryPage('app')
            page.app='retail'
            self.assertFalse(page.can_render())
