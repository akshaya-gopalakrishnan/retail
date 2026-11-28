"""Additional operation permission for backend Sales Invoices only."""
import hashlib
import json
import secrets

import frappe
from frappe.rate_limiter import rate_limit
from frappe import _
from frappe.utils import cint, flt

ROLE = "Admin"
APPROVER_ROLES = frozenset({ROLE, "Customer Administrator"})
ROW_FIELDS = ("rate", "price_list_rate", "discount_percentage", "discount_amount", "margin_rate_or_amount", "custom_foc_qty")


def install():
    if not frappe.db.exists("Role", ROLE):
        frappe.get_doc({"doctype": "Role", "role_name": ROLE, "desk_access": 1}).insert(ignore_permissions=True)

    from retail.access_defaults import grant
    grant("POS Operator Privilege", ROLE, {"read": 1, "write": 1, "create": 1})
    frappe.clear_cache(doctype="POS Operator Privilege")


def applies(doc):
    return not any(cint(doc.get(field)) for field in ("is_pos", "is_consolidated", "custom_is_van_sale"))


def can_approve(user):
    # Administrator profile grants Customer Administrator. Super Admin alone
    # administers access settings and is not a business-operation approval role.
    return user == "Administrator" or bool(APPROVER_ROLES.intersection(frappe.get_roles(user)))


def allowed():
    return can_approve(frappe.session.user)


def deny(operation):
    frappe.throw(_("User ID and password approval from an Admin user is required to {0} in backend Sales Invoices.").format(operation), frappe.PermissionError)


def validate(doc, method=None):
    if not applies(doc) or allowed() or approved(doc):
        return
    header_approved = approved_header(doc)
    if (cint(doc.get("is_return")) or any(flt(row.qty) < 0 for row in doc.items)) and not header_approved:
        deny(_("make returns"))
    previous = doc.get_doc_before_save()
    if not header_approved and cint(doc.get("ignore_pricing_rule")) and not (previous and cint(previous.get("ignore_pricing_rule"))):
        deny(_("disable automatic pricing"))
    for field in ("discount_amount", "additional_discount_percentage"):
        if not header_approved and flt(doc.get(field)) != flt(previous.get(field) if previous else 0):
            deny(_("change discounts"))
    old_rows = {row.name: row for row in previous.items} if previous else {}
    expected_doc = frappe.copy_doc(doc)
    from retail.domains.item.packing_scan import get_item_details
    pending = []
    details_cache = {}
    for row, expected in zip(doc.items, expected_doc.items):
        if approved_row(doc, row):
            continue
        old = old_rows.get(row.name)
        same_context = previous and all(doc.get(f) == previous.get(f) for f in (
            "customer", "selling_price_list", "currency", "conversion_rate", "plc_conversion_rate", "posting_date"))
        if old and same_context and all(row.get(f) == old.get(f) for f in (
            "item_code", "uom", "conversion_factor", "rate", "custom_foc_qty")):
            continue
        key = (row.item_code, row.get("uom"), flt(row.get("qty")), flt(row.get("conversion_factor")),
               row.get("warehouse"), row.get("batch_no"))
        if key not in details_cache:
            args = frappe._dict({key: doc.get(key) for key in (
                "company", "customer", "currency", "conversion_rate", "selling_price_list",
                "price_list_currency", "plc_conversion_rate", "ignore_pricing_rule", "campaign", "sales_partner")})
            args.update({key: row.get(key) for key in (
                "item_code", "uom", "stock_uom", "qty", "conversion_factor", "warehouse", "batch_no")})
            args.update(doctype="Sales Invoice", name=doc.name, child_docname=row.name, transaction_date=doc.posting_date,
                        price_list=doc.selling_price_list, transaction_type="selling")
            details_cache[key] = get_item_details(args, doc=expected_doc)
        values = details_cache[key]
        for field in ROW_FIELDS:
            expected.set(field, values.get(field, 0))
        expected.rate = automatic_row_rate(values, row)
        pending.append((row, expected))
    if pending:
        from retail.promotions.promo_price import apply_inclusive_promo_prices
        apply_inclusive_promo_prices(expected_doc)
    # Native totals may rewrite discount percentages and margins while
    # preserving the final selling price. Approval follows that price.
    for row, expected in pending:
        for field in ("rate", "custom_foc_qty"):
            precision = row.precision(field) if hasattr(row, "precision") else 6
            if flt(row.get(field), precision) != flt(expected.get(field), precision):
                deny(_("change prices or discounts"))


def automatic_row_rate(values, row):
    """Use the form's price-list, margin and rounded discount calculation."""
    if flt(values.get("rate")) or not flt(values.get("price_list_rate")):
        return flt(values.get("rate"))
    listed = flt(values.get("price_list_rate"), row.precision("price_list_rate"))
    margin = flt(values.get("margin_rate_or_amount"))
    with_margin = listed + (listed * margin / 100 if values.get("margin_type") == "Percentage" else margin)
    if flt(values.get("discount_amount")) > 0:
        discount = flt(values.get("discount_amount"), row.precision("discount_amount"))
        return flt(with_margin - discount, row.precision("rate"))
    return flt(with_margin * (1 - flt(values.get("discount_percentage")) / 100), row.precision("rate"))


APPROVAL_FIELD = "_retail_sales_approval"


