"""Additive schema gate and explicit, reviewable recovery of partial Retail setup.

Automatic hooks install missing schema only. Financial recovery is opt-in, fills
blanks only and refuses ambiguous accounts. Never runs migration/backfill hooks.
"""
import hashlib
import json

import frappe

FOC_ROWS = (
    "Purchase Order Item", "Purchase Receipt Item", "Purchase Invoice Item",
    "Sales Order Item", "Delivery Note Item", "Sales Invoice Item",
    "POS Invoice Item", "Stock Entry Detail",
)
PROFILE_DEFAULTS = {
    "income_account": "default_income_account",
    "expense_account": "default_expense_account",
    "write_off_account": "write_off_account",
    "account_for_change_amount": "default_cash_account",
    "cost_center": "cost_center", "write_off_cost_center": "cost_center",
}
ALIASES = {
    "default_income_account": ("Pos Sales", "Sales Account", "Sales", "Retail Sales", "Shop Sales"),
    "default_expense_account": ("Cost of Goods Sold in Trading", "Cost of Goods Sold"),
    "default_cash_account": ("Main Safe", "Cash", "Cash In Hand"),
    "default_bank_account": ("Banks Current Accounts", "Bank", "Bank Account"),
    "default_inventory_account": ("Stock in Hand",),
    "default_receivable_account": ("Trade Receivable", "Trade Receivables", "Debtors"),
    "default_payable_account": ("Trade Payable", "Trade Payables", "Creditors"),
    "write_off_account": ("Write Off Receivables & Payables", "Write Off"),
    "exchange_gain_loss_account": ("Loss on Difference on Exchange", "Exchange Gain/Loss"),
}


def definitions():
    from retail.pos_transaction_display import TYPE_OPTIONS
    fields = {dt: [
        {"fieldname": "custom_foc_key", "label": "FOC Relationship", "fieldtype": "Data", "hidden": 1, "read_only": 1},
        {"fieldname": "custom_foc_parent", "label": "FOC Paid Row Relationship", "fieldtype": "Data", "hidden": 1, "read_only": 1},
    ] for dt in FOC_ROWS}
    fields.update({
        "POS Invoice": [{"fieldname": "custom_pos_transaction_type", "label": "Transaction Type", "fieldtype": "Select", "options": TYPE_OPTIONS, "read_only": 1, "no_copy": 1, "in_list_view": 1, "in_standard_filter": 1, "insert_after": "status"}],
        "POS Sync Log": [
            {"fieldname": "custom_accounting_invoice", "label": "Accounting Sales Invoice", "fieldtype": "Link", "options": "Sales Invoice", "read_only": 1, "insert_after": "linked_invoice", "in_list_view": 1},
            {"fieldname": "custom_pos_transaction_type", "label": "Sync Type", "fieldtype": "Data", "read_only": 1, "in_list_view": 1, "in_standard_filter": 1, "insert_after": "sync_type"},
        ],
        "Sales Order": [{"fieldname": "custom_app_order_id", "label": "App Order ID", "fieldtype": "Data", "insert_after": "po_no", "read_only": 1, "no_copy": 1, "unique": 1}],
        "Item Price": [{"fieldname": "custom_retail_item_buying_price", "label": "Retail Item Managed Buying Price", "fieldtype": "Check", "default": "0", "hidden": 1, "read_only": 1, "no_copy": 1}],
    })
    return fields


def install_schema():
    """Safe for existing sites: never overwrite a site's existing field definition."""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    missing = {}
    for dt, fields in definitions().items():
        meta = frappe.get_meta(dt, cached=False)
        for field in fields:
            if not meta.has_field(field["fieldname"]):
                missing.setdefault(dt, []).append(field)
    if missing:
        create_custom_fields(missing, update=False)


def validate_schema():
    problems = []
    for dt, fields in definitions().items():
        meta = frappe.get_meta(dt, cached=False)
        columns = set(frappe.db.get_table_columns(dt))
        for field in fields:
            current = meta.get_field(field["fieldname"])
            if not current or field["fieldname"] not in columns:
                problems.append(f"Missing {dt}.{field['fieldname']}")
            elif current.fieldtype != field["fieldtype"]:
                problems.append(f"Wrong type {dt}.{field['fieldname']}")
    return problems


