import frappe


BRAND_NAME = "CELESTA ERP"
HEADER_BRAND_NAME = "CELESTA"
LOGO_URL = "/assets/retail/images/retail-logo.svg?v=4"
FAVICON_URL = "/assets/retail/images/business-suite-app-icon.svg?v=3"
APP_LOGO_URL = "/assets/retail/images/business-suite-app-icon.svg?v=3"


def apply_default_branding():
    website_settings = frappe.get_single("Website Settings")
    website_settings.app_name = BRAND_NAME
    website_settings.app_logo = APP_LOGO_URL
    website_settings.splash_image = LOGO_URL
    website_settings.favicon = FAVICON_URL
    website_settings.brand_html = f'<img src="/assets/retail/images/business-suite-app-icon.svg?v=3" class="retail-web-brand-icon" alt="{BRAND_NAME}"><span class="retail-web-brand">{HEADER_BRAND_NAME}</span>'
    website_settings.footer_logo = LOGO_URL
    website_settings.footer_powered = f'Powered by <span class="text-muted">{BRAND_NAME}</span>'
    website_settings.copyright = BRAND_NAME
    website_settings.save(ignore_permissions=True)

    frappe.db.set_single_value("System Settings", "app_name", BRAND_NAME)
    frappe.db.set_single_value("Navbar Settings", "app_logo", APP_LOGO_URL)
    frappe.clear_cache()
    return {"brand": BRAND_NAME, "logo": LOGO_URL, "app_logo": APP_LOGO_URL}