def fingerprint(doc):
    fields = ("customer", "company", "currency", "conversion_rate", "selling_price_list",
              "posting_date", "is_return", "return_against", "ignore_pricing_rule",
              "discount_amount", "additional_discount_percentage", "apply_discount_on")
    payload = {field: doc.get(field) for field in fields}
    payload["items"] = [
        {field: (round(flt(row.get(field)), 6) if field in ROW_FIELDS or field in ("qty", "conversion_factor") else row.get(field))
         for field in ("item_code", "uom", "qty", "conversion_factor", "sales_invoice_item", *ROW_FIELDS)}
        for row in doc.items
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def header_snapshot(doc):
    fields = ("customer", "company", "currency", "selling_price_list", "is_return", "return_against",
              "ignore_pricing_rule", "additional_discount_percentage", "apply_discount_on")
    snapshot = {field: doc.get(field) for field in fields}
    for field in ("conversion_rate", "plc_conversion_rate", "additional_discount_percentage", "is_return", "ignore_pricing_rule"):
        snapshot[field] = round(flt(doc.get(field)), 6)
    # Native totals recalculate this amount when an approved percentage is used.
    snapshot["discount_amount"] = 0 if flt(doc.get("additional_discount_percentage")) else round(flt(doc.get("discount_amount")), 6)
    return snapshot


def row_snapshot(row):
    # Discount and margin fields are native representations of the same final
    # price. Save can rewrite them without changing the approved selling rate.
    numeric = ("rate", "price_list_rate", "custom_foc_qty")
    return {field: round(flt(row.get(field)), 6) if field in numeric else row.get(field)
            for field in ("item_code", "uom", *numeric)}


def approval_tokens(doc):
    tokens = doc.get(APPROVAL_FIELD) or []
    return [tokens] if isinstance(tokens, str) else tokens if isinstance(tokens, list) else []


def valid_grants(doc):
    original = getattr(getattr(doc, "flags", None), "retail_approval_original_name", None)
    for token in approval_tokens(doc)[-100:]:
        if not isinstance(token, str):
            continue
        grant = frappe.cache.get_value("retail-sales-approval:" + token)
        if (grant and grant["actor"] == frappe.session.user and grant["document"] in (doc.name, original)
                and frappe.db.get_value("User", grant["approver"], "enabled") and can_approve(grant["approver"])):
            yield grant


def approved_header(doc):
    return any(grant.get("header") == header_snapshot(doc) for grant in valid_grants(doc))


def approved_row(doc, row):
    return any(grant.get("header") == header_snapshot(doc) and row_snapshot(row) in grant.get("rows", [])
               for grant in valid_grants(doc))


def approved(doc):
    return approved_header(doc) and all(approved_row(doc, row) for row in doc.items)


def before_insert(doc, method=None):
    # Frappe assigns the permanent invoice and child names before validation.
    doc.flags.retail_approval_original_name = doc.name or doc.get("localname") or doc.get("__temporary_name")


def after_insert(doc, method=None):
    for token in approval_tokens(doc):
        grant = frappe.cache.get_value("retail-sales-approval:" + token)
        if grant and grant["actor"] == frappe.session.user and grant["document"] == doc.flags.retail_approval_original_name:
            grant["document"] = doc.name
            frappe.cache.set_value("retail-sales-approval:" + token, grant, expires_in_sec=600)


def approval_document(doc):
    doc = frappe.get_doc(frappe.parse_json(doc))
    if doc.doctype != "Sales Invoice" or not applies(doc):
        frappe.throw(_("Approval is only available for backend Sales Invoices."), frappe.PermissionError)
    doc.check_permission("create" if doc.is_new() else "write")
    if not doc.is_new():
        doc.load_doc_before_save()
    return doc


@frappe.whitelist(methods=["POST"])
def requires_approval(doc):
    doc = approval_document(doc)
    muted = frappe.flags.mute_messages
    frappe.flags.mute_messages = True
    try:
        validate(doc)
        return False
    except frappe.PermissionError:
        return True
    except frappe.DoesNotExistError as exc:
        frappe.throw(str(exc) or _("A linked record used by this invoice is missing."), frappe.ValidationError)
    finally:
        frappe.flags.mute_messages = muted


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=300)
def authorize(doc, user, password):
    doc = approval_document(doc)
    from frappe.utils.password import check_password
    if not user or not password:
        frappe.throw(_("Enter the approving user ID and password."), frappe.AuthenticationError)
    user = check_password(user, password)
    if not frappe.db.get_value("User", user, "enabled") or not can_approve(user):
        frappe.throw(_("The selected user must be enabled and have the Admin or Customer Administrator role. The Administrator Role Profile supplies Customer Administrator. Save the User assignment before trying again."), frappe.ValidationError)
    token = secrets.token_urlsafe(32)
    frappe.cache.set_value("retail-sales-approval:" + token, {
        "actor": frappe.session.user, "approver": user, "document": doc.name,
        "fingerprint": fingerprint(doc), "header": header_snapshot(doc),
        "rows": [row_snapshot(row) for row in doc.items],
    }, expires_in_sec=600)
    return token


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def approver_query(doctype, txt, searchfield, start, page_len, filters=None):
    """Search enabled saved IDs; authorize separately checks approval rights."""
    if not (frappe.has_permission("Sales Invoice", "create") or frappe.has_permission("Sales Invoice", "write")):
        frappe.throw(_("Sales Invoice access is required."), frappe.PermissionError)
    return frappe.db.sql(
        """select u.name, u.full_name, u.username from `tabUser` u
        where u.enabled = 1
          and u.name not in ('Guest', 'Administrator')
          and (u.name like %(txt)s or u.full_name like %(txt)s or u.username like %(txt)s)
        order by u.full_name, u.name
        limit %(start)s, %(page_len)s""",
        {"txt": "%" + (txt or "") + "%", "start": max(0, cint(start)),
         "page_len": min(50, max(1, cint(page_len)))},
    )
