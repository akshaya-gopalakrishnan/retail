"""Permission-aware receipt lookup for the Desk invoice finder."""
import frappe
from frappe import _
from frappe.utils import get_datetime, get_timedelta

INVOICE_TYPES = ("POS Invoice", "Sales Invoice")
LIMIT = 100


def date_windows(start, end):
    """Split a datetime interval into disjoint date/time filters (inclusive)."""
    start = get_datetime(start) if start else None
    end = get_datetime(end) if end else None
    if start and end and start > end:
        frappe.throw(_("From date/time must be before To date/time."))
    if start and end and start.date() == end.date():
        return [[["posting_date", "=", start.date()],
                 ["posting_time", ">=", start.time()], ["posting_time", "<=", end.time()]]]
    windows = []
    middle = []
    if start:
        first = [["posting_date", "=", start.date()], ["posting_time", ">=", start.time()]]
        windows.append(first)
        middle.append(["posting_date", ">", start.date()])
    if end:
        windows.append([["posting_date", "=", end.date()], ["posting_time", "<=", end.time()]])
        middle.append(["posting_date", "<", end.date()])
    windows.append(middle)
    return windows


@frappe.whitelist()
def search_invoices(filters=None):
    filters = frappe.parse_json(filters) if isinstance(filters, str) else filters
    if filters is not None and not isinstance(filters, dict):
        frappe.throw(_("Invalid search filters."))
    filters = filters or {}
    invoice_type = filters.get("invoice_type") or "All"
    if invoice_type not in (*INVOICE_TYPES, "All"):
        frappe.throw(_("Invalid invoice type."))
    if not any(filters.get(key) for key in ("bill_number", "from_datetime", "to_datetime", "customer", "cashier", "counter", "branch")):
        frappe.throw(_("Enter a bill number or at least one search filter."))
    if invoice_type != "All" and not frappe.has_permission(invoice_type, "read"):
        frappe.throw(_("You do not have permission to read invoices."), frappe.PermissionError)
    windows = date_windows(filters.get("from_datetime"), filters.get("to_datetime"))
    rows = []
    permitted = []
    for doctype in INVOICE_TYPES if invoice_type in ("All", "Sales Invoice") else (invoice_type,):
        if not frappe.has_permission(doctype, "read"):
            continue
        permitted.append(doctype)
        meta = frappe.get_meta(doctype)
        fields = ["name", "posting_date", "posting_time", "customer", "customer_name",
                  "grand_total", "currency", "docstatus", "status"]
        optional = ["pos_bill_no", "pos_branch", "pos_counter", "pos_cashier_employee",
                    "pos_cashier", "consolidated_invoice"]
        fields += [field for field in optional if meta.has_field(field)]
        query_filters = []
        unsupported = False
        for key, field in (("customer", "customer"), ("cashier", "pos_cashier_employee"),
                           ("counter", "pos_counter"), ("branch", "pos_branch")):
            if filters.get(key):
                if not meta.has_field(field):
                    unsupported = True
                    break
                query_filters.append([field, "=", filters[key]])
        if unsupported:
            continue
        bill = str(filters.get("bill_number") or "").strip()
        bill_filters = [["name", "=", bill]] if bill else []
        if bill and meta.has_field("pos_bill_no"):
            bill_filters.append(["pos_bill_no", "=", bill])
        for window in windows:
            # get_list applies document permissions and user/branch restrictions.
            found = frappe.get_list(doctype, fields=fields, filters=query_filters + window,
                or_filters=bill_filters, order_by="posting_date desc, posting_time desc, name desc",
                page_length=LIMIT + 1)
            for row in found:
                row["invoice_type"] = doctype
                rows.append(row)
    if not permitted:
        frappe.throw(_("You do not have permission to read invoices."), frappe.PermissionError)
    if invoice_type == "Sales Invoice":
        # POS receipts carry terminal metadata; their accounting invoices do not.
        receipts = [row for row in rows if row["invoice_type"] == "POS Invoice" and row.get("consolidated_invoice")]
        sales = {row["name"]: row for row in rows if row["invoice_type"] == "Sales Invoice"}
        if receipts and frappe.has_permission("Sales Invoice", "read"):
            linked = frappe.get_list("Sales Invoice", filters={"name": ["in", [row["consolidated_invoice"] for row in receipts]]},
                fields=["name", "docstatus", "status"], page_length=len(receipts))
            allowed = {row.name: row for row in linked}
            for receipt in receipts:
                name = receipt["consolidated_invoice"]
                if name in allowed:
                    sales[name] = dict(receipt, name=name, invoice_type="Sales Invoice",
                        pos_invoice=receipt["name"], docstatus=allowed[name].docstatus, status=allowed[name].status)
        rows = list(sales.values())
    rows.sort(key=lambda row: (str(row["posting_date"]), get_timedelta(row["posting_time"]).total_seconds(), row["name"]), reverse=True)
    rows = rows[:LIMIT + 1]
    for field, doctype, title, target in (("pos_cashier_employee", "Employee", "employee_name", "cashier_name"),
                                          ("pos_counter", "POS Branch Counter", "counter_name", "counter_name")):
        names = list({row.get(field) for row in rows if row.get(field)})
        if names and frappe.has_permission(doctype, "read"):
            labels = {row.name: row.get(title) for row in frappe.get_list(doctype,
                filters={"name": ["in", names]}, fields=["name", title], page_length=len(names))}
            for row in rows:
                row[target] = labels.get(row.get(field))
    return {"invoices": rows[:LIMIT], "has_more": len(rows) > LIMIT}
