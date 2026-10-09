"""Profitability uses signed base net revenue and current posted stock values."""
import frappe
from frappe.utils import flt


def invoice_profitability(invoice, posted_item_costs, *, vat_accounts):
    """Read submitted sales amounts in company currency, without rate fallbacks.

    Callers supply current posted costs keyed by invoice item, and the company's
    explicitly identified VAT accounts. Freight and other taxes are not VAT.
    Distributed discount is already the net (tax-exclusive) invoice reduction;
    adding the header discount as well would count it twice.
    """
    if invoice.get("doctype") not in ("Sales Invoice", "POS Invoice"):
        raise ValueError("Profitability accepts customer sales documents only")
    if invoice.get("docstatus") != 1:
        raise ValueError("Profitability accepts submitted documents only")
    items = invoice.get("items") or []
    taxes = invoice.get("taxes") or []
    net = flt(invoice.get("base_net_total"))
    result = frappe._dict(net_sales=net, gross_sales=0, discount=0,
                         sales_returns=-net if invoice.get("is_return") else 0,
                         vat=sum(flt(t.get("base_tax_amount_after_discount_amount"))
                                 for t in taxes if t.get("account_head") in vat_accounts),
                         revenue_status="Recorded", tax_status="Recorded", cost_status="Posted")
    if invoice.get("base_total_taxes_and_charges") is not None and abs(
        sum(flt(t.get("base_tax_amount_after_discount_amount")) for t in taxes)
        - flt(invoice.get("base_total_taxes_and_charges"))
    ) > 0.01:
        result.tax_status = "Recorded tax rows do not reconcile to header total taxes"
    if not invoice.get("is_return"):
        conversion = flt(invoice.get("conversion_rate")) or 1
        item_discount = sum(item_discount_value(i, conversion) for i in items)
        distributed = sum(flt(i.get("distributed_discount_amount")) * conversion for i in items)
        if item_discount and any(t.get("included_in_print_rate") for t in taxes):
            result.gross_sales = result.discount = None
            result.revenue_status = "Tax-inclusive item discount lacks a verified net discount allocation"
        else:
            result.discount = item_discount + distributed
            result.gross_sales = net + result.discount
    if abs(sum(flt(i.get("base_net_amount")) for i in items) - net) > 0.01:
        result.revenue_status = "Invoice item net amounts do not reconcile to header net total"
        result.gross_sales = result.discount = None
    missing = [i.get("name") for i in items if posted_item_costs.get(i.get("name")) is None]
    result.cost_amount = None if missing or not items else sum(posted_item_costs[i.get("name")] for i in items)
    if result.cost_amount is None:
        result.cost_status = "No matched posted stock valuation: " + ", ".join(missing or ["no invoice items"])
    result.gross_profit, result.profit_percent = profit_values(net, result.cost_amount)
    if invoice.get("is_return"):
        result.profit_percent = None
    return result


def profit_values(net_sales, cogs):
    if net_sales is None or cogs is None:
        return None, None
    profit = flt(net_sales) - flt(cogs)
    return profit, profit / flt(net_sales) * 100 if net_sales else 0


def profitability_total(rows, label_field, revenue="net_sales", margin="profit_percent"):
    """Preserve unavailable inputs and calculate margin from aggregate amounts."""
    total = frappe._dict({label_field: frappe._("Total"), "is_total_row": 1})
    fields = [revenue, "cost_amount"]
    fields += ["gross_sales", "discount", "sales_returns", "vat"]
    for field in fields:
        total[field] = (
            None if any(row.get(field) is None for row in rows)
            else sum(flt(row.get(field)) for row in rows)
        )
    if total.get("vat") is None:
        # Full invoices retain their trustworthy tax-row VAT even if per-item allocation is unknown.
        from collections import defaultdict
        invoices = defaultdict(list)
        for row in rows:
            invoices[(row.get("voucher_type"), row.get("invoice_no"))].append(row)
        if invoices and all(group[0].get("invoice_item_count") == len(group) for group in invoices.values()):
            total.vat = sum(flt(group[0].get("invoice_vat")) for group in invoices.values())
    total.source_status = "; ".join(sorted({r.get("source_status") for r in rows
        if r.get("source_status") and r.get("source_status") != "Recorded / Posted"})) or "Recorded / Posted"
    total.gross_profit, total[margin] = profit_values(total[revenue], total.cost_amount)
    return total


