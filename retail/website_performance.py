"""Avoid discarded website boot work for native Desk and website scripts."""

import frappe
from frappe.website.page_renderers.template_page import TemplatePage
from frappe.website.page_renderers.base_renderer import BaseRenderer


class DeskEntryPage(TemplatePage):
    """Retain the native Desk controller, without the discarded website boot."""

    def __init__(self, path, http_status_code=None):
        if path in ("app", "retail-desk-entry") and self._matches("app"):
            super().__init__("app", http_status_code)
        else:
            BaseRenderer.__init__(self, path, http_status_code)
            self.template_path = ""

    @staticmethod
    def _matches(path):
        request = getattr(frappe.local, "request", None)
        return bool(
            path == "app" and request and request.method in ("GET", "HEAD")
            and (request.path == "/app" or request.path.startswith("/app/"))
            and frappe.session.user != "Guest"
        )

    def can_render(self):
        return (
            self._matches(self.path) and getattr(self, "app", None) == "frappe"
            and super().can_render()
        )

    def init_context(self):
        if not self.can_render():
            return super().init_context()
        from retail.guest_entry import get_entry_settings
        # app.py supplies the real permission-filtered Desk boot and CSRF token.
        self.context = get_entry_settings()
        self.context.update(frappe.local.conf.get("website_context") or {})


class WebsiteScriptPage(TemplatePage):
    def can_render(self):
        # Preserve an installed app's own replacement of the standard endpoint.
        return (
            self.path == "website_script.js"
            and getattr(self, "app", None) == "frappe"
            and super().can_render()
        )

    def init_context(self):
        # The standard script controller supplies Website Script, theme JS and
        # analytics settings. Its template only needs view tracking from the
        # website context; there is no reason to build apps/workspace boot data.
        self.context = frappe._dict(
            enable_view_tracking=frappe.get_cached_doc("Website Settings").enable_view_tracking
        )
        self.context.update(frappe.local.conf.get("website_context") or {})
