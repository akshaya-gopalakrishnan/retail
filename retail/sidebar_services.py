"""Explicit capabilities for RPC services which are not native document APIs."""
from functools import lru_cache

import frappe

TRANSACTIONS = ("Sales Invoice", "POS Invoice", "Sales Order", "Quotation", "Delivery Note",
                "Purchase Order", "Purchase Receipt", "Purchase Invoice", "Supplier Quotation",
                "Stock Entry", "Stock Reconciliation", "Payment Entry", "Material Request")
LINK_HELPERS = {
    "retail.domains.item.vat_pricing.get_item_tax_rate": "Item",
    "retail.domains.transactions.vat.get_transaction_item_vat_rate": "Item",
    "retail.domains.item.packing_scan.scan_barcode": "Item",
    "erpnext.stock.utils.scan_barcode": "Item",
    "erpnext.stock.get_item_details.get_item_tax_template": "Item",
    "erpnext.stock.get_item_details.get_conversion_factor": "Item",
    "erpnext.stock.get_item_details.get_batch_based_item_price": "Item",
    "erpnext.stock.get_item_details.apply_price_list": "Item",
    "erpnext.stock.get_item_details.get_item_tax_info": "Item",
    "erpnext.stock.get_item_details.get_item_tax_map": "Item",
    "erpnext.stock.get_item_details.get_blanket_order_details": "Item",
    "erpnext.stock.utils.get_incoming_rate": "Item",
    "erpnext.stock.doctype.stock_settings.stock_settings.get_enable_stock_uom_editing": None,
    "erpnext.controllers.accounts_controller.get_default_taxes_and_charges": None,
    "erpnext.controllers.accounts_controller.get_taxes_and_charges": None,
    "erpnext.controllers.accounts_controller.get_payment_terms": None,
    "erpnext.controllers.accounts_controller.get_payment_term_details": None,
    "erpnext.accounts.doctype.accounting_dimension.accounting_dimension.get_dimensions": None,
    "erpnext.accounts.party.get_party_details": None,
    "erpnext.accounts.party.get_party_account": None,
    "erpnext.accounts.party.get_due_date": None,
    "erpnext.setup.utils.get_exchange_rate": None,
    "erpnext.controllers.taxes_and_totals.get_round_off_applicable_accounts": "Account",
    "erpnext.controllers.taxes_and_totals.get_rounding_tax_settings": None,
    "erpnext.setup.doctype.company.company.get_default_company_address": "Company",
    "frappe.contacts.doctype.address.address.get_address_display": "Address",
}
LINK_FIELDS = {
    "Customer": {"name", "customer_name", "customer_group", "territory", "default_currency", "default_price_list",
                 "tax_category", "is_internal_customer", "represents_company"},
    "Supplier": {"name", "supplier_name", "supplier_group", "default_currency", "default_price_list", "tax_category"},
    "Item": {"name", "item_name", "stock_uom", "is_stock_item", "has_batch_no", "has_serial_no", "disabled",
             "is_sales_item", "is_purchase_item", "item_group", "brand"},
    "Company": {"name", "default_currency", "default_receivable_account", "default_payable_account",
                "default_income_account", "cost_center", "round_off_account", "round_off_cost_center"},
    "Warehouse": {"name", "company", "is_group", "disabled"},
    "Account": {"name", "account_currency", "account_type", "company", "is_group"},
    "Stock Settings": {"sample_retention_warehouse"},
}


