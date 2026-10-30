"""POS-reported promotion evidence; advisory checks never reprice completed bills."""
import hashlib
import json
import math

import frappe
from frappe.utils import cint, flt, get_datetime, now_datetime

TYPES = ("Promo Price", "Buy X Get Y Promotion", "Gift Voucher Promotion")
AUDIT_FIELD = "custom_pos_promotion_history"


def version(doc):
    return hashlib.sha256(f"{doc.doctype}:{doc.name}:{doc.modified}".encode()).hexdigest()


def record_revision(doc, method=None, *, baseline=False):
    key = version(doc)
    if frappe.db.exists("Retail Promotion Revision", key):
        return
    rule = doc.as_dict()
    # Baselines prove current state only, never invent pre-install history.
    frappe.get_doc(dict(doctype="Retail Promotion Revision", name=key,
        promotion_type=doc.doctype, promotion=doc.name,
        effective_from=now_datetime() if baseline else doc.modified,
        rule_json=frappe.as_json(rule))).insert(ignore_permissions=True, set_name=key)


def install():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({"POS Invoice": [dict(fieldname=AUDIT_FIELD,
        label="POS Promotion History", fieldtype="Code", options="JSON", hidden=1,
        read_only=1, no_copy=1)]}, update=True)
    frappe.db.add_index("Retail Promotion Revision", ["promotion_type", "promotion", "effective_from"])
    for doctype in TYPES:
        for name in frappe.get_all(doctype, pluck="name"):
            record_revision(frappe.get_doc(doctype, name), baseline=True)
    # Update just these links; preserve workspace content and user customizations.
    if frappe.db.exists("Workspace", "Promotions"):
        workspace = frappe.get_doc("Workspace", "Promotions")
        names = ("Promotion Performance", "Promotion Sales Summary", "Promotion Sales Detail")
        existing = {r.link_to for r in workspace.links}
        position = next((i + 1 for i, r in enumerate(workspace.links)
                         if r.type == "Card Break" and r.label == "Promotion History"), None)
        if position is not None:
            for name in reversed(names):
                if name not in existing:
                    row = workspace.append("links", dict(type="Link", label=name, link_type="Report",
                        link_to=name, is_query_report=1))
                    workspace.links.remove(row)
                    workspace.links.insert(position, row)
            for i, row in enumerate(workspace.links, 1):
                row.idx = i
                if row.type == "Card Break" and row.label == "Promotion History":
                    row.link_count = 4
            workspace.save(ignore_permissions=True)


def check_schedule(rule, payload):
    """Require original sale time: never silently substitute sync arrival time."""
    from retail.promotions.schedule import is_active
    if not payload.get("posting_date") or not payload.get("posting_time"):
        return "Review Required", "Original sale date/time missing"
    enabled = cint(rule.get("enabled")) if rule.get("doctype") == "Gift Voucher Promotion" else not cint(rule.get("disabled"))
    if not enabled:
        return "Review Required", "Promotion disabled at sale time"
    try:
        if not is_active(frappe._dict(rule), frappe._dict(payload)):
            return "Review Required", "Sale outside promotion dates/hours"
    except (ValueError, TypeError):
        return "Review Required", "Invalid sale date/time or promotion schedule"
    return "Schedule Valid", "Enabled and within dates/hours; eligibility/amounts are POS-reported"


