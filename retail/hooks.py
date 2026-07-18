app_name = "retail"
app_title = "Retail"
app_publisher = "Arab Scale"
app_description = "Retail Application"
app_email = "akshayagopal1@gmail.com"
app_license = "mit"
app_logo_url = "/assets/retail/images/celesta-app-icon.svg"

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

app_include_css = [
    "/assets/retail/css/retail_icons.css?v=23",
    "/assets/retail/css/brand_themes.css?v=14",
    "/assets/retail/css/workspace_glass.css?v=5",
]

app_include_js = [
    "/assets/retail/js/retail_navigation.js?v=76",
    "/assets/retail/js/local_draft_recovery.js?v=12",
    "/assets/retail/js/forms/transaction_items.js?v=12",
    "/assets/retail/js/brand_theme_switcher.js?v=8",
    "/assets/retail/js/reports/gross_profit_item_filter.js?v=1",
]

# include js, css files in header of web template
web_include_css = [
    "/assets/retail/css/brand_themes.css?v=11",
    "/assets/retail/css/website_branding.css?v=13",
]

web_include_js = [
    "/assets/retail/js/website_branding.js?v=2",
]

website_context = {
    "brand_html": '<img src="/assets/retail/images/celesta-app-icon.svg?v=1" class="retail-web-brand-icon" alt="Celesta"><span class="retail-web-brand">CELESTA</span>',
    "favicon": "/assets/retail/images/celesta-app-icon.svg?v=1",
    "splash_image": "/assets/retail/images/retail-logo.svg?v=2",
}

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
	],
	"Purchase Invoice": "public/js/hide_transaction_id_list.js",
	"Sales Order": "public/js/hide_transaction_id_list.js",
	"Purchase Order": "public/js/hide_transaction_id_list.js",
	"Delivery Note": "public/js/hide_transaction_id_list.js",
	"Purchase Receipt": "public/js/hide_transaction_id_list.js",
	"Stock Entry": "public/js/hide_transaction_id_list.js",
	"Material Request": "public/js/hide_transaction_id_list.js",
	"Customer": "public/js/hide_transaction_id_list.js",
	"Item": "public/js/hide_transaction_id_list.js",
	"Supplier": "public/js/hide_transaction_id_list.js",
	"Serial and Batch Bundle": "public/js/hide_transaction_id_list.js",
	"Bin": "public/js/hide_transaction_id_list.js",
	"Sales Taxes and Charges Template": "public/js/hide_transaction_id_list.js",
	"Counter": "public/js/hide_transaction_id_list.js",
}
doctype_js = {
	"Item": "public/js/forms/item.js",
	"Item Price": "public/js/forms/item_price_rate_update.js",
	"Retail Item Rate Audit": "public/js/forms/retail_item_rate_audit.js",
	"Purchase Order": "public/js/forms/foc_qty.js",
	"Purchase Receipt": [
		"public/js/forms/foc_qty.js",
		"public/js/forms/purchase_selling_price.js",
	],
	"Purchase Invoice": [
		"public/js/forms/foc_qty.js",
		"public/js/forms/purchase_selling_price.js",
	],
	"Sales Order": "public/js/forms/foc_qty.js",
	"Delivery Note": "public/js/forms/foc_qty.js",
	"Sales Invoice": "public/js/forms/sales_invoice.js",
	"POS Invoice": "public/js/forms/foc_qty.js",
	"Stock Entry": "public/js/forms/foc_qty.js",
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
after_install = "retail.naming.install_retail_defaults"

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

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

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
	"Purchase Order": {
		"validate": [
			"retail.domains.foc.apply_foc_quantities",
			"retail.domains.transactions.vat.set_vat_rates",
			"retail.domains.purchase.order.set_balance_qty",
		],
		"on_submit": "retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
		"on_cancel": "retail.domains.item.item_price_sync.recalculate_transaction_item_prices",
		"on_update_after_submit": "retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
	},
	"Purchase Receipt": {
		"before_naming": "retail.naming.set_transaction_naming_series",
		"validate": [
			"retail.domains.foc.apply_foc_quantities",
			"retail.domains.transactions.vat.set_vat_rates",
			"retail.domains.purchase.selling_price.set_selling_price_margins",
		],
		"on_submit": [
			"retail.domains.foc.add_foc_stock_ledger_entries",
			"retail.domains.purchase.order.sync_balance_qty_from_transaction",
			"retail.domains.item.average_purchase_rate.sync_average_purchase_rates",
			"retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
			"retail.domains.purchase.selling_price.update_selected_selling_prices",
		],
		"on_cancel": [
			"retail.domains.purchase.order.sync_balance_qty_from_transaction",
			"retail.domains.item.average_purchase_rate.sync_average_purchase_rates",
			"retail.domains.item.item_price_sync.recalculate_transaction_item_prices",
		],
		"on_update_after_submit": [
			"retail.domains.purchase.order.sync_balance_qty_from_transaction",
			"retail.domains.item.average_purchase_rate.sync_average_purchase_rates",
			"retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
		],
	},
	"Purchase Invoice": {
		"before_naming": "retail.naming.set_transaction_naming_series",
		"before_validate": "retail.domains.transactions.stock.set_update_stock_for_standalone_invoice",
		"validate": [
			"retail.domains.foc.apply_foc_quantities",
			"retail.domains.transactions.vat.set_vat_rates",
			"retail.domains.purchase.selling_price.set_selling_price_margins",
		],
		"on_submit": [
			"retail.domains.foc.add_foc_stock_ledger_entries",
			"retail.domains.purchase.order.sync_balance_qty_from_transaction",
			"retail.domains.item.average_purchase_rate.sync_average_purchase_rates",
			"retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
			"retail.domains.purchase.selling_price.update_selected_selling_prices",
		],
		"on_cancel": [
			"retail.domains.purchase.order.sync_balance_qty_from_transaction",
			"retail.domains.item.average_purchase_rate.sync_average_purchase_rates",
			"retail.domains.item.item_price_sync.recalculate_transaction_item_prices",
		],
		"on_update_after_submit": [
			"retail.domains.purchase.order.sync_balance_qty_from_transaction",
			"retail.domains.item.average_purchase_rate.sync_average_purchase_rates",
			"retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
		],
	},
    "Item": {
		"before_naming": "retail.domains.item.naming.set_automatic_item_code",
		"validate": [
			"retail.domains.item.packing_sync.sync_uoms_and_barcodes",
			"retail.domains.item.vat_pricing.update_item_vat_prices",
		],
        "on_update": [
			"retail.domains.item.item_price_sync.sync_simple_item_prices",
			"retail.domains.item.average_purchase_rate.sync_average_purchase_rate_from_item",
			"retail.domains.item.rate_audit.audit_item_master_rate_change",
        ],
    },
	"Item Price": {
		"on_update": "retail.domains.item.item_price_sync.sync_item_master_purchase_rate_from_item_price",
	},
	"Sales Invoice": {
		"before_naming": "retail.naming.set_transaction_naming_series",
		"before_validate": "retail.domains.transactions.stock.set_update_stock_for_standalone_invoice",
		"validate": [
			"retail.domains.foc.apply_foc_quantities",
			"retail.domains.transactions.vat.set_vat_rates",
			"retail.domains.sales.counter.set_sales_invoice_counter_name",
			"retail.domains.sales.invoice_totals.apply_retail_shipping_charges",
			"retail.api.pos_sync.validate_external_reference",
			"retail.api.pos_sync.block_external_sales_invoice",
		],
		"on_submit": [
			"retail.domains.foc.add_foc_stock_ledger_entries",
			"retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
		],
		"on_cancel": "retail.domains.item.item_price_sync.recalculate_transaction_item_prices",
		"on_update_after_submit": "retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
	},
	"POS Invoice": {
		"validate": [
			"retail.domains.foc.apply_foc_quantities",
			"retail.domains.transactions.vat.set_vat_rates",
			"retail.api.pos_sync.validate_external_reference",
		],
		"on_submit": [
			"retail.domains.foc.add_foc_stock_ledger_entries",
			"retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
		],
		"on_cancel": "retail.domains.item.item_price_sync.recalculate_transaction_item_prices",
		"on_update_after_submit": "retail.domains.item.item_price_sync.sync_latest_transaction_item_prices",
    },
    "Delivery Note": {
		"before_naming": "retail.naming.set_transaction_naming_series",
		"validate": [
			"retail.domains.foc.apply_foc_quantities",
			"retail.domains.transactions.vat.set_vat_rates",
		],
		"on_submit": [
			"retail.domains.foc.add_foc_stock_ledger_entries",
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
		"validate": "retail.domains.transactions.vat.set_vat_rates",
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
		"validate": "retail.domains.foc.apply_foc_quantities",
		"on_submit": "retail.domains.foc.add_foc_stock_ledger_entries",
	},
	"Payment Entry": {
		"before_naming": "retail.naming.set_transaction_naming_series",
		"validate": "retail.api.pos_sync.validate_external_reference",
	},
	"Journal Entry": {
		"before_naming": "retail.naming.set_transaction_naming_series",
	},
}

after_migrate = [
	"retail.branding.apply_default_branding",
	"retail.setup.hide_non_retail_workspaces",
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
	"retail.domains.item.vat_pricing.ensure_item_vat_pricing_fields",
	"retail.domains.item.rate_audit.ensure_rate_audit_setup",
	"retail.domains.item.vat_pricing.backfill_item_master_last_purchase_rates",
	"retail.domains.sales.invoice_totals.ensure_all_transaction_totals_fields",
	"retail.domains.purchase.selling_price.ensure_purchase_selling_price_fields",
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
	"frappe.desk.query_report.run": "retail.retail_app.report.stock_movement_utils.run_query_report",
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

fixtures = [
    {
        "dt": "DocType",
        "filters": [
            ["name", "in", ("Counter",)]
        ],
    },
    "Custom Field",
    "Client Script",
    "Server Script",
    {
        "dt": "Print Format",
        "filters": [
            [
                "name",
                "in",
                (
                    "ppppppppppppppppppppp",
                ),
            ]
        ],
    },
    {
        "dt": "Letter Head",
        "filters": [
            [
                "name",
                "in",
                (
                    "Arab Scale Letter Head - Standard",
                ),
            ]
        ],
    },
    "Property Setter",
    "List View Settings",
    "Custom DocPerm",
    "Workflow",
    "Workflow State",
    "Workflow Action Master",
    {
        "dt": "Page",
        "filters": [
            [
                "name",
                "in",
                (
                    "retail-item-family-l",
                ),
            ]
        ],
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
    {
        "dt": "Workspace",
        "filters": [
            [
                "name",
                "in",
                (
                    "Accounts",
                    "Accounts Payable",
                    "Accounts Receivable",
                    "Bank Accounts",
                    "Branding",
                    "Brands",
                    "Business Profile",
                    "Customers",
                    "Delivery Notes",
                    "Home",
                    "Item Groups",
                    "Item Family List",
                    "Items",
                    "Items List",
                    "Journal Entries",
                    "Manufacturing",
                    "Manufacturing Reports",
                    "Manufacturing Setup",
                    "Material Requests",
                    "MFG BOM",
                    "MFG Job Cards",
                    "MFG Production Plan",
                    "MFG Quality Inspection",
                    "MFG Reports",
                    "MFG Setup",
                    "MFG Stock Entries",
                    "MFG Work Orders",
                    "Payments",
                    "Price Lists",
                    "Purchase Invoices",
                    "Purchase Orders",
                    "Purchase Receipts",
                    "Purchase Returns",
                    "Purchases",
                    "POS",
                    "POS Branch Day Closings",
                    "POS Cashier Shifts",
                    "POS Closing Entries",
                    "POS Counter Sessions",
                    "POS Counters",
                    "POS Invoices",
                    "POS Opening Entries",
                    "POS Profiles",
                    "POS Reports",
                    "POS Sync Logs",
                    "Reports",
                    "Sales",
                    "Sales Invoices",
                    "Sales Orders",
                    "Sales Returns",
                    "Serials & Batches",
                    "Settings",
                    "Stock Adjustments",
                    "Stock Status",
                    "Stock Take",
                    "Stocks",
                    "Suppliers",
                    "System Rules",
                    "Taxes",
                    "Warehouses",
                ),
            ]
        ],
    },
]
# app_include_js = "/assets/retail/js/retail_navigation.js?v=15"