def set_profit(row, revenue="net_sales", margin="profit_percent"):
    if row.get("missing_cost_rows"):
        row.cost_amount = None
    row.gross_profit, row[margin] = profit_values(row.get(revenue), row.get("cost_amount"))


def sales_cost_join():
    # Aggregate split SLEs before joining. Delivery costs are allocated in stock UOM.
    return """
    left join (
        select voucher_type, voucher_no, voucher_detail_no,
            sum(-stock_value_difference) cost_amount, sum(actual_qty) actual_qty
        from `tabStock Ledger Entry`
        where is_cancelled = 0
        group by voucher_type, voucher_no, voucher_detail_no
    ) posted_cost on posted_cost.voucher_type = case when si.update_stock = 1
        then 'Sales Invoice' else 'Delivery Note' end
        and posted_cost.voucher_no = case when si.update_stock = 1
            then si.name else sii.delivery_note end
        and posted_cost.voucher_detail_no = case when si.update_stock = 1
            then sii.name else sii.dn_detail end
    """


def sales_cost_sql():
    return """case when si.update_stock = 1 then posted_cost.cost_amount
        when si.is_return = 1 and posted_cost.actual_qty <= 0 then null
        when not exists (select 1 from `tabDelivery Note` dn
            where dn.name = sii.delivery_note and dn.docstatus = 1) then null
        else posted_cost.cost_amount * sii.stock_qty / nullif(-posted_cost.actual_qty, 0)
        end"""


VALUE_FIELDS = ("gross_sales", "discount", "sales_returns", "net_sales", "vat", "cost_amount")


def profitability_columns(columns=()):
    """One presentation contract, including explicit source discrepancies."""
    replaced = set(VALUE_FIELDS) | {"net_amount", "sales_amount", "return_amount",
        "gross_profit", "margin_percent", "profit_percent", "cost_status", "source_status"}
    result = [c for c in columns if c["fieldname"] not in replaced]
    for field, label in zip(VALUE_FIELDS + ("gross_profit", "profit_percent"),
            ("Gross Sales", "Discount", "Sales Returns", "Net Sales", "VAT", "COGS",
             "Gross Profit", "Gross Profit Margin %")):
        result.append(dict(fieldname=field, label=frappe._(label),
            fieldtype="Percent" if field == "profit_percent" else "Currency", width=145))
    result.append(dict(fieldname="source_status", label=frappe._("Source Status"), fieldtype="Data", width=350))
    return result


def recorded_vat_accounts(company):
    # Explicit VAT-labelled ledger accounts; never treat every Tax account as VAT.
    return set(frappe.get_all("Account", filters={"company": company,
        "account_type": "Tax", "account_name": ["like", "%VAT%"]}, pluck="name"))


def posted_costs(doc):
    if doc.doctype == "Sales Invoice":
        rows = frappe.db.sql(f"""select sii.name, {sales_cost_sql()} cost
            from `tabSales Invoice` si join `tabSales Invoice Item` sii on sii.parent=si.name
            {sales_cost_join()} where si.name=%s""", doc.name, as_dict=True)
    else:
        from retail.retail_app.report.pos_report_utils import pos_cost_joins
        rows = frappe.db.sql(f"""select pii.name,
            coalesce(consolidated_cost.cost_amount,direct_cost.cost_amount) cost
            from `tabPOS Invoice` pi join `tabPOS Invoice Item` pii on pii.parent=pi.name
            {pos_cost_joins()} where pi.name=%s""", doc.name, as_dict=True)
    return {r.name: r.cost for r in rows}