def audit_application(application, payload, doc):
    row = dict(application)
    row.update(status="Review Required", reason="Historical rule unavailable")
    kind, name = row.get("promotion_type"), row.get("promotion")
    if not isinstance(kind, str) or kind not in TYPES or not isinstance(name, str) or not name:
        row['reason'] = "Unknown promotion type/reference"
        return row
    if doc.is_return:
        row['reason'] = "Return requires original sale promotion evidence"
        if doc.return_against:
            original = frappe.db.get_value("POS Invoice", doc.return_against, AUDIT_FIELD)
            original_audit = json.loads(original or '{}')
            if not original_audit.get('reported'):
                original_doc = frappe.get_doc('POS Invoice', doc.return_against)
                if not original_doc.is_return:
                    capture(original_doc)
                    original_audit = json.loads(original_doc.get(AUDIT_FIELD) or '{}')
            evidence = original_audit.get('applications', [])
            if any(r.get('promotion_type') == kind and r.get('promotion') == name
                   and r.get('item_row') == row.get('original_item_row') for r in evidence):
                row.update(status="Return Linked", reason="Reversal linked to original promotion; reported amounts retained")
        return row
    if not payload.get('posting_date') or not payload.get('posting_time'):
        row['reason'] = "Original sale date/time missing"
        return row
    try:
        sale_time = get_datetime(f"{payload['posting_date']} {payload['posting_time']}")
    except (ValueError, TypeError):
        row['reason'] = "Invalid original sale date/time"
        return row
    revision = frappe.get_all("Retail Promotion Revision", filters={
        'promotion_type': kind, 'promotion': name, 'effective_from': ['<=', sale_time]},
        fields=['name', 'rule_json'], order_by='effective_from desc, creation desc', limit=1)
    if not revision:
        return row
    actual = revision[0]
    row['checked_version'] = actual.name
    if row.get('promotion_version') != actual.name:
        row['reason'] = "POS version missing or differs from rule effective at sale time"
        return row
    rule = json.loads(actual.rule_json)
    if (rule.get('company') and rule['company'] != doc.company) or (
            rule.get('warehouse') and rule['warehouse'] != doc.set_warehouse):
        row['reason'] = "Promotion company/warehouse differs from sale"
        return row
    row['status'], row['reason'] = check_schedule(rule, payload)
    return row


def resolve_item_row(application, items):
    """Resolve evidence against original sale lines, never guess between repeats."""
    identity = ('item_code', 'barcode', 'uom')
    if application.get('item_row') is not None:
        value = application['item_row']
        try:
            idx = int(value)
            valid = not isinstance(value, bool) and float(value) == idx and 1 <= idx <= len(items)
        except (ValueError, TypeError, OverflowError):
            valid = False
        if not valid:
            return 0, 'Invalid item_row; use 1-based payload item position'
        if any(application.get(k) is not None and application[k] != items[idx-1].get(k) for k in identity):
            return 0, 'Promotion item identity differs from item_row'
        return idx, None
    if not isinstance(application.get('item_code'), str) or not application['item_code']:
        return 0, 'Supply item_code or item_row for promotion attribution'
    matches = [i for i, item in enumerate(items, 1)
               if all(application.get(k) is None or application[k] == item.get(k) for k in identity)]
    if len(matches) == 1:
        return matches[0], None
    return 0, ('Ambiguous promotion item; supply barcode/uom or item_row' if matches
               else 'Promotion item does not match an invoice row')


def applications_for(payload, precision=2):
    """Accept terminal item evidence without changing completed financial facts.

    An explicit header array is authoritative, including an empty array.
    Nested promotion_discount_amount is a line total in the item's price basis.
    """
    if 'applied_promotions' in payload:
        return payload['applied_promotions']
    applications = []
    reported = False
    for idx, item in enumerate(payload.get('items') or [], 1):
        if 'applied_promotions' not in item:
            continue
        reported = True
        nested = item['applied_promotions']
        if not isinstance(nested, list):
            applications.append(dict(item_row=idx))
            continue
        for source in nested:
            if not isinstance(source, dict):
                applications.append(source)
                continue
            row = dict(source)
            row['item_row'] = idx
            for key in ('item_code', 'barcode', 'uom'):
                row[key] = item.get(key)
            row.setdefault('quantity', item.get('qty'))
            row.setdefault('sales_amount', item.get('net_amount'))
            row.setdefault('free_quantity', 0)
            if 'discount_amount' not in row and source.get('promotion_discount_amount') is not None:
                try:
                    factor = 1 + float(item.get('vat_rate') or 0) / 100 if cint(item.get('rate_includes_vat')) else 1
                    row['discount_amount'] = flt(float(source['promotion_discount_amount']) / factor, precision)
                except (ValueError, TypeError, ZeroDivisionError, OverflowError):
                    row['discount_amount'] = 'invalid'
            applications.append(row)
    return applications if reported else None