def authorize_link_service(command, form):
    """Narrow native lookup/calculation dependencies of selected transactions.

    These return link facts or calculated draft values, never a full denied
    document, arbitrary fields, or authority to change a linked record.
    """
    from retail.sidebar_permissions import target_allowed, deny
    eligible = lambda: any(target_allowed("doctype", dt) and frappe.has_permission(dt, "read") for dt in (*TRANSACTIONS, "Item"))
    if command == "frappe.desk.reportview.get_list" and form.get("doctype") == "Party Type":
        filters = frappe.parse_json(form.get("filters")) or {}
        fields = frappe.parse_json(form.get("fields")) or ["name"]
        report = {"Receivable": "Accounts Receivable", "Payable": "Accounts Payable"}.get(
            filters.get("account_type") if isinstance(filters, dict) else None)
        if (not report or filters != {"account_type": filters["account_type"]} or fields != ["name"] or
                not (target_allowed("report", report) or widget_report_allowed(report)) or
                not frappe.has_permission("Party Type", "read") or
                any(form.get(key) for key in ("doc", "docs", "document"))):
            deny()
        return True  # Native report filter options, never party/customer records.
    if command == "frappe.client.get_value" and form.get("doctype") == "Report":
        fields = form.get("fieldname") or "name"
        try:
            fields = frappe.parse_json(fields) if isinstance(fields, str) else fields
        except ValueError:
            pass
        fields = [fields] if isinstance(fields, str) else fields
        try:
            filters = frappe.parse_json(form.get("filters"))
        except ValueError:
            filters = form.get("filters")
        if isinstance(filters, str):
            filters = {"name": filters}
        name = filters.get("name") if isinstance(filters, dict) else None
        if (not isinstance(fields, list) or not set(fields).issubset({"name", "ref_doctype", "report_type"}) or
                not isinstance(filters, dict) or set(filters) != {"name"} or not isinstance(name, str) or
                any(form.get(key) for key in ("doc", "docs", "document"))):
            deny()
        if not target_allowed("report", name) and not widget_report_allowed(name):
            deny()
        return True  # Only report routing metadata; native get_value checks read.
    if command == "frappe.client.get_single_value" and form.get("doctype") == "LDAP Settings":
        # Native User refresh reads this flag to display its LDAP button.
        # Keep the Administrator's own recovery form usable as well.
        if (form.get("field") != "enabled" or
                any(form.get(key) for key in ("doc", "docs", "document")) or
                not (frappe.session.user == "Administrator" or target_allowed("doctype", "User")) or
                not frappe.has_permission("User", "read") or
                not frappe.has_permission("LDAP Settings", "read")):
            deny()
        return True  # Native get_single_value still checks LDAP read permission.
    if command == "frappe.client.get_single_value" and form.get("doctype") == "Stock Settings":
        if form.get("field") != "disable_serial_no_and_batch_selector" or not eligible():
            deny()
        return True  # Native get_single_value retains its own read permission check.
    if command in LINK_HELPERS:
        if not eligible():
            deny()
        dependency = LINK_HELPERS[command] or form.get("party_type")
        if dependency and not (frappe.has_permission(dependency, "select") or frappe.has_permission(dependency, "read")):
            deny()
        return True
    if command == "frappe.client.get_value" and form.get("doctype") in LINK_FIELDS and not target_allowed("doctype", form["doctype"]):
        fields = form.get("fieldname") or "name"
        try:
            fields = frappe.parse_json(fields) if isinstance(fields, str) else fields
        except ValueError:
            pass
        fields = [fields] if isinstance(fields, str) else fields
        try:
            filters = frappe.parse_json(form.get("filters"))
        except ValueError:
            filters = form.get("filters")
        if isinstance(filters, str):
            filters = {"name": filters}
        if (not eligible() or not isinstance(fields, list) or not set(fields).issubset(LINK_FIELDS[form["doctype"]])
                or not isinstance(filters, dict) or set(filters) != {"name"} or not isinstance(filters["name"], str)
                or not (frappe.has_permission(form["doctype"], "select") or frappe.has_permission(form["doctype"], "read"))):
            deny()
        return True
    return False

