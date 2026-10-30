app_name = "retail"
app_title = "CELESTA ERP"
app_publisher = "Arab Scale"
app_description = "CELESTA ERP Application"
app_email = "akshayagopal1@gmail.com"
app_license = "mit"
app_logo_url = "/assets/retail/images/business-suite-app-icon.svg"

# Apps
# ------------------

required_apps = ["erpnext", "hrms"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "retail",
# 		"logo": "/assets/retail/logo.png",
# 		"title": "Retail",
# 		"route": "/retail",
# 		"has_permission": "retail.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = [
#     "/assets/retail/css/retail_icons.css"
# ]
# retail/retail/hooks.py

app_include_css = ["retail_desk.bundle.css"]

app_include_js = ["retail_desk.bundle.js"]

# include js, css files in header of web template
web_include_css = ["retail_website.bundle.css"]

web_include_js = ["retail_website.bundle.js"]

page_renderer = [
	"retail.guest_entry.GuestLoginPage",
	"retail.website_performance.DeskEntryPage",
	"retail.website_performance.WebsiteScriptPage",
]
website_path_resolver = ["retail.guest_entry.resolve_guest_entry"]

jinja = {"methods": ["retail.cdn.include_script", "retail.cdn.include_style", "retail.print_item_tax.item_tax_for_print", "retail.pos_day_closing_print.day_closing_print_data"]}
update_website_context = ["retail.cdn.update_website_context"]

website_context = {
	"brand_html": '<img src="/assets/retail/images/business-suite-app-icon.svg?v=3" class="retail-web-brand-icon" alt="CELESTA ERP"><span class="retail-web-brand">CELESTA</span>',
	"favicon": "/assets/retail/images/business-suite-app-icon.svg?v=3",
	"splash_image": "/assets/retail/images/retail-logo.svg?v=4",
}

website_route_rules = [
	{"from_route": "/me", "to_route": "retail-me"},
	{"from_route": "/profile", "to_route": "retail-me"},
	{"from_route": "/website", "to_route": "retail-home"},
]

website_redirects = [
	{"source": "/", "target": "/app", "redirect_http_status": 302},
	{"source": "/index", "target": "/retail-home", "redirect_http_status": 302},
]

boot_session = "retail.workspace_permissions.extend_bootinfo"

# Demo generation is disabled; setup and migrations must not create business records.

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "retail/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
doctype_list_js = {
	"Item Price": "public/js/list/item_price.js",
	"POS Invoice": "public/js/pos_creation_controls.js",
	"POS Opening Entry": "public/js/pos_creation_controls.js",
	"POS Closing Entry": "public/js/pos_creation_controls.js",
	"POS Cashier Shift": "public/js/pos_creation_controls.js",
	"POS Counter Session": "public/js/pos_creation_controls.js",
	"POS Sync Log": "public/js/pos_creation_controls.js",
	"Journal Entry": "public/js/hide_transaction_id_list.js",
	"Payment Entry": "public/js/hide_transaction_id_list.js",
	"Sales Invoice": [
		"public/js/hide_transaction_id_list.js",
		"public/js/sales_invoice_list.js",
	],
	"Purchase Invoice": "public/js/hide_transaction_id_list.js",
	"Sales Order": [
		"public/js/hide_transaction_id_list.js",
		"public/js/sales_order_list.js",
	],
	"Purchase Order": "public/js/hide_transaction_id_list.js",
	"Delivery Note": "public/js/hide_transaction_id_list.js",
	"Purchase Receipt": "public/js/hide_transaction_id_list.js",
	"Stock Entry": "public/js/hide_transaction_id_list.js",
	"Van Session": "public/js/list/van_session.js",
	"Material Request": [
		"public/js/hide_transaction_id_list.js",
		"public/js/list/material_request.js",
	],
	"Customer": [
		"public/js/hide_transaction_id_list.js",
		"public/js/list/customer_balances.js",
	],
	"Item": [
		"public/js/hide_transaction_id_list.js",
		"public/js/item_list_zebra_labels.js",
	],
	"Supplier": "public/js/hide_transaction_id_list.js",
	"Serial and Batch Bundle": "public/js/hide_transaction_id_list.js",
	"Bin": "public/js/hide_transaction_id_list.js",
	"Sales Taxes and Charges Template": "public/js/hide_transaction_id_list.js",
	"Counter": "public/js/hide_transaction_id_list.js",
}
doctype_js = {
	"Buy X Get Y Promotion": "public/js/forms/buy_x_get_y_promotion.js",
	"Promo Price": "public/js/forms/promo_price.js",
	"Employee": "public/js/forms/pos_login.js",
	"User": "public/js/forms/pos_login.js",
	"Item": "public/js/forms/item.js",
	"Item Price": "public/js/forms/item_price_rate_update.js",
	"Retail Item Rate Audit": "public/js/forms/retail_item_rate_audit.js",
	"Purchase Order": [
		"public/js/forms/foc_qty.js",
		"public/js/forms/purchase_history.js",
	],
	"Purchase Receipt": [
		"public/js/forms/foc_qty.js",
		"public/js/forms/purchase_selling_price.js",
		"public/js/forms/purchase_history.js",
	],
	"Purchase Invoice": [
		"public/js/forms/foc_qty.js",
		"public/js/forms/purchase_selling_price.js",
		"public/js/forms/purchase_history.js",
	],
	"Sales Order": "public/js/forms/foc_qty.js",
	"Delivery Note": "public/js/forms/foc_qty.js",
	"Sales Invoice": ["public/js/forms/sales_invoice.js", "public/js/forms/sales_invoice_loyalty.js"],
	"Payment Entry": "public/js/forms/payment_entry.js",
	"POS Invoice": ["public/js/forms/foc_qty.js", "public/js/forms/pos_invoice.js"],
	"Stock Entry": [
		"public/js/forms/foc_qty.js",
		"public/js/forms/van_stock_entry.js",
	],
	"Material Request": "public/js/forms/material_request.js",
	"Van Session": "public/js/forms/van_session.js",
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "retail/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "retail.utils.jinja_methods",
# 	"filters": "retail.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "retail.install.before_install"
after_install = [
	"retail.patches.setup_pos_operator_privileges.execute",
	"retail.naming.install_retail_defaults",
	"retail.pos_credit.ensure_payment_invoice_field",
]

# Print Format fixtures must exist before creating site-owned editable copies.
after_sync = [
	"retail.editable_print_formats.ensure_editable_print_formats",
	"retail.setup.ensure_print_languages",
]

# Uninstallation
# ------------

# before_uninstall = "retail.uninstall.before_uninstall"
# after_uninstall = "retail.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "retail.utils.before_app_install"
# after_app_install = "retail.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "retail.utils.before_app_uninstall"
# after_app_uninstall = "retail.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "retail.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"Van Fleet": "retail.van_assignment.fleet_condition",
	"Van Session": "retail.van_assignment.session_condition",
	"Sales Invoice": "retail.van_permissions.get_sales_invoice_permission_query_conditions",
	"Customer": "retail.van_permissions.get_customer_permission_query_conditions",
	"Stock Entry": "retail.van_permissions.get_stock_entry_permission_query_conditions",
	"Payment Entry": "retail.van_permissions.get_payment_entry_permission_query_conditions",
	"Material Request": "retail.van_permissions.get_material_request_permission_query_conditions",
}

has_permission = {
	"Van Fleet": "retail.van_assignment.has_fleet_permission",
	"Van Session": "retail.van_assignment.has_session_permission",
	"Sales Invoice": "retail.van_permissions.has_sales_invoice_permission",
	"Customer": "retail.van_permissions.has_customer_permission",
	"Stock Entry": "retail.van_permissions.has_stock_entry_permission",
	"Payment Entry": "retail.van_payment.has_payment_entry_permission",
	"Material Request": "retail.van_material_request.has_material_request_permission",
}

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Van Session": {
		"validate": "retail.van_assignment.validate_session",
		"before_update_after_submit": "retail.van_assignment.validate_session",
	},
	"*": {
		"before_insert": "retail.document_codes.assign",
		"autoname": "retail.short_codes.autoname",
		"before_naming": "retail.short_codes.before_naming",
		"validate": ["retail.van_assignment.validate_transaction", "retail.document_codes.validate"],
		"before_submit": "retail.van_assignment.validate_transaction",
	},
	"Employee": {
        "before_save": "retail.employee_permissions.prepare_employee",
		"validate": [
			"retail.pos_login.apply_employee_pos_login",
			"retail.pos_privileges.validate_employee_assignment",
		],
		"on_update": "retail.pos_login.sync_employee_pos_user",
	},
	"User": {
		"validate": "retail.pos_login.apply_user_pos_login",
		"after_insert": "retail.grid_view_settings.apply_default_grid_view_settings_for_user",
	},
	"Purchase Order": {
		"before_submit": "retail.domains.purchase.history.warn_before_submit",
		"validate": [
			"retail.domains.foc.apply_foc_quantities",
			"retail.domains.transactions.vat.set_vat_rates",
			"retail.domains.purchase.order.set_balance_qty",
		],
		"before_save": "retail.domains.transactions.vat.set_vat_rates",
		"on_submit": "retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
		"on_cancel": "retail.domains.item.item_price_sync.recalculate_transaction_item_prices",
		"on_update_after_submit": "retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
	},
	"Purchase Receipt": {
		"before_naming": "retail.naming.set_transaction_naming_series",
		"before_submit": "retail.domains.purchase.history.warn_before_submit",
		"validate": [
			"retail.domains.foc.apply_foc_quantities",
			"retail.domains.transactions.vat.set_vat_rates",
			"retail.domains.purchase.selling_price.set_selling_price_margins",
		],
		"on_submit": [
			"retail.domains.purchase.order.sync_balance_qty_from_transaction",
			"retail.domains.item.average_purchase_rate.sync_average_purchase_rates",
			"retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
			"retail.domains.purchase.selling_price.update_selected_selling_prices",
		],
		"on_cancel": [
			"retail.domains.purchase.order.sync_balance_qty_from_transaction",
			"retail.domains.item.average_purchase_rate.sync_average_purchase_rates",
			"retail.domains.item.item_price_sync.recalculate_transaction_item_prices",
			"retail.domains.purchase.price_history.rollback_selling_prices",
		],
		"on_update_after_submit": [
			"retail.domains.purchase.order.sync_balance_qty_from_transaction",
			"retail.domains.item.average_purchase_rate.sync_average_purchase_rates",
			"retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
		],
	},
	"Purchase Invoice": {
		"before_naming": "retail.naming.set_transaction_naming_series",
		"before_submit": "retail.domains.purchase.history.warn_before_submit",
		"before_validate": "retail.domains.transactions.stock.set_update_stock_for_standalone_invoice",
		"validate": [
			"retail.domains.foc.apply_foc_quantities",
			"retail.domains.transactions.vat.set_vat_rates",
			"retail.domains.purchase.selling_price.set_selling_price_margins",
		],
		"on_submit": [
			"retail.domains.purchase.order.sync_balance_qty_from_transaction",
			"retail.domains.item.average_purchase_rate.sync_average_purchase_rates",
			"retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
			"retail.domains.purchase.selling_price.update_selected_selling_prices",
		],
		"on_cancel": [
			"retail.domains.purchase.order.sync_balance_qty_from_transaction",
			"retail.domains.item.average_purchase_rate.sync_average_purchase_rates",
			"retail.domains.item.item_price_sync.recalculate_transaction_item_prices",
			"retail.domains.purchase.price_history.rollback_selling_prices",
		],
		"on_update_after_submit": [
			"retail.domains.purchase.order.sync_balance_qty_from_transaction",
			"retail.domains.item.average_purchase_rate.sync_average_purchase_rates",
			"retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
		],
	},
	"Item": {
		"before_naming": "retail.domains.item.naming.set_automatic_item_code",
		"before_validate": [
			"retail.domains.item.scale_item_validation.ensure_item_barcode",
			"retail.domains.item.packing_sync.sync_uoms_and_barcodes",
		],
		"validate": [
			"retail.domains.item.scale_item_validation.ensure_item_barcode",
			"retail.domains.item.packing_sync.validate_packing_uoms",
			"retail.domains.item.scale_item_validation.validate_scale_item",
			"retail.domains.item.vat_pricing.update_item_vat_prices",
		],
		"on_update": [
			"retail.domains.item.item_price_sync.sync_simple_item_prices",
			"retail.domains.item.average_purchase_rate.sync_average_purchase_rate_from_item",
			"retail.domains.item.rate_audit.audit_item_master_rate_change",
		],
	},
	"Customer": {
		"validate": "retail.van_customer.validate_van_customer_access",
	},
	"Item Price": {
		"validate": "retail.domains.item.item_price_sync.populate_item_price_barcode",
		"before_save": "retail.domains.purchase.price_history.audit_direct_price_edit",
		"on_update": "retail.domains.item.item_price_sync.sync_item_master_purchase_rate_from_item_price",
	},
	"Sales Invoice": {
		"before_naming": "retail.naming.set_transaction_naming_series",
		"before_validate": [
			"retail.domains.transactions.stock.set_update_stock_for_standalone_invoice",
			"retail.van_sales_invoice.apply_van_sales_invoice_rules",
		],
		"validate": [
			"retail.domains.foc.apply_foc_quantities",
			"retail.domains.transactions.vat.set_vat_rates",
			"retail.promotions.promo_price.apply_inclusive_promo_prices",
			"retail.domains.sales.counter.set_sales_invoice_counter_name",
			"retail.domains.sales.invoice_totals.apply_retail_shipping_charges",
			"retail.api.pos_sync.validate_external_reference",
			"retail.api.pos_sync.block_external_sales_invoice",
			"retail.promotions.gift_voucher.apply_gift_voucher_redemption",
		],
		"on_submit": [
			"retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
			"retail.promotions.gift_voucher.issue_gift_vouchers",
			"retail.promotions.gift_voucher.mark_gift_voucher_redeemed",
		],
		"on_cancel": [
			"retail.domains.item.item_price_sync.recalculate_transaction_item_prices",
			"retail.promotions.gift_voucher.cancel_issued_gift_vouchers",
			"retail.promotions.gift_voucher.restore_redeemed_gift_voucher",
		],
		"on_update_after_submit": "retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
	},
	"POS Invoice": {
		"before_validate": "retail.domains.transactions.vat.prepare_external_pos_taxes",
		"validate": [
			"retail.domains.foc.apply_foc_quantities",
			"retail.domains.transactions.vat.set_vat_rates",
			"retail.promotions.promo_price.apply_inclusive_promo_prices",
			"retail.api.pos_sync.validate_external_reference",
			"retail.promotions.gift_voucher.apply_gift_voucher_redemption",
			"retail.pos_completed_sale.restore",
		],
		"on_submit": [
			"retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
			"retail.promotions.gift_voucher.issue_gift_vouchers",
			"retail.promotions.gift_voucher.mark_gift_voucher_redeemed",
		],
		"on_cancel": [
			"retail.domains.item.item_price_sync.recalculate_transaction_item_prices",
			"retail.promotions.gift_voucher.cancel_issued_gift_vouchers",
			"retail.promotions.gift_voucher.restore_redeemed_gift_voucher",
		],
		"on_update_after_submit": "retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
	},
	"Delivery Note": {
		"before_naming": "retail.naming.set_transaction_naming_series",
		"validate": [
			"retail.domains.foc.apply_foc_quantities",
			"retail.domains.transactions.vat.set_vat_rates",
		],
		"on_submit": [
			"retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
		],
		"on_cancel": "retail.domains.item.item_price_sync.recalculate_transaction_item_prices",
		"on_update_after_submit": "retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
	},
	"Sales Order": {
		"validate": [
			"retail.domains.foc.apply_foc_quantities",
			"retail.domains.transactions.vat.set_vat_rates",
		],
		"on_submit": "retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
		"on_cancel": "retail.domains.item.item_price_sync.recalculate_transaction_item_prices",
		"on_update_after_submit": "retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
	},
	"Quotation": {
		"validate": "retail.domains.transactions.vat.set_vat_rates",
	},
	"Supplier Quotation": {
		"validate": "retail.domains.transactions.vat.set_vat_rates",
	},
	"Material Request": {
		"validate": [
			"retail.van_material_request.apply_van_material_request_rules",
			"retail.domains.transactions.vat.set_vat_rates",
		],
	},
	"Opportunity": {
		"validate": "retail.domains.transactions.vat.set_vat_rates",
	},
	"Blanket Order": {
		"validate": "retail.domains.transactions.vat.set_vat_rates",
	},
	"Subcontracting Order": {
		"validate": "retail.domains.transactions.vat.set_vat_rates",
	},
	"Subcontracting Receipt": {
		"validate": "retail.domains.transactions.vat.set_vat_rates",
	},
	"Stock Entry": {
		"validate": [
			"retail.van_stock.merge_duplicate_van_stock_rows",
			"retail.domains.foc.apply_foc_quantities",
		],
	},
	"Payment Entry": {
		"on_submit": "retail.pos_credit.refresh_payment_balance",
		"on_cancel": "retail.pos_credit.refresh_payment_balance",
		"before_naming": "retail.naming.set_transaction_naming_series",
		"validate": [
			"retail.van_payment.apply_van_payment_rules",
			"retail.api.pos_sync.validate_external_reference",
		],
	},
	"Journal Entry": {
		"before_naming": "retail.naming.set_transaction_naming_series",
	},
}