def capture(doc, method=None):
    from retail.pos_completed_sale import payload_for
    payload = payload_for(doc)
    if not payload:
        return
    precision = doc.precision('net_total') if callable(getattr(doc, 'precision', None)) else 2
    applications = applications_for(payload, precision=precision or 2)
    result = dict(version=1, reported=isinstance(applications, list), applications=[])
    if applications is not None and not isinstance(applications, list):
        result.update(reported=False, reason='applied_promotions must be an array')
    seen = set()
    for application in applications if isinstance(applications, list) else []:
        if not isinstance(application, dict):
            result['applications'].append(dict(status='Review Required', reason='Invalid promotion evidence'))
            continue
        allowed = ('promotion_type', 'promotion', 'promotion_version', 'item_row', 'original_item_row',
                   'quantity', 'discount_amount', 'sales_amount', 'free_quantity', 'item_code', 'barcode', 'uom')
        evidence = {key: application.get(key) for key in allowed}
        invalid_shape = any(not isinstance(value, (str, int, float, type(None))) for value in evidence.values())
        if invalid_shape:
            result['applications'].append(dict(status='Review Required', reason='Invalid promotion evidence fields'))
            continue
        idx, identity_error = resolve_item_row(evidence, payload.get('items') or [])
        evidence['item_row'] = idx
        row = audit_application(evidence, payload, doc)
        if row.get('quantity') is None or row.get('discount_amount') is None or row.get('sales_amount') is None:
            row.update(status='Review Required', reason='Required quantity/discount/sales amount missing')
        if identity_error:
            row.update(status='Review Required', reason=identity_error, excluded_from_totals=True)
        else:
            item = payload['items'][idx-1]
            saved_item = (doc.get('items') or [])[idx-1] if idx <= len(doc.get('items') or []) else {}
            row.update(item_code=item.get('item_code') or saved_item.get('item_code'),
                       barcode=item.get('barcode') or saved_item.get('barcode'),
                       uom=item.get('uom') or saved_item.get('uom'))
        key = (row.get('promotion_type'), row.get('promotion'), idx)
        if key in seen:
            row.update(status='Review Required', reason='Duplicate application for promotion/item row', excluded_from_totals=True)
        seen.add(key)
        for field in ('quantity', 'discount_amount', 'sales_amount', 'free_quantity'):
            try:
                value = float(row.get(field) or 0)
                if not math.isfinite(value):
                    raise ValueError()
                row[field] = (-1 if doc.is_return else 1) * abs(value)
            except (ValueError, TypeError):
                row[field] = 0
                row.update(status='Review Required', reason=f'Invalid {field}')
        result['applications'].append(row)
    doc.set(AUDIT_FIELD, frappe.as_json(result))


def report_rows(filters):
    """Respect invoice permissions and company/user restrictions, including pagination."""
    conditions = {'docstatus': 1, 'pos_sync_source': 'Offline POS'}
    if not filters.get('from_date') or not filters.get('to_date'):
        frappe.throw('From Date and To Date are required')
    if get_datetime(filters.from_date) > get_datetime(filters.to_date):
        frappe.throw('From Date cannot be after To Date')
    conditions['posting_date'] = ['between', [filters.from_date, filters.to_date]]
    for key in ('company', 'pos_branch', 'pos_counter', 'pos_cashier'):
        if filters.get(key):
            conditions[key] = filters[key]
    start = 0
    while True:
        invoices = frappe.get_list('POS Invoice', filters=conditions,
            fields=['name', 'posting_date', 'posting_time', 'company', 'currency', 'pos_branch', 'pos_counter',
                    'pos_cashier', 'pos_cashier_employee', 'is_return', AUDIT_FIELD, 'custom_pos_completed_payload'], order_by='posting_date, name',
            limit_start=start, limit_page_length=500)
        for invoice in invoices:
            audit = json.loads(invoice.pop(AUDIT_FIELD) or '{}')
            payload = json.loads(invoice.pop('custom_pos_completed_payload') or '{}')
            # Older receipts already retain the original nested evidence. Read
            # it without rewriting submitted documents or inventing evidence.
            if not audit.get('reported') and any('applied_promotions' in item for item in payload.get('items') or []):
                doc = frappe.get_doc('POS Invoice', invoice.name)
                capture(doc)
                audit = json.loads(doc.get(AUDIT_FIELD) or '{}')
            applications = audit.get('applications', [])
            # Use the saved sale description, including its actual packing, before master names.
            item_names = {}
            if any(a.get('promotion') and a.get('item_row') for a in applications):
                saved = frappe.get_doc('POS Invoice', invoice.name)
                item_names = {line.idx: line.item_name for line in saved.items}
            for application in applications:
                # Sales reports contain attributed promotions, not placeholder invoice rows.
                if not application.get('promotion') or not application.get('promotion_type'):
                    continue
                row = dict(application)
                row['item_name'] = item_names.get(row.get('item_row'))
                row.update(invoice=invoice.name, **{k: v for k, v in invoice.items() if k != 'name'})
                if filters.get('promotion') and row.get('promotion') != filters.promotion:
                    continue
                if filters.get('status') and row.get('status') != filters.status:
                    continue
                yield row
        if len(invoices) < 500:
            break
        start += 500


