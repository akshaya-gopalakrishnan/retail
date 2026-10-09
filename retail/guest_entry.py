"""Guest entry only: retain Frappe login rendering without Desk discovery.

The settings/boot builders mirror Frappe's website builders, omitting only
Desk app discovery. A parity regression test guards that deliberately narrow
copy against framework changes. No framework function is patched.
"""

# Website context builders adapted from Frappe (MIT).
# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors.

from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import cint, encode, get_assets_json, get_request_site_address, get_system_timezone
from frappe.website.doctype.website_settings.website_settings import modify_header_footer_items
from frappe.website.page_renderers.base_renderer import BaseRenderer
from frappe.website.page_renderers.template_page import TemplatePage
from frappe.website.path_resolver import resolve_path


def resolve_guest_entry(path):
    # This hook runs in website routing, after validate_auth (including Retail's
    # licensing/access hooks), and before any renderer initializes its context.
    request = frappe.local.request
    if (
        frappe.session.user == "Guest"
        and request.method in ("GET", "HEAD")
        and (path == "app" or path.startswith("app/"))
        and (request.path == "/app" or request.path.startswith("/app/"))
    ):
        from frappe.www.app import get_context

        # Reuse the standard Guest branch, including destination encoding and
        # the login message. It raises frappe.Redirect before any boot work.
        get_context(frappe._dict())
    # Match PathResolver's default route resolution, including slash redirects.
    from werkzeug.routing.exceptions import RequestRedirect

    try:
        endpoint = resolve_path(path)
        if endpoint == "app" and frappe.session.user != "Guest":
            from retail.website_performance import DeskEntryPage
            # Frappe hardcodes TemplatePage for endpoint=app, bypassing custom
            # renderers. Select an internal endpoint only for its native Desk
            # template; preserve installed overrides and forbidden Website users.
            if DeskEntryPage._matches("app") and frappe.get_cached_value(
                "User", frappe.session.user, "user_type"
            ) == "System User" and DeskEntryPage("app").can_render():
                return "retail-desk-entry"
        return endpoint
    except RequestRedirect as exc:
        frappe.flags.redirect_location = exc.new_url
        raise frappe.Redirect(exc.code) from exc


class GuestLoginPage(TemplatePage):
    def __init__(self, path, http_status_code=None):
        # Custom renderers are instantiated before can_render is checked. Avoid
        # even template-file discovery for authenticated or unrelated requests.
        if (
            path == "login"
            and frappe.local.request.path == "/login"
            and frappe.local.request.method in ("GET", "HEAD")
            and frappe.session.user == "Guest"
        ):
            super().__init__(path, http_status_code)
        else:
            BaseRenderer.__init__(self, path, http_status_code)
            self.template_path = ""

    def can_render(self):
        return (
            self.path == "login"
            and frappe.local.request.path == "/login"
            and frappe.local.request.method in ("GET", "HEAD")
            and frappe.session.user == "Guest"
            and getattr(self, "app", None) == "frappe"
            and super().can_render()
        )

    def init_context(self):
        # Defense in depth if the renderer is called outside PathResolver.
        if not self.can_render():
            return super().init_context()
        self.context = get_guest_login_settings()
        self.context.update(frappe.local.conf.get("website_context") or {})


def get_guest_login_settings(context=None):
    return get_entry_settings(context, boot_factory=get_guest_login_boot)


def get_entry_settings(context=None, boot_factory=None):
    """Standard website settings with an optional entry-specific boot builder."""
    hooks = frappe.get_hooks()
    context = frappe._dict(context or {})
    settings = frappe.get_cached_doc("Website Settings")

    context = context.update(
        {
            "top_bar_items": modify_header_footer_items(settings.top_bar_items),
            "footer_items": modify_header_footer_items(settings.footer_items),
            "post_login": [
                {"label": _("My Account"), "url": "/me"},
                {"label": _("Log out"), "url": "/?cmd=web_logout"},
            ],
        }
    )

    for k in [
        "banner_html",
        "banner_image",
        "brand_html",
        "copyright",
        "twitter_share_via",
        "facebook_share",
        "google_plus_one",
        "twitter_share",
        "linked_in_share",
        "disable_signup",
        "hide_footer_signup",
        "head_html",
        "title_prefix",
        "navbar_template",
        "footer_template",
        "navbar_search",
        "enable_view_tracking",
        "footer_logo",
        "call_to_action",
        "call_to_action_url",
        "show_language_picker",
        "footer_powered",
    ]:
        if setting_value := settings.get(k):
            context[k] = setting_value

    for k in [
        "facebook_share",
        "google_plus_one",
        "twitter_share",
        "linked_in_share",
        "disable_signup",
    ]:
        context[k] = int(context.get(k) or 0)

    if settings.address:
        context["footer_address"] = settings.address

    if frappe.request:
        context.url = quote(str(get_request_site_address(full_address=True)), safe="/:")

    context.encoded_title = quote(encode(context.title or ""), "")

    context.web_include_js = hooks.web_include_js or []

    context.web_include_css = hooks.web_include_css or []

    via_hooks = hooks.website_context or []
    for key in via_hooks:
        context[key] = via_hooks[key]
        if key not in ("top_bar_items", "footer_items", "post_login") and isinstance(
            context[key], list | tuple
        ):
            context[key] = context[key][-1]

    if context.disable_website_theme:
        context.theme = frappe._dict()

    else:
        from frappe.website.doctype.website_theme.website_theme import get_active_theme

        context.theme = get_active_theme() or frappe._dict()

    if not context.get("favicon"):
        context["favicon"] = "/assets/frappe/images/frappe-favicon.svg"

    if settings.favicon and settings.favicon != "attach_files:":
        context["favicon"] = settings.favicon

    context["hide_login"] = settings.hide_login

    if settings.splash_image:
        context["splash_image"] = settings.splash_image

    context.read_only_mode = frappe.flags.read_only
    if boot_factory is not None:
        context.boot = boot_factory()

    return context


def get_guest_login_boot():
    from frappe.integrations.frappe_providers.frappecloud_billing import is_fc_site

    return {
        "lang": frappe.local.lang or "en",
        "apps_data": {
            "apps": [],
            "is_desk_apps": 1,  # Frappe classifies an empty app list as Desk-only.
            "default_path": "",
        },
        "sysdefaults": {
            "float_precision": cint(frappe.get_system_settings("float_precision")) or 3,
            "date_format": frappe.get_system_settings("date_format") or "yyyy-mm-dd",
            "time_format": frappe.get_system_settings("time_format") or "HH:mm:ss",
            "first_day_of_the_week": frappe.get_system_settings("first_day_of_the_week") or "Sunday",
            "number_format": frappe.get_system_settings("number_format") or "#,###.##",
            "currency": frappe.get_system_settings("currency"),
        },
        "time_zone": {
            "system": get_system_timezone(),
            "user": frappe.db.get_value("User", frappe.session.user, "time_zone") or get_system_timezone(),
        },
        "assets_json": get_assets_json(),
        "sitename": frappe.local.site,
        "is_fc_site": 1 if is_fc_site() else 0,
    }