after_migrate = [
	"retail.build_asset_manifest.install",
	"retail.patches.setup_pos_operator_privileges.execute",
	"retail.pos_credit.ensure_payment_invoice_field",
	"retail.branding.apply_default_branding",
	"retail.setup.hide_non_retail_workspaces",
	"retail.setup.ensure_settings_sidebar_workspaces",
	"retail.setup.ensure_website_route_redirects",
	"retail.setup.clear_url_shortcut_link_targets",
	"retail.promotions.gift_voucher.ensure_gift_voucher_invoice_fields",
	"retail.setup.ensure_default_print_formats",
	"retail.setup.ensure_print_languages",
	"retail.retail_app.report.pos_report_utils.ensure_pos_reports",
	"retail.domains.transactions.vat.ensure_transaction_vat_rate_fields",
	"retail.domains.purchase.order.backfill_balance_qty",
	"retail.retail_app.report.damaged_and_expired_stock.damaged_and_expired_stock.ensure_report",
	"retail.retail_app.report.item_family_list.item_family_list.ensure_setup",
	"retail.retail_app.report.near_expiry_report.near_expiry_report.ensure_report",
	"retail.retail_app.report.negative_stock_report.negative_stock_report.ensure_report",
	"retail.domains.item.average_purchase_rate.backfill_average_purchase_rates",
	"retail.domains.item.average_purchase_rate.clear_average_purchase_rate_description",
	"retail.domains.item.average_purchase_rate.ensure_item_price_list_field",
	"retail.domains.item.naming.install_item_code_defaults",
	"retail.domains.item.item_price_sync.disable_legacy_item_price_scripts",
	"retail.domains.item.item_price_sync.ensure_standard_purchase_rate_field",
	"retail.domains.item.packing_sync.disable_legacy_uom_barcode_script",
	"retail.domains.item.packing_rate.ensure_packing_purchase_rate_script",
	"retail.domains.item.arabic_name.ensure_item_arabic_name_field",
	"retail.domains.item.pos_flags.ensure_item_pos_flags",
	"retail.domains.item.scale_item_validation.ensure_scale_item_setup",
	"retail.retail_app.doctype.scale_barcode_format.scale_barcode_format.ensure_default_scale_barcode_format",
	"retail.domains.item.scale_export_service.ensure_default_scale_export_template",
	"retail.grid_view_settings.install_default_grid_view_settings",
	"retail.domains.item.vat_pricing.ensure_item_vat_pricing_fields",
	"retail.domains.item.rate_audit.ensure_rate_audit_setup",
	"retail.domains.item.vat_pricing.backfill_item_master_last_purchase_rates",
	"retail.domains.sales.invoice_totals.ensure_all_transaction_totals_fields",
	"retail.domains.purchase.selling_price.ensure_purchase_selling_price_fields",
	"retail.van_sales_setup.ensure_van_sales_metadata",
	"retail.van_sales_setup.remove_legacy_van_sales_invoice",
	"retail.customer_reports_workspace.ensure_customer_report_cards",
]

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"retail.tasks.all"
# 	],
# 	"daily": [
# 		"retail.tasks.daily"
# 	],
# 	"hourly": [
# 		"retail.tasks.hourly"
# 	],
# 	"weekly": [
# 		"retail.tasks.weekly"
# 	],
# 	"monthly": [
# 		"retail.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "retail.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "retail.event.get_events"
# }
override_whitelisted_methods = {
	"erpnext.stock.get_item_details.get_item_details": "retail.domains.item.packing_scan.get_item_details",
	"erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry.get_pos_invoices": "retail.pos_realtime.get_pos_invoices",
	"frappe.desk.query_report.run": "retail.retail_app.report.stock_movement_utils.run_query_report",
	"frappe.desk.desktop.get_workspace_sidebar_items": "retail.workspace_permissions.get_workspace_sidebar_items",
	"frappe.desk.desktop.get_desktop_page": "retail.business_home_preload.get_desktop_page",
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "retail.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["retail.utils.before_request"]
# after_request = ["retail.utils.after_request"]

# Job Events
# ----------
# before_job = ["retail.utils.before_job"]
# after_job = ["retail.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"retail.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

from retail.short_codes import PREFIXES as _retail_numbered_doctypes

fixtures = [
	{
		"dt": "DocType",
		"filters": [["name", "in", ("Counter",)]],
	},
	"Custom Field",
	"Client Script",
	"Server Script",
	{
		"dt": "Property Setter",
		"filters": [
			[
				"name",
				"not in",
				[
					*[
						f"{dt}-naming_series-{prop}"
						for dt in _retail_numbered_doctypes
						for prop in ("options", "default")
					],
					*[
						f"{dt}-main-default_print_format"
						for dt in (
							"Sales Invoice",
							"Delivery Note",
							"Quotation",
							"Sales Order",
							"Supplier Quotation",
							"Purchase Order",
							"Purchase Receipt",
							"Purchase Invoice",
							"Material Request",
						)
					],
				],
			]
		],
	},
	{"dt": "Print Format", "filters": [["name", "not like", "% - Editable"], ["name", "not like", "% - A4"]]},
	"List View Settings",
	"Custom DocPerm",
	"Workflow",
	"Workflow State",
	"Workflow Action Master",
	{
		"dt": "Workspace",
		"filters": [["module", "=", "Retail-app"]],
	},
	{
		"dt": "Zebra Label Format",
		"filters": [["name", "in", ("Shelf Label", "Barcode Label")]],
	},
	{
		"dt": "Number Card",
		"filters": [
			[
				"name",
				"in",
				(
					"Today's Sales",
					"Today's Profit",
					"Invoice Count Today",
					"Low Stock Items",
					"Out of Stock Items",
					"Return Amount Today",
					"Damage Amount Today",
					"Cash in Hand Today",
				),
			]
		],
	},
]
# app_include_js = "/assets/retail/js/retail_navigation.js?v=15"

# Keep the configured short public identifiers available after migrations.
after_migrate.append("retail.document_codes.install")
after_install.append("retail.document_codes.install")
boot_session = [boot_session, "retail.document_codes.boot", "retail.column_preferences.boot_session"]

scheduler_events = {"hourly": ["retail.document_codes.backfill_missing"]}

# Retail owns loyalty validation and ledger reversals; no ERPNext core edits.
# Frappe v15 has no extend_doctype_class. Keep these existing scoped subclasses
# for receipt immutability/loyalty/posting; replacing them changes business logic.
override_doctype_class = {  # nosemgrep: frappe-semgrep-rules.rules.override-doctype-class
	"Batch": "retail.batch.RetailBatch",
	"Sales Invoice": "retail.loyalty_sales_invoice.RetailSalesInvoice",
	"POS Invoice": "retail.pos_completed_sale.RetailPOSInvoice",
	"POS Closing Entry": "retail.pos_realtime.RetailPOSClosingEntry",
}
doc_events["POS Invoice"]["on_submit"].append("retail.pos_realtime.post_invoice")
after_install.append("retail.loyalty_setup.install")
after_migrate.append("retail.loyalty_setup.install")
doc_events["Sales Invoice"]["validate"].append("retail.loyalty.validate_redemption")

# POS and Van Sales require both a module selection and a dedicated role.
auth_hooks = ["retail.module_access.guard_request"]
permission_query_conditions["*"] = "retail.module_access.query_conditions"
has_permission["*"] = "retail.module_access.has_permission"
for _event in ("validate", "before_submit", "before_cancel", "on_trash", "before_update_after_submit"):
	_existing = doc_events["*"].get(_event, [])
	if isinstance(_existing, str):
		_existing = [_existing]
	doc_events["*"][_event] = ["retail.module_access.validate_document", *_existing]
after_migrate.append("retail.module_access.install")
after_install.append("retail.module_access.install")

after_install.append("retail.company_bill_format.ensure_company_bill_format_fields")
after_migrate.append("retail.company_bill_format.ensure_company_bill_format_fields")

# Free goods must be normal document rows before ERPNext validates and posts.
for _foc_doctype in (
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
	"Sales Order",
	"Delivery Note",
	"Sales Invoice",
	"POS Invoice",
	"Stock Entry",
):
	_foc_events = doc_events[_foc_doctype]
	_before = _foc_events.get("before_validate", [])
	if isinstance(_before, str):
		_before = [_before]
	_foc_events["before_validate"] = [*_before, "retail.domains.foc.prepare_foc_items"]
	_validate = _foc_events.get("validate", [])
	if isinstance(_validate, str):
		_validate = [_validate]
	_foc_events["validate"] = [*_validate, "retail.domains.foc.validate_foc_items"]

# Classify the original receipt independently of its accounting lifecycle status.
doc_events["POS Invoice"]["validate"].append("retail.pos_transaction_display.set_transaction_type")
after_install.append("retail.pos_transaction_display.execute")

# POS list filters, totals, and closed-session dates.
after_install.append("retail.pos_list_settings.execute")
for _dt, _handler in {
	"POS Opening Entry": "retail.pos_list_settings.set_opening_summary",
	"POS Closing Entry": "retail.pos_list_settings.set_closing_summary",
}.items():
	doc_events.setdefault(_dt, {}).setdefault("validate", []).append(_handler)
for _event in ("on_submit", "on_cancel"):
	doc_events.setdefault("POS Closing Entry", {}).setdefault(_event, []).append(
		"retail.pos_list_settings.update_opening_end_date"
	)
for _dt in ("POS Profile", "POS Branch Counter"):
	doctype_list_js[_dt] = "public/js/list/pos_master_status.js"

after_migrate.append("retail.pos_list_settings.configure")

# Native Celesta access profiles and protected technical administration.
# Keep these last so they run before legacy permission/controller hooks.
has_permission["*"] = [has_permission["*"], "retail.access_control.has_permission"]
permission_query_conditions["*"] = [
	permission_query_conditions["*"],
	"retail.access_control.query_conditions",
]
auth_hooks.insert(0, "retail.access_control.guard_request")
for _event in ("before_validate", "validate", "before_save", "on_trash", "before_rename"):
	_existing = doc_events["*"].get(_event, [])
	if isinstance(_existing, str):
		_existing = [_existing]
	doc_events["*"][_event] = ["retail.access_control.validate_document", *_existing]
_existing_user_validate = doc_events["User"]["validate"]
if isinstance(_existing_user_validate, str):
	_existing_user_validate = [_existing_user_validate]
doc_events["User"]["validate"] = ["retail.access_control.prepare_super_user", *_existing_user_validate]
override_whitelisted_methods.update(
	{
		"frappe.desk.search.get_names_for_mentions": "retail.access_control.get_names_for_mentions",
		"frappe.core.doctype.user.user.reset_password": "retail.access_control.reset_password",
	}
)
boot_session.append("retail.access_control.boot_session")
after_install.append("retail.access_control.install")
after_migrate.append("retail.access_control.install")
for _access_doctype in ("User", "Employee"):
	_scripts = doctype_js.get(_access_doctype, [])
	if isinstance(_scripts, str):
		_scripts = [_scripts]
	doctype_js[_access_doctype] = [*_scripts, "public/js/forms/access_control.js"]

# Preserve native permission popups while directing users to the right support contact.
after_request = ["retail.permission_messages.after_request"]

# Audited branch-day revisions and payment-method corrections (native forms).
for _event in ("before_insert", "before_validate", "before_submit", "before_cancel", "on_trash"):
	_handlers = doc_events.setdefault("POS Branch Day Closing", {}).get(_event, [])
	if isinstance(_handlers, str):
		_handlers = [_handlers]
	doc_events["POS Branch Day Closing"][_event] = [
		*_handlers,
		"retail.pos_day_corrections.guard_day_document",
	]
for _dt in ("POS Invoice", "Sales Invoice"):
	for _event in ("before_validate", "before_cancel", "before_update_after_submit"):
		_handlers = doc_events.setdefault(_dt, {}).get(_event, [])
		if isinstance(_handlers, str):
			_handlers = [_handlers]
		doc_events[_dt][_event] = [*_handlers, "retail.pos_day_corrections.guard_corrected_document"]
doc_events["POS Invoice"].setdefault("before_submit", []).append("retail.pos_day_corrections.guard_sale_day")
after_install.append("retail.patches.setup_pos_day_corrections.execute")
after_migrate.append("retail.patches.setup_pos_day_corrections.execute")

doc_events.setdefault("POS Cashier Shift", {}).setdefault("before_validate", []).append(
	"retail.pos_day_corrections.guard_closed_shift"
)

# Native collection corrections retain cancellation/amendment history.
for _event in ("before_validate", "before_submit", "before_cancel", "before_update_after_submit", "on_trash"):
	_handlers = doc_events.setdefault("Payment Entry", {}).get(_event, [])
	if isinstance(_handlers, str):
		_handlers = [_handlers]
	doc_events["Payment Entry"][_event] = [*_handlers, "retail.pos_settlement_corrections.guard_payment"]

# Selected license seats and emergency recovery.
has_permission["Celesta License Settings"] = "retail.licensing.client.has_permission"

# Enforce license validity and assigned seats at login only for now.
# Existing sessions and API requests must not revalidate licensing.
on_login = "retail.licensing.enforcement.on_login"
on_session_creation = "retail.licensing.enforcement.on_session_creation"
# Restrict only invalid-license repair admissions; never revalidate normal requests.
auth_hooks.insert(0, "retail.licensing.enforcement.guard_request")

# Refresh signed entitlements independently of login and billing requests.
scheduler_events.setdefault("hourly", []).append("retail.licensing.client.scheduled_sync")

# Durable completed POS acceptance and native accounting settlement recovery.
scheduler_events.setdefault("cron", {}).setdefault("*/5 * * * *", []).append("retail.pos_settlements.recover")

# Additive Retail sidebar capabilities. Hooks are scoped to explicit HTTP
# targets, so linked-document checks and internal posting keep native behavior.
auth_hooks.append("retail.sidebar_permissions.guard_request")
before_job = ["retail.sidebar_permissions.before_job"]
boot_session.append("retail.sidebar_permissions.boot")
after_install.append("retail.sidebar_permissions.install")
after_migrate.append("retail.sidebar_permissions.install")

# Installation fixtures/customizations sync after after_install in Frappe v15.
after_sync.append("retail.auto_repeat_setup.install")
after_migrate.append("retail.auto_repeat_setup.install")
doctype_js["User"].append("public/js/forms/sidebar_permissions.js")
doc_events["User"]["validate"].append("retail.sidebar_permissions.validate_user")
doc_events["User"].setdefault("on_update", []).append("retail.sidebar_permissions.user_updated")
for _sidebar_event in (
	"before_validate",
	"before_save",
	"before_submit",
	"before_cancel",
	"on_trash",
	"before_update_after_submit",
):
	doc_events["*"].setdefault(_sidebar_event, []).append("retail.sidebar_permissions.validate_document")
from retail.sidebar_registry import entries

_sidebar_doctypes = {
	target for _entry in entries() for _kind, target in _entry["targets"] if _kind == "doctype"
}
for _sidebar_dt in _sidebar_doctypes:
	for _mapping, _handler in (
		(has_permission, "retail.sidebar_permissions.has_permission"),
		(permission_query_conditions, "retail.sidebar_permissions.query_conditions"),
	):
		_current = _mapping.get(_sidebar_dt, [])
		if isinstance(_current, str):
			_current = [_current]
		_mapping[_sidebar_dt] = [*_current, _handler]

# Frappe v15 imports fixtures/customizations between after_install and after_sync.
# Run the existing setup only once those fields and workspace records exist.
after_sync = [
	"retail.build_asset_manifest.install",
	"retail.install.ensure_workspace_routes",
	*after_install,
	*after_sync,
]
after_install = ["retail.install.prepare_fixture_doctypes"]
after_migrate.append("retail.install.ensure_workspace_routes")

# New sites skip migration patches; posting schema must also survive fixture sync.
after_sync.append("retail.pos_sync_schema.install")
after_migrate.append("retail.pos_sync_schema.install")

# Keep native list configuration, with additional column-count choices.
after_sync.append("retail.list_view_columns.install")
after_migrate.append("retail.list_view_columns.install")

# Former core customizations are owned and installed by Retail.
override_doctype_class["Report"] = "retail.core_compat.reports.RetailReport"
override_whitelisted_methods["frappe.desk.query_report.get_script"] = "retail.core_compat.reports.get_script"
before_request = ["retail.core_compat.runtime.install"]
before_job.append("retail.core_compat.runtime.install")
after_sync.append("retail.core_compat.setup.install")
after_migrate.append("retail.core_compat.setup.install")

# Display warehouse titles while retaining native stock-value calculations.
override_whitelisted_methods["erpnext.stock.dashboard_chart_source.warehouse_wise_stock_value.warehouse_wise_stock_value.get"] = "retail.chart_labels.warehouse_stock_value"

# Seed once so subsequent Customize Form choices survive migrations.
after_sync.append("retail.item_quick_entry.install")
after_migrate.append("retail.item_quick_entry.install")

# Preserve transaction display facts without changing ERPNext-owned fields.
after_sync.append("retail.transaction_identity.install")
after_migrate.append("retail.transaction_identity.install")
for _identity_doctype in ("Sales Invoice", "POS Invoice", "Delivery Note",
                          "Purchase Invoice", "Purchase Receipt", "Stock Entry"):
    _identity_handlers = doc_events.setdefault(_identity_doctype, {}).get("before_submit", [])
    if isinstance(_identity_handlers, str):
        _identity_handlers = [_identity_handlers]
    doc_events[_identity_doctype]["before_submit"] = [
        *_identity_handlers, "retail.transaction_identity.snapshot_document",
    ]

# Record promotion master revisions and audit POS evidence without changing totals.
after_migrate.append("retail.promotions.history.install")
after_sync.append("retail.promotions.history.install")
for _promotion_type in ("Promo Price", "Buy X Get Y Promotion", "Gift Voucher Promotion"):
    _revision_handlers = doc_events.setdefault(_promotion_type, {}).get("on_update", [])
    if isinstance(_revision_handlers, str):
        _revision_handlers = [_revision_handlers]
    doc_events[_promotion_type]["on_update"] = [*_revision_handlers, "retail.promotions.history.record_revision"]
doc_events["POS Invoice"].setdefault("before_submit", []).append("retail.promotions.history.capture")

# Client administrators delegate only their own assigned access to managed staff.
override_whitelisted_methods.update({
    "frappe.core.doctype.user.user.get_all_roles": "retail.delegated_access.get_all_roles",
    "frappe.core.doctype.user.user.get_perm_info": "retail.delegated_access.get_perm_info",
})
doc_events["User"].setdefault("onload", []).append("retail.delegated_access.onload")
doc_events["User"]["validate"].append("retail.delegated_access.validate_manager")
doc_events["User"].setdefault("on_update", []).append("retail.delegated_access.sync_children")
after_sync.append("retail.delegated_access.install")
after_migrate.append("retail.delegated_access.install")

# Keep scale-derived quantities and rates precise within the sales document.
for _scale_sales_type in ("Sales Invoice", "POS Invoice", "Sales Order", "Delivery Note", "Quotation"):
    _scale_handlers = doc_events.setdefault(_scale_sales_type, {}).get("before_validate", [])
    if isinstance(_scale_handlers, str):
        _scale_handlers = [_scale_handlers]
    doc_events[_scale_sales_type]["before_validate"] = [
        *_scale_handlers, "retail.domains.item.scale_sales.prepare_precision",
    ]

# Existing POS profile selection never grants profile-document administration.
override_whitelisted_methods["frappe.client.validate_link"] = "retail.pos_privileges.validate_profile_link"

# Live ledger balances and readable loyalty document titles.
doctype_js["Loyalty Point Entry"] = "public/js/loyalty_entry_display.js"
doctype_list_js["Loyalty Point Entry"] = "public/js/loyalty_entry_display.js"
after_sync.append("retail.loyalty_display.install")
after_migrate.append("retail.loyalty_display.install")

# Retail promotional card batches: additive schema, navigation and print helpers.
after_migrate.append("retail.voucher_cards.install")
after_sync.append("retail.voucher_cards.install")
jinja["methods"].append("retail.voucher_cards.voucher_card_print_data")

# Series selection is internal for documents numbered by Retail.
after_migrate.append("retail.short_codes.hide_naming_series")

# Native serial/batch fields directly in purchase item grids.
for _warehouse_dt in ("Sales Order", "Delivery Note", "Purchase Order", "Purchase Receipt", "Purchase Invoice", "Sales Invoice"):
	_scripts = doctype_js[_warehouse_dt]
	if isinstance(_scripts, str):
		_scripts = [_scripts]
	doctype_js[_warehouse_dt] = [*_scripts, "public/js/forms/default_warehouse.js"]

for _purchase_identity_dt in ("Purchase Invoice", "Purchase Receipt"):
	doctype_js[_purchase_identity_dt].append("public/js/forms/purchase_stock_identity.js")

# Item/serial/batch lookup on these lists, without overriding core endpoints.
for _item_filter_dt in ("POS Invoice", "Sales Invoice", "Purchase Order", "Purchase Invoice", "Purchase Receipt"):
	_scripts = doctype_list_js.get(_item_filter_dt, [])
	if isinstance(_scripts, str):
		_scripts = [_scripts]
	doctype_list_js[_item_filter_dt] = [*_scripts, "public/js/list/document_item_filters.js"]
	_conditions = permission_query_conditions.get(_item_filter_dt, [])
	if isinstance(_conditions, str):
		_conditions = [_conditions]
	permission_query_conditions[_item_filter_dt] = [*_conditions, "retail.document_item_filters.query_conditions"]