def _usable(account, company, spec):
    types = ("", "Income Account") if spec[2] == "Income Account" else (spec[2],)
    if spec[0] == "Post Dated Cheques Received":
        types = ("Bank", "Receivable")
    return (account.company == company.name and account.root_type == spec[1]
            and (account.account_type or "") in types and not account.is_group
            and not account.disabled and account.account_currency == company.default_currency)


def _candidate(accounts, company, spec, aliases):
    for label in aliases:
        matches = [a.name for a in accounts if a.account_name.casefold() == label.casefold()
                   and _usable(a, company, spec)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return None
    return None


def plan(company):
    """Read-only recovery proposal. Existing nonblank financial choices are preserved."""
    from retail.accounting_defaults import DEFAULTS, PAYMENT_ACCOUNT_SPECS
    doc = frappe.get_doc("Company", company)
    accounts = frappe.get_all("Account", filters={"company": company}, fields=[
        "name", "account_name", "company", "root_type", "account_type",
        "account_currency", "is_group", "disabled",
    ], order_by="name")
    result = {"site": frappe.local.site, "company": company, "changes": [],
              "blockers": [], "warnings": [], "schema_problems": validate_schema()}
    changes = result["changes"]
    resolved = {}
    for field, spec in DEFAULTS.items():
        current = doc.get(field)
        if current:
            resolved[field] = current
            account = next((a for a in accounts if a.name == current), None)
            if not account or not _usable(account, doc, spec):
                result["blockers"].append(f"Review existing {field}: {current}; preserved")
            if field == "default_receivable_account" and account and account.account_name == "Trade in Opening Fees":
                result["warnings"].append("Existing receivable is Trade in Opening Fees; preserved, review intended customer routing")
            continue
        candidate = _candidate(accounts, doc, spec, ALIASES.get(field, spec[3]))
        if not candidate:
            result["blockers"].append(f"No unambiguous existing account for {field}")
        else:
            resolved[field] = candidate
            changes.append({"doctype": "Company", "name": company, "field": field, "value": candidate})
    resolved["cost_center"] = doc.cost_center
    if not doc.cost_center:
        result["blockers"].append("Company cost center is blank")
    if doc.cost_center and not doc.round_off_cost_center:
        changes.append({"doctype": "Company", "name": company, "field": "round_off_cost_center", "value": doc.cost_center})
    for mode in ("Cash", "Card", "Credit Card", "Cheque", "Bank Draft", "Wire Transfer"):
        if frappe.db.exists("Mode of Payment", mode):
            payment = frappe.get_doc("Mode of Payment", mode)
            if not payment.enabled or payment.type != ("Cash" if mode == "Cash" else "Bank"):
                result["warnings"].append(f"Preserved disabled or differently typed payment mode: {mode}")
                continue
            rows = [r for r in payment.accounts if r.company == company]
            if len(rows) > 1:
                result["blockers"].append(f"Duplicate company payment mappings: {mode}")
                continue
            if rows and rows[0].default_account:
                account = next((a for a in accounts if a.name == rows[0].default_account), None)
                if not account or account.is_group or account.disabled or account.root_type != "Asset":
                    result["blockers"].append(f"Invalid existing payment account: {mode}")
                continue
        spec = PAYMENT_ACCOUNT_SPECS.get(mode)
        account = (_candidate(accounts, doc, spec, spec[3]) if spec else
                   resolved.get("default_cash_account" if mode == "Cash" else "default_bank_account"))
        if account:
            changes.append({"doctype": "Mode of Payment", "name": mode, "field": "accounts", "value": account})
        else:
            result["warnings"].append(f"No existing account for {mode}; left unconfigured (not added to POS)")
    for name in frappe.get_all("POS Profile", filters={"company": company}, pluck="name"):
        profile = frappe.get_doc("POS Profile", name)
        for row in profile.payments:
            mapping = frappe.db.get_value("Mode of Payment Account", {"parent": row.mode_of_payment, "company": company}, "default_account")
            proposed = any(c["doctype"] == "Mode of Payment" and c["name"] == row.mode_of_payment for c in changes)
            if not mapping and not proposed:
                result["blockers"].append(f"POS profile {name} uses unmapped payment mode {row.mode_of_payment}")
        for field, source in PROFILE_DEFAULTS.items():
            if profile.meta.has_field(field) and not profile.get(field) and resolved.get(source):
                changes.append({"doctype": "POS Profile", "name": name, "field": field, "value": resolved[source]})
    meta = frappe.get_meta("Item", cached=False)
    if meta.get_field("item_code").reqd:
        changes.append({"doctype": "Item setting", "name": "item_code", "field": "reqd", "value": "0"})
    templates = []
    for name in frappe.get_all("Item Tax Template", filters={"company": company, "disabled": 0}, pluck="name"):
        template = frappe.get_doc("Item Tax Template", name)
        if template.taxes and sum(float(t.tax_rate or 0) for t in template.taxes) == 5:
            templates.append(name)
    for field in ("custom_tax", "custom_purchase_tax_template"):
        current = meta.get_field(field).default
        if current:
            if not frappe.db.exists("Item Tax Template", current):
                result["blockers"].append(f"Invalid existing Item default: {field}")
        elif len(templates) == 1 and frappe.db.count("Company") == 1:
            changes.append({"doctype": "Item setting", "name": field, "field": "default", "value": templates[0]})
        else:
            result["blockers"].append(f"Cannot choose unambiguous Item VAT default: {field}")
    # Include financial state so a stale review cannot approve a changed target.
    state = {"result": result, "accounts": accounts, "company": doc.as_dict(),
             "payments": frappe.get_all("Mode of Payment Account", filters={"company": company}, fields=["parent", "default_account"], order_by="parent"),
             "profiles": [frappe.get_doc("POS Profile", name).as_dict() for name in frappe.get_all("POS Profile", filters={"company": company}, pluck="name", order_by="name")]}
    result["review_token"] = hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()
    return result


def apply(company, review_token):
    """Apply exactly a current reviewed proposal; no ledgers or existing choices changed."""
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter
    frappe.only_for("System Manager")
    report = plan(company)
    if report["review_token"] != review_token or report["blockers"]:
        raise RuntimeError("Plan changed or has blockers; run plan again before repair")
    # DDL may commit implicitly. Validate the entire financial plan before schema work.
    install_schema()
    problems = validate_schema()
    if problems:
        raise RuntimeError("Schema verification failed before financial changes: " + "; ".join(problems))
    for change in report["changes"]:
        dt, name, field, value = (change[k] for k in ("doctype", "name", "field", "value"))
        if dt == "Item setting":
            make_property_setter("Item", name, field, value, "Check" if field == "reqd" else "Data", validate_fields_for_doctype=False)
        elif dt == "Mode of Payment":
            payment = frappe.get_doc(dt, name) if frappe.db.exists(dt, name) else frappe.new_doc(dt)
            payment.mode_of_payment = name
            if payment.is_new():
                payment.type, payment.enabled = ("Cash" if name == "Cash" else "Bank"), 1
            rows = [r for r in payment.accounts if r.company == company]
            if rows:
                rows[0].default_account = value
            else:
                payment.append("accounts", {"company": company, "default_account": value})
            payment.save(ignore_permissions=True)
        else:
            frappe.db.set_value(dt, name, field, value)
    frappe.clear_cache()
    remaining = plan(company)
    if remaining["blockers"] or remaining["schema_problems"] or remaining["changes"]:
        raise RuntimeError("Post-repair verification failed: " + json.dumps(remaining, default=str))
    return {"configuration": "APPLIED_WITH_REVIEW_ITEMS" if remaining["warnings"] else "VERIFIED", "report": remaining,
            "business_workflows": "NOT YET VERIFIED"}


def initialize_item_defaults(doc=None, method=None):
    """Fill blank global defaults only for an unambiguous single-company site."""
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter
    companies = frappe.get_all("Company", pluck="name")
    if len(companies) != 1:
        return
    templates = []
    for name in frappe.get_all("Item Tax Template", filters={"company": companies[0], "disabled": 0}, pluck="name"):
        template = frappe.get_doc("Item Tax Template", name)
        if template.taxes and sum(float(t.tax_rate or 0) for t in template.taxes) == 5:
            templates.append(name)
    if len(templates) != 1:
        return
    meta = frappe.get_meta("Item", cached=False)
    for field in ("custom_tax", "custom_purchase_tax_template"):
        current = meta.get_field(field)
        if current and not current.default:
            make_property_setter("Item", field, "default", templates[0], "Data", validate_fields_for_doctype=False)


def validate():
    problems = validate_schema()
    if problems:
        raise RuntimeError("Retail schema incomplete: " + "; ".join(problems))
    return {"retail_required_schema": "OK"}


def validate_disposable_company():
    """Exercise the actual UAE chart on an empty isolated validation site only."""
    import os
    if (os.environ.get("RETAIL_DISPOSABLE_VALIDATION") != "1"
            or frappe.local.site != "retail-test.localhost"
            or frappe.db.count("Company")):
        raise RuntimeError("Requires an explicitly disposable empty validation site")
    validate()
    # Company creation normally follows the ERPNext Setup Wizard's master-data
    # stage. Run that native stage here too, rather than masking missing links.
    from erpnext.setup.setup_wizard.operations.install_fixtures import install
    install(country="United Arab Emirates")
    company = frappe.get_doc({
        "doctype": "Company", "company_name": "Retail UAE Installation Validation",
        "abbr": "RUV", "default_currency": "AED", "country": "United Arab Emirates",
        "create_chart_of_accounts_based_on": "Standard Template",
        "chart_of_accounts": "U.A.E - Chart of Accounts",
    }).insert(ignore_permissions=True)
    from retail.accounting_defaults import DEFAULTS, VERSION_FIELD
    if company.get(VERSION_FIELD) != 1:
        raise RuntimeError("New-company accounting initialization did not finish")
    accounts = frappe.get_all("Account", filters={"company": company.name}, fields=[
        "name", "account_name", "company", "root_type", "account_type",
        "account_currency", "is_group", "disabled",
    ])
    for field, spec in DEFAULTS.items():
        account = next((a for a in accounts if a.name == company.get(field)), None)
        if not account or not _usable(account, company, spec):
            raise RuntimeError(f"Invalid new-company default: {field}")
    cheque = frappe.get_doc("Account", "Post Dated Cheques Received - RUV")
    if cheque.account_type != "Receivable":
        raise RuntimeError("Native cheque account was retyped")
    meta = frappe.get_meta("Item", cached=False)
    if meta.get_field("item_code").reqd:
        raise RuntimeError("Automatic Item Code still mandatory")
    for field in ("custom_tax", "custom_purchase_tax_template"):
        if not meta.get_field(field).default:
            raise RuntimeError(f"Missing new-company Item default: {field}")
    report = plan(company.name)
    if report["blockers"]:
        raise RuntimeError(json.dumps(report, default=str))
    # Exercise the real Item validation/on_update chain, not only helper mocks.
    from retail.domains.item.item_price_sync import MANAGED_BUYING_FIELD
    item = frappe.get_doc({
        "doctype": "Item", "item_name": "Retail Validation Buying Clear",
        "custom_arabic_item_name": "اختبار", "item_group": "Products", "stock_uom": "Nos",
        "custom_purchase_rate_entry": 39.90, "custom_purchase_rate_includes_vat": 1,
        "custom_sales_rate_entry": 2.95, "custom_sales_rate_includes_vat": 1,
        "custom_retail_packing_detail": [{
            "packing_name": "Retail Validation Box", "packing_uom": "Box",
            "conversion_factor": 36, "barcode": "8880000000036",
            "purchase_rate": 1436.40, "purchase_vat_mode": "Including VAT",
            "selling_rate": 106.20, "selling_vat_mode": "Including VAT",
        }],
    }).insert(ignore_permissions=True)
    packing_uom = item.custom_retail_packing_detail[0].uom
    prices_before = {}
    for uom, rate in (("Nos", 38), (packing_uom, 1368)):
        price = frappe.db.get_value("Item Price", {"item_code": item.name,
            "price_list": "Standard Buying", "uom": uom},
            ["name", "price_list_rate", MANAGED_BUYING_FIELD], as_dict=True)
        if not price or price.price_list_rate != rate or not price.get(MANAGED_BUYING_FIELD):
            raise RuntimeError(f"New Item buying price not tracked: {uom}")
        prices_before[uom] = price.name
    item.custom_purchase_rate_entry = 0
    item.custom_retail_packing_detail[0].purchase_rate = 0
    item.save(ignore_permissions=True)
    for uom, name in prices_before.items():
        if frappe.db.get_value("Item Price", name, "price_list_rate") != 0:
            raise RuntimeError(f"Intentional buying clear did not persist: {uom}")
    return {"uae_company_initialization": "OK", "schema": "OK",
            "item_defaults": "OK", "buying_price_clear": "OK", "remaining_proposal": report}