def source_status(doc, values):
    messages = [values[k] for k in ("revenue_status", "tax_status", "cost_status")
                if values[k] not in ("Recorded", "Posted")]
    voucher = doc.get("consolidated_invoice") if doc.doctype == "POS Invoice" else doc.name
    if voucher and not frappe.db.exists("GL Entry", {"voucher_type": "Sales Invoice",
            "voucher_no": voucher, "is_cancelled": 0}):
        messages.append("No active GL for " + voucher)
    if doc.doctype == "POS Invoice" and voucher:
        linked = set(frappe.get_all("Sales Invoice Item", filters={"parent": voucher}, pluck="pos_invoice_item"))
        if any(i.name not in linked for i in doc.items):
            messages.append("Stale or unmatched POS consolidation link: " + voucher)
    item_codes = tuple({i.item_code for i in doc.items})
    warehouses = tuple({i.warehouse for i in doc.items if i.warehouse})
    if item_codes and warehouses:
        pending = frappe.db.sql("""select distinct r.name, r.status
            from `tabRepost Item Valuation` r
            left join `tabStock Ledger Entry` base on base.voucher_type=r.voucher_type and base.voucher_no=r.voucher_no
            where r.company=%s and r.docstatus=1 and r.status in ('Queued','In Progress','Failed')
            and ((r.item_code in %s and r.warehouse in %s)
                or (base.item_code in %s and base.warehouse in %s))""",
            (doc.company, item_codes, warehouses, item_codes, warehouses), as_dict=True)
        messages.extend("Stock repost " + r.status + ": " + r.name for r in pending)
    if voucher and doc.doctype == "Sales Invoice" and doc.get("update_stock") and values.cost_amount is not None:
        gl_cost = frappe.db.sql("""select sum(g.credit-g.debit)
            from `tabGL Entry` g join `tabAccount` a on a.name=g.account
            where g.voucher_type='Sales Invoice' and g.voucher_no=%s and g.is_cancelled=0
            and a.account_type='Stock'""", voucher)[0][0]
        if gl_cost is not None and abs(flt(gl_cost)-values.cost_amount) > .011:
            messages.append("Posted SLE COGS differs from stock GL: " + voucher)
    return "; ".join(messages) or "Recorded / Posted"