# (menu workspace identity, native DocType, required actions)
POS_SERVICES = {
    "health_check": ("POS Invoices", "POS Invoice", ("read",)),
    "get_pos_master_data": ("POS Invoices", "POS Invoice", ("read",)),
    "get_pos_promo_prices": ("POS Invoices", "POS Invoice", ("read",)),
    "get_pos_buy_x_get_y_promotions": ("POS Invoices", "POS Invoice", ("read",)),
    "get_pos_loyalty_programs": ("POS Invoices", "POS Invoice", ("read",)),
    "get_warehouse_stock_snapshot": ("POS Invoices", "POS Invoice", ("read",)),
    "create_pos_invoice": ("POS Invoices", "POS Invoice", ("create", "submit")),
    "create_pos_sales_invoice": ("Sales Invoices", "Sales Invoice", ("create", "submit")),
    "create_credit_pos_invoice": ("Sales Invoices", "Sales Invoice", ("create", "submit")),
    "create_pos_return_invoice": ("POS Invoices", "POS Invoice", ("create", "submit")),
    "create_pos_payment_entry": ("Payments", "Payment Entry", ("create", "submit")),
    "create_customer_deposit": ("Payments", "Payment Entry", ("create", "submit")),
    "pay_customer_invoice": ("Payments", "Payment Entry", ("create", "submit")),
    "get_customer_balances": ("Customers", "Customer", ("read",)),
    "upsert_customer": ("Customers", "Customer", ("create", "write")),
    "get_sync_status": ("POS Sync Logs", "POS Sync Log", ("read",)),
    "get_queue_dependencies": ("POS Sync Logs", "POS Sync Log", ("read",)),
    "ingest_queue_errors": ("POS Sync Logs", "POS Sync Log", ("create",)),
    "set_cashier_quick_pin": ("POS Cashier Shifts", "POS Cashier Shift", ("write",)),
    "verify_cashier_quick_pin": ("POS Cashier Shifts", "POS Cashier Shift", ("read",)),
    "get_cashier_shift_status": ("POS Cashier Shifts", "POS Cashier Shift", ("read",)),
    "open_cashier_shift": ("POS Cashier Shifts", "POS Cashier Shift", ("create",)),
    "pause_cashier_shift": ("POS Cashier Shifts", "POS Cashier Shift", ("write",)),
    "resume_cashier_shift": ("POS Cashier Shifts", "POS Cashier Shift", ("write",)),
    "close_cashier_shift": ("POS Cashier Shifts", "POS Cashier Shift", ("write",)),
    "reopen_cashier_shift": ("POS Cashier Shifts", "POS Cashier Shift", ("write",)),
    "create_pos_cash_movement": ("POS Cashier Shifts", "POS Cashier Shift", ("write",)),
    "open_pos_shift": ("POS Opening Entries", "POS Opening Entry", ("create", "submit")),
    "close_pos_shift": ("POS Closing Entries", "POS Closing Entry", ("create", "submit")),
    "make_branch_day_closing": ("POS Branch Day Closings", "POS Branch Day Closing", ("create",)),
    "cancel_branch_day_closing": ("POS Branch Day Closings", "POS Branch Day Closing", ("cancel",)),
    "submit_branch_day_closing": ("POS Branch Day Closings", "POS Branch Day Closing", ("submit",)),
}


@lru_cache(maxsize=1)
def _workspace_definitions():
    """Cache only static fixture definitions, never a user's permissions."""
    import json
    from pathlib import Path

    workspaces = {}
    for path in sorted((Path(__file__).parent / "retail_app/workspace").glob("*/*.json")):
        workspace = json.loads(path.read_text())
        if workspace.get("name") in workspaces:
            continue
        definitions = {}
        for kind, table, field in (("Dashboard Chart", "charts", "chart_name"),
                                   ("Number Card", "number_cards", "number_card_name")):
            definitions[kind] = frozenset(row[field] for row in workspace.get(table, []) if row.get(field))
        definitions["count"] = frozenset(row["link_to"] for row in workspace.get("shortcuts", [])
                                         if row.get("type") == "DocType" and row.get("link_to"))
        workspaces[workspace.get("name")] = definitions
    return workspaces


def workspace_dependencies():
    """Trusted widget and shortcut definitions for the selected Retail menus."""
    from retail.sidebar_permissions import selection
    from retail.sidebar_registry import entries

    selected = selection()
    workspaces = {entry["workspace"] for entry in entries() if selected is None or entry["id"] in selected}
    definitions = {"Dashboard Chart": set(), "Number Card": set(), "count": set()}
    for name, workspace in _workspace_definitions().items():
        if name in workspaces:
            for kind in definitions:
                definitions[kind].update(workspace[kind])
    return definitions


def widget_report_allowed(name):
    """A selected workspace may load the report used by its stored widget."""
    definitions = workspace_dependencies()
    return any(frappe.get_cached_doc(kind, widget).get("report_name") == name and
               frappe.has_permission(kind, "read", doc=widget)
               for kind in ("Dashboard Chart", "Number Card") for widget in definitions[kind])