def columns(summary=False):
    specs = [('promotion_type','Promotion Type','Data',160), ('promotion','Promotion','Data',180),
             ('currency','Currency','Link',85), ('status','Schedule Check','Data',130)]
    if summary:
        specs += [('company','Company','Link',150), ('uom','UOM','Data',90), ('receipts','Receipts','Int',90), ('return_receipts','Return Receipts','Int',110)]
    else:
        specs += [('invoice','POS Invoice','Link',170), ('posting_date','Sale Date','Date',100),
                  ('posting_time','Sale Time','Time',90), ('pos_branch','Branch','Data',130),
                  ('pos_counter','Counter','Data',130), ('pos_cashier','Cashier','Data',130),
                  ('item_code','Item','Link',130), ('barcode','Barcode','Data',120), ('uom','UOM','Data',90)]
    specs += [('quantity','Net Quantity','Float',100), ('free_quantity','Net Free Quantity','Float',120),
              ('discount_amount','Net Promotion Discount (Ex VAT)','Currency',180),
              ('sales_amount','Attributed Net Sales (Ex VAT)','Currency',180)]
    if not summary:
        specs += [('reason','Check Notes','Data',350)]
    return [dict(fieldname=k, label=label, fieldtype=t, width=w,
                 **({'options': {'invoice':'POS Invoice','item_code':'Item','currency':'Currency','company':'Company'}.get(k, 'currency')}
                    if t in ('Link','Currency') else {})) for k,label,t,w in specs]


def execute_summary(filters=None):
    filters = frappe._dict(filters or {})
    # Old bookmarked check filters must not silently hide part of a sales summary.
    filters.pop('status', None)
    grouped = {}
    for row in report_rows(filters):
        if row.get('status') == 'Not Reported' or not row.get('promotion'):
            continue
        key = tuple(row.get(k) for k in ('promotion_type','promotion','currency','company','uom'))
        if key not in grouped:
            grouped[key] = dict(zip(('promotion_type','promotion','currency','company','uom'),key),
                                receipts=set(), return_receipts=set(), quantity=0, free_quantity=0,
                                discount_amount=0, sales_amount=0)
        target = grouped[key]
        target['return_receipts' if row.get('is_return') else 'receipts'].add(row['invoice'])
        if not row.get('excluded_from_totals'):
            for field in ('quantity','free_quantity','discount_amount','sales_amount'):
                target[field] += flt(row.get(field))
    for target in grouped.values():
        for field in ('receipts','return_receipts'):
            target[field] = len(target[field])
    report_columns = [c for c in columns(True) if c['fieldname'] != 'status'
                      and (c['fieldname'] != 'company' or not filters.get('company'))]
    labels = {
        'promotion': 'Promotion Name', 'receipts': 'Sales Bills', 'return_receipts': 'Return Bills',
        'quantity': 'Net Quantity (Incl. Free)', 'free_quantity': 'Free Quantity',
        'uom': 'Unit', 'discount_amount': 'Promotion Discount (Excl. VAT)',
        'sales_amount': 'Net Sales (Excl. VAT)',
    }
    order = ['promotion_type', 'promotion', 'company', 'receipts', 'return_receipts',
             'quantity', 'free_quantity', 'uom', 'discount_amount', 'sales_amount', 'currency']
    for column in report_columns:
        column['label'] = labels.get(column['fieldname'], column['label'])
        if column['fieldname'] in ('quantity', 'free_quantity'):
            column['width'] = 180
        elif column['fieldname'] == 'discount_amount':
            column['width'] = 215
    report_columns.sort(key=lambda c: order.index(c['fieldname']))
    return report_columns, list(grouped.values()), None


def exchange_applications(payload, rows):
    """Preserve application-to-line identity when existing exchange code splits a bill."""
    applications = payload.get('applied_promotions')
    if not isinstance(applications, list):
        return applications
    positions = {row.get('_promotion_source_row'): idx for idx, row in enumerate(rows, 1)}
    result = []
    for application in applications:
        if not isinstance(application, dict):
            continue
        source, error = resolve_item_row(application, payload.get('items') or [])
        if error:
            # Keep unresolved evidence visible, and prevent re-matching against a
            # split subset from turning an originally ambiguous match into a guess.
            result.append(dict(application, item_row=0))
        elif source in positions:
            result.append(dict(application, item_row=positions[source]))
    return result