def invoice_rows(doc, *, vat_accounts_by_company=None):
    """Allocate persisted invoice fields to items, preserving header reconciliation.

    VAT uses ERPNext's persisted item-wise tax details, in company currency.
    Unknown item allocation remains unavailable instead of guessing a tax rate.
    """
    import json
    costs = posted_costs(doc)
    # The caller owns this memo for one calculation only. Standalone callers
    # and unexpected company/memo values retain the normal lookup path.
    if isinstance(vat_accounts_by_company, dict) and isinstance(doc.company, str):
        if doc.company not in vat_accounts_by_company:
            vat_accounts_by_company[doc.company] = recorded_vat_accounts(doc.company)
        accounts = vat_accounts_by_company[doc.company]
    else:
        accounts = recorded_vat_accounts(doc.company)
    values = invoice_profitability(doc, costs, vat_accounts=accounts)
    status = source_status(doc, values)
    conversion = flt(doc.conversion_rate) or 1
    vat_by_code = {}
    allocation_ok = True
    for tax in doc.taxes:
        if tax.account_head not in accounts:
            continue
        details = json.loads(tax.item_wise_tax_detail or "{}")
        if abs(sum(flt(v[1]) * conversion for v in details.values()) -
               flt(tax.base_tax_amount_after_discount_amount)) > 0.011:
            allocation_ok = False
        for code, detail in details.items():
            vat_by_code[code] = vat_by_code.get(code, 0) + flt(detail[1]) * conversion
    code_totals = {}
    for item in doc.items:
        code_totals[item.item_code] = code_totals.get(item.item_code, 0) + flt(item.base_net_amount)
    rows = []
    for item in doc.items:
        row = frappe._dict({k: doc.get(k) for k in
            ("company", "posting_date", "posting_time", "customer", "customer_name", "is_return", "status", "pos_profile")})
        row.update({k: item.get(k) for k in ("item_code", "item_name", "item_group", "brand", "warehouse", "uom", "stock_uom")})
        row.update(invoice_no=doc.name, sales_invoice=doc.get("consolidated_invoice") if doc.doctype == "POS Invoice" else doc.name,
            pos_invoice=doc.name if doc.doctype == "POS Invoice" else None,
            invoice_item=item.name, invoice_item_count=len(doc.items), invoice_vat=values.vat,
            voucher_type=doc.doctype, voucher_no=doc.name,
            branch=doc.get("pos_branch") or doc.get("branch"),
            counter=doc.get("pos_counter") if doc.doctype == "POS Invoice" else doc.get("custom_counter"),
            cashier=doc.get("pos_cashier") or doc.owner, cashier_employee=doc.get("pos_cashier_employee"),
            terminal_id=doc.get("pos_terminal_id"), van=doc.get("custom_van"),
            van_session=doc.get("custom_van_session"), driver=doc.get("custom_driver"), driver_name=doc.get("custom_driver_name"),
            net_sales=flt(item.base_net_amount), cost_amount=costs.get(item.name),
            qty=flt(item.stock_qty), net_qty=flt(item.stock_qty), items_sold=flt(item.stock_qty),
            sold_qty=0 if doc.is_return else flt(item.stock_qty),
            return_qty=-flt(item.stock_qty) if doc.is_return else 0,
            transaction_type="Return" if doc.is_return else "Sale", source_status=status)
        row.discount = item_discount_value(item, conversion) + flt(item.distributed_discount_amount) * conversion
        row.gross_sales = row.net_sales + row.discount
        row.sales_returns = 0
        if doc.is_return:
            row.gross_sales = row.discount = 0
            row.sales_returns = -row.net_sales
        if values.gross_sales is None:
            row.gross_sales = row.discount = None
        denominator = code_totals[item.item_code]
        row.vat = (vat_by_code.get(item.item_code, 0) * row.net_sales / denominator
                   if denominator else 0) if allocation_ok else None
        if len(doc.items) == 1:
            row.vat = values.vat
        if row.vat is None:
            row.source_status += "; VAT item allocation does not reconcile"
        if doc.doctype == "Sales Invoice" and item.get("pos_invoice"):
            dimensions = frappe.db.get_value("POS Invoice", item.pos_invoice,
                ["pos_branch", "pos_counter", "pos_cashier", "pos_cashier_employee"], as_dict=True)
            if dimensions:
                row.branch, row.counter = dimensions.pos_branch, dimensions.pos_counter
                row.cashier, row.cashier_employee = dimensions.pos_cashier, dimensions.pos_cashier_employee
        row.net_rate = flt(item.base_net_rate)
        row.gross_profit, row.profit_percent = profit_values(row.net_sales, row.cost_amount)
        if doc.is_return:
            row.profit_percent = None
        # Header measures are attached once, never multiplied by item joins.
        row.paid_amount = flt(doc.base_paid_amount) if item.idx == 1 else 0
        row.outstanding_amount = flt(doc.outstanding_amount) * conversion if item.idx == 1 else 0
        rows.append(row)
    # Exact invoice VAT remains trustworthy even when item allocation is unavailable.
    return rows


