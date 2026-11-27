"""Company-owned VAT policy for ordinary trading Sales Invoices."""

import frappe
from frappe.utils import cint, flt
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

COMPANY_FIELD = "custom_enable_trading_sales_vat"
INVOICE_FIELD = "custom_trading_vat_disabled"


def ensure_setup():
    create_custom_fields({
        "Company": [
            {"fieldname": "custom_trading_invoice_vat", "label": "Trading Invoice VAT",
             "fieldtype": "Section Break", "insert_after": "custom_default_sales_rate_includes_vat"},
            {"fieldname": COMPANY_FIELD, "label": "Enable VAT on Trading Sales Invoices",
             "fieldtype": "Check", "default": "1", "insert_after": "custom_trading_invoice_vat",
             "description": ""},
        ],
        "Sales Invoice": [{"fieldname": INVOICE_FIELD, "label": "Trading VAT Disabled",
                           "fieldtype": "Check", "default": "0", "hidden": 1,
                           "read_only": 1, "no_copy": 1, "insert_after": "taxes_and_charges"}],
    }, ignore_validate=True)
    # Update only known VAT expressions in the editable A4 copy; retain site edits.
    if frappe.db.exists("Print Format", "Sales Invoice - A4"):
        original = frappe.db.get_value("Print Format", "Sales Invoice - A4", "html") or ""
        html = original.replace('{{ _("Tax Invoice") }}',
            '{{ _("Sales Invoice") if doc.get("custom_trading_vat_disabled") else _("Tax Invoice") }}')
        html = html.replace('{% if doc.taxes and doc.taxes|length > 0 %}',
            '{% if not doc.get("custom_trading_vat_disabled") and doc.taxes and doc.taxes|length > 0 %}')
        if html != original:
            frappe.db.set_value("Print Format", "Sales Invoice - A4", "html", html)

    from retail.domains.transactions.trading_vat_print import install
    install()


def vat_disabled(doc):
    if doc.get("doctype") != "Sales Invoice" or cint(doc.get("is_pos")) or cint(doc.get("is_consolidated")):
        return False
    if cint(doc.get("docstatus")) != 0:
        # During submit the document already has docstatus=1, but its policy
        # must still be enforced before the first accounting posting.
        submitting = False
        if doc.get("_action") == "submit":
            stored_status = frappe.db.get_value("Sales Invoice", doc.get("name"), "docstatus") if doc.get("name") else None
            submitting = cint(stored_status) == 0
        if not submitting:
            return bool(cint(doc.get(INVOICE_FIELD)))
    if doc.get("return_against"):
        return bool(frappe.db.get_value("Sales Invoice", doc.get("return_against"), INVOICE_FIELD))
    company = doc.get("company")
    if not company or not frappe.get_meta("Company").has_field(COMPANY_FIELD):
        return False
    return not cint(frappe.get_cached_value("Company", company, COMPANY_FIELD))


def vat_accounts(doc):
    """Identify VAT accounts without removing freight or other invoice charges."""
    templates = {row.get("item_tax_template") for row in doc.get("items") or []}
    for row in doc.get("items") or []:
        if row.get("item_code"):
            templates.add(frappe.get_cached_value("Item", row.item_code, "custom_tax"))
    if doc.get("company"):
        templates.add(frappe.get_cached_value("Company", doc.company, "custom_default_sales_vat_template"))
    accounts = set()
    for template in templates - {None, ""}:
        for row in frappe.get_cached_doc("Item Tax Template", template).taxes:
            accounts.add(row.tax_type)
    return accounts


def prepare(doc, method=None):
    if not vat_disabled(doc):
        if doc.get("doctype") == "Sales Invoice" and not cint(doc.get("docstatus")):
            doc.set(INVOICE_FIELD, 0)
        return False
    accounts = vat_accounts(doc)
    # A draft created under VAT may already carry 3.81 exclusive / 4 inclusive.
    # Convert that draft once; subsequent explicit rate edits remain authoritative.
    converting = not cint(doc.get(INVOICE_FIELD))
    for row in doc.get("items") or []:
        if converting and (flt(row.get("custom_vat_amount")) or row.get("item_tax_template")) and flt(row.get("custom_rate_including_vat")) > flt(row.get("rate")):
            row.rate = flt(row.custom_rate_including_vat)
            if row.get("price_list_rate"):
                from retail.domains.transactions.vat import get_transaction_item_vat_rate
                rate = get_transaction_item_vat_rate(row.item_code, item_tax_template=row.get("item_tax_template"), parent_doctype="Sales Invoice")
                row.price_list_rate = flt(row.price_list_rate) * (1 + rate / 100)
                row.discount_amount = flt(row.price_list_rate) - flt(row.rate)
        row.item_tax_template = None
        row.item_tax_rate = "{}"
        row.custom_vat_amount = 0
        row.custom_rate_including_vat = flt(row.get("rate"))
        row.amount = flt(row.get("qty")) * flt(row.get("rate"))
        row.custom_amount_including_vat = row.amount
    doc.set(INVOICE_FIELD, 1)
    doc.taxes_and_charges = None
    doc.set("taxes", [row for row in doc.get("taxes") or []
                       if row.account_head not in accounts and not (row.get("description") or "").startswith("Sales Tax [")])
    return True


def lookup_rate(args, item_code, rate):
    """Retail maintains net Item Prices; preserve their gross selling price."""
    context = frappe._dict(args)
    context.doctype = args.get("parenttype") or args.get("doctype")
    if rate is None or not vat_disabled(context):
        return rate
    from retail.domains.transactions.vat import get_transaction_item_vat_rate
    vat = get_transaction_item_vat_rate(item_code, parent_doctype="Sales Invoice")
    return flt(rate) * (1 + vat / 100)