def authorize_service(command, form):
    if command == "retail.domains.transactions.vat.get_transaction_vat_tax_rows":
        from retail.sidebar_permissions import require_document, deny
        doc = frappe.get_doc(frappe.parse_json(form.get("doc")))
        require_document(doc)
        if not frappe.has_permission(doc.doctype, "read"):
            deny()
        return True
    from retail.sidebar_permissions import enabled, require_target, target_allowed, deny
    from retail.sidebar_registry import entries

    def capability(workspace, doctype=None, actions=("read",)):
        entry = next((entry for entry in entries() if entry["workspace"] == workspace), None)
        if not entry or not enabled(entry["id"]):
            deny()
        if doctype and any(not frappe.has_permission(doctype, action) for action in actions):
            deny()
        return True

    if command == "retail.document_codes.ensure_codes":
        # Lists initialize their existing public codes through this helper.
        # It must follow the selected list, never authorize another DocType.
        doctype = form.get("doctype")
        require_target("doctype", doctype)
        if not frappe.has_permission(doctype, "read"):
            deny()
        return True  # The service retains its configured-type/read checks.

    if command.startswith("retail.api.pos_sync."):
        function = command.rsplit(".", 1)[1]
        rule = POS_SERVICES.get(function)
        if function == "get_pos_master_data":
            for doctype in ("Item", "Item Price", "Customer", "Warehouse", "Company", "POS Profile", "POS Branch Counter", "Employee"):
                if not frappe.has_permission(doctype, "read"):
                    deny()
        return capability(*rule) if rule else False
    if command == "retail.sidebar_permissions.get_editor":
        # The endpoint itself requires the protected administrator identity.
        return True
    if command == "erpnext.stock.dashboard_chart_source.warehouse_wise_stock_value.warehouse_wise_stock_value.get":
        charts = workspace_dependencies()["Dashboard Chart"]
        supplied = frappe.parse_json(form.get("chart")) or {}
        name = form.get("chart_name") or supplied.get("name")
        if (name not in charts or frappe.get_cached_doc("Dashboard Chart", name).get("source") != "Warehouse wise Stock Value" or
                not frappe.has_permission("Dashboard Chart", "read", doc=name)):
            deny()
        if not frappe.has_permission("Warehouse", "read") or not frappe.has_permission("Bin", "read"):
            deny()
        return True  # The source uses native permission-filtered Warehouse/Bin lists.
    if command in ("retail.domains.item.margin_cost.get_stock_margin_cost",
                   "retail.domains.item.arabic_name.translate_item_name_to_arabic",
                   "erpnext.stock.dashboard.item_dashboard.get_data"):
        require_target("doctype", "Item")
        if not frappe.has_permission("Item", "read", doc=form.get("item_code")):
            deny()
        if command.endswith("item_dashboard.get_data") and not frappe.has_permission("Bin", "read"):
            deny()
        return True
    if command == "erpnext.accounts.doctype.unreconcile_payment.unreconcile_payment.doc_has_references":
        from retail.sidebar_permissions import require_document
        dt = form.get("doctype")
        name = form.get("docname")
        require_target("doctype", dt)
        if not name or not frappe.has_permission(dt, "read", doc=name):
            deny()
        require_document(frappe.get_doc(dt, name))
        return True
    if command in ("frappe.client.get", "frappe.desk.form.load.getdoc") and form.get("doctype") in ("Dashboard Chart", "Number Card"):
        kind, name = form["doctype"], form.get("name")
        if (name not in workspace_dependencies()[kind] or
                any(form.get(key) for key in ("doc", "docs", "document")) or
                not frappe.has_permission(kind, "read", doc=name)):
            deny()
        return True  # Native definition reads still check their own permissions.
    if command in (
        "retail.retail_app.report.low_stock_reorder_report.low_stock_reorder_report.get_low_stock_items_count",
        "retail.retail_app.report.low_stock_reorder_report.low_stock_reorder_report.get_out_of_stock_items_count",
    ):
        if not frappe.has_permission("Item", "read") or not frappe.has_permission("Bin", "read"):
            deny()
        if not (enabled("workspace:business_home") or enabled("workspace:items")):
            deny()
        return True
    if command == "frappe.desk.doctype.dashboard_chart_source.dashboard_chart_source.get_config":
        sources = {frappe.get_cached_doc("Dashboard Chart", name).get("source")
                   for name in workspace_dependencies()["Dashboard Chart"]
                   if frappe.has_permission("Dashboard Chart", "read", doc=name)}
        if not form.get("name") or form["name"] not in sources:
            deny()
        return True
    if command == "retail.retail_app.page.retail_item_family_l.retail_item_family_l.get_rows":
        return capability("Item Family List", "Item")
    if command in ("retail.loyalty.get_available_points", "retail.loyalty.get_return_preview"):
        permitted = any(frappe.has_permission(dt, "read") and target_allowed("doctype", dt)
                        for dt in ("Sales Invoice", "POS Invoice"))
        if not permitted:
            deny()
        return True
    if command in ("erpnext.stock.get_item_details.get_item_details", "retail.domains.item.packing_scan.get_item_details"):
        args = frappe.parse_json(form.get("args")) or {}
        doctype = args.get("doctype") or form.get("doctype")
        require_target("doctype", doctype)
        if not frappe.has_permission(doctype, "read") or not frappe.has_permission("Item", "select"):
            deny()
        return True
    if command in ("retail.domains.purchase.history.get_comparisons", "retail.domains.purchase.history.get_history",
                   "retail.domains.purchase.history.get_stock_context"):
        document = frappe.parse_json(form.get("document")) or {}
        require_target("doctype", document.get("doctype"))
        if not frappe.has_permission(document.get("doctype"), "read"):
            deny()
        # The existing service checks native permission separately on every
        # history source; the selected document authorizes only the caller context.
        return True
    if command in ("frappe.desk.doctype.number_card.number_card.get_result",
                   "frappe.desk.doctype.number_card.number_card.get_percentage_difference",
                   "frappe.desk.doctype.dashboard_chart.dashboard_chart.get"):
        # Widgets belong to any selected workspace, while their stored data
        # source remains authoritative even when the browser supplies a draft.
        chart = command.endswith("dashboard_chart.get")
        supplied = frappe.parse_json(form.get("chart") if chart else form.get("doc")) or {}
        name = form.get("chart_name") if chart else supplied.get("name")
        name = name or supplied.get("name")
        kind = "Dashboard Chart" if chart else "Number Card"
        if name not in workspace_dependencies()[kind] or not frappe.has_permission(kind, "read", doc=name):
            deny()
        stored = frappe.get_cached_doc("Dashboard Chart" if chart else "Number Card", name)
        for field in ("document_type", "parent_document_type", "source", "report_name", "type",
                      "chart_type", "function", "aggregate_function_based_on", "method", "aggregate_function",
                      "based_on", "group_by_based_on", "group_by_type", "value_based_on"):
            if field in supplied and supplied[field] != stored.get(field):
                deny()
        if stored.get("document_type") and not frappe.has_permission(stored.document_type, "read"):
            deny()
        if stored.get("document_type"):
            frappe.flags.setdefault("retail_sidebar_service_doctypes", set()).add(stored.document_type)
        return True
    if command == "retail.column_preferences.save":
        require_target("doctype", form.get("doctype"))
        return True
    if command in ("frappe.utils.print_format.download_pdf", "upload_file", "frappe.handler.upload_file"):
        dt = form.get("doctype")
        name = form.get("name") or form.get("docname")
        require_target("doctype", dt)
        action = "print" if command.endswith("download_pdf") else "write"
        if not frappe.has_permission(dt, action, doc=name):
            deny()
        return True
    if command == "retail.customer_balances.get_customer_credit_balances":
        return capability("Customers", "Customer")
    if command == "retail.invoice_search.search_invoices":
        # This service runs its own list queries; install the same row condition.
        if not any(target_allowed("doctype", dt) and frappe.has_permission(dt, "read") for dt in ("Sales Invoice", "POS Invoice")):
            deny()
        frappe.flags.retail_sidebar_service_doctypes = {"Sales Invoice", "POS Invoice"}
        return True
    if command in ("retail.van_stock.get_van_stock_view", "retail.van_stock.get_van_warehouse_stock"):
        return capability("Van Sales Stock View Link", "Stock Entry")
    if command.startswith("retail.retail_app.retail_dashboard."):
        function = command.rsplit(".", 1)[1]
        if function in ("get_pos_top_selling_products", "get_pos_sales_by_counter", "get_pos_sales_trend_7_days"):
            return capability("POS Reports", "POS Invoice")
        if function in ("get_van_top_selling_products", "get_van_sales_by_van", "get_van_sales_trend_7_days"):
            return capability("Van Sales Reports", "Sales Invoice")
        if function == "get_cash_in_hand_today":
            return capability("Business Home", "GL Entry")
        if function == "get_damage_amount_today":
            return capability("Business Home", "Stock Entry")
        # Business Home is intentionally a dashboard capability, subject to the
        # existing permission-filtered data services and native read permissions.
        if function in ("get_today_sales", "get_today_profit", "get_invoice_count_today", "get_return_amount_today",
                        "get_top_selling_products", "get_sales_by_counter", "get_sales_trend_7_days",
                        "get_profit_number_card", "get_business_home_profit_cards"):
            return capability("Business Home", "Sales Invoice")
    return False