def profitability_rows(filters=None, doctype="Sales Invoice", *, van=False):
    from frappe.utils import getdate
    filters = frappe._dict(filters or {})
    conditions = {"docstatus": 1}
    for key in ("company", "customer", "pos_profile"):
        if filters.get(key):
            conditions[key] = filters[key]
    conditions["posting_date"] = ["between", [filters.get("from_date") or getdate(), filters.get("to_date") or getdate()]]
    mapping = {"counter": "pos_counter" if doctype == "POS Invoice" else "custom_counter",
               "branch": "pos_branch" if doctype == "POS Invoice" else "branch",
               "cashier": "pos_cashier" if doctype == "POS Invoice" else "owner",
               "cashier_employee": "pos_cashier_employee", "shift": "pos_cashier_shift",
               "pos_invoice": "name", "sales_invoice": "name", "van": "custom_van",
               "van_session": "custom_van_session", "driver": "custom_driver"}
    for key, field in mapping.items():
        if filters.get(key):
            if doctype == "Sales Invoice" and key in ("branch", "counter", "cashier", "cashier_employee"):
                continue  # Filter resolved original POS dimensions below.
            if not frappe.get_meta(doctype).has_field(field) and field not in ("name", "owner"):
                frappe.throw(f"{doctype} does not support the {key} filter")
            conditions[field] = filters[key]
    if van:
        conditions["custom_is_van_sale"] = 1
        from retail.van_assignment import is_operator
        if is_operator():
            sessions = frappe.get_all("Van Session", filters={"custom_salesperson": frappe.session.user}, pluck="name")
            if filters.get("van_session") and filters.van_session not in sessions:
                return []
            conditions["custom_van_session"] = ["in", sessions]
    if filters.get("status") == "Cancelled":
        return []
    if filters.get("status") == "Return":
        conditions["is_return"] = 1
    elif filters.get("status"):
        conditions["status"] = filters.status
    rows = []
    vat_accounts_by_company = {}
    for name in frappe.get_list(doctype, filters=conditions, pluck="name", limit_page_length=0, order_by="posting_date desc, name"):
        for row in invoice_rows(frappe.get_doc(doctype, name), vat_accounts_by_company=vat_accounts_by_company):
            if all(not filters.get(k) or row.get(k) == filters[k] for k in ("item_code", "item_group", "warehouse", "brand", "branch", "counter", "cashier", "cashier_employee")):
                rows.append(row)
    return rows


def aggregate_profitability(rows, fields):
    from collections import defaultdict
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(k) for k in fields)].append(row)
    result = []
    for key, members in groups.items():
        row = profitability_total(members, "_total")
        row.pop("_total", None)
        row.pop("is_total_row", None)
        row.update(dict(zip(fields, key)))
        for field in ("qty", "net_qty", "sold_qty", "return_qty", "items_sold", "paid_amount", "outstanding_amount",
                      "cash_amount", "card_amount", "other_payment_amount", "credit_sales", "credit_notes_issued",
                      "credit_notes_redeemed", "credit_notes_applied", "credit_notes_unresolved", "current_customer_outstanding"):
            if any(field in member for member in members):
                row[field] = sum(flt(m.get(field)) for m in members)
        row.invoice_count = len({m.invoice_no for m in members if not m.is_return})
        row.return_count = len({m.invoice_no for m in members if m.is_return})
        row.item_count = len({m.item_code for m in members})
        row.average_bill_value = row.net_sales / row.invoice_count if row.invoice_count else 0
        row.source_status = "; ".join(sorted({m.source_status for m in members if m.source_status != "Recorded / Posted"})) or "Recorded / Posted"
        if all(m.is_return for m in members):
            row.profit_percent = None
        result.append(row)
    return result


def report_result(rows, columns, groups=None):
    data = aggregate_profitability(rows, groups) if groups else rows
    if data:
        total = profitability_total(rows, next((c["fieldname"] for c in columns if c.get("fieldtype") in ("Data", "Link")), columns[0]["fieldname"]))
        total.source_status = "; ".join(sorted({r.source_status for r in data if r.source_status and r.source_status != "Recorded / Posted"})) or "Recorded / Posted"
        for field in ("cash_amount", "card_amount", "other_payment_amount", "credit_sales", "credit_notes_issued",
                      "credit_notes_redeemed", "credit_notes_applied", "credit_notes_unresolved", "current_customer_outstanding"):
            if any(field in row for row in rows):
                total[field] = sum(flt(row.get(field)) for row in rows)
        data.append(total)
    return profitability_columns(columns), data, None, None, None, True


def item_discount_value(item, conversion):
    return (max(flt(item.get("discount_amount")), 0) * abs(flt(item.get("qty"))) * conversion
            if not item.get("is_free_item") and flt(item.get("rate")) else 0)
