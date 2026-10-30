"""Read-only promotion profitability using posted stock movements, never current rates."""
from collections import Counter

import frappe
from frappe.utils import add_days, date_diff, flt, getdate
from retail.promotions.history import report_rows


def posted_cost(doc, line):
    """Return signed cost in company currency, or None until fully stock-posted."""
    sources = [(doc.doctype, doc.name, line.name)]
    if doc.get('consolidated_invoice'):
        mapped = frappe.get_all('Sales Invoice Item', filters={
            'parent': doc.consolidated_invoice, 'pos_invoice': doc.name,
            'pos_invoice_item': line.name, 'docstatus': 1}, fields=['name', 'parent'])
        sources = [('Sales Invoice', r.parent, r.name) for r in mapped]
    entries = []
    for kind, voucher, detail in sources:
        entries.extend(frappe.get_all('Stock Ledger Entry', filters={
            'voucher_type': kind, 'voucher_no': voucher, 'voucher_detail_no': detail,
            'is_cancelled': 0}, fields=['actual_qty', 'stock_value_difference']))
    # Missing entries, non-stock services and incomplete movements are unknown, not zero cost.
    if not entries or abs(sum(flt(e.actual_qty) for e in entries) + flt(line.stock_qty)) > 0.00001:
        return None
    return -sum(flt(e.stock_value_difference) for e in entries)


def enrich(rows):
    docs, costs = {}, {}
    counts = Counter((r['invoice'], r.get('item_row')) for r in rows if not r.get('excluded_from_totals'))
    result = []
    for source in rows:
        row = frappe._dict(source)
        key = (row.invoice, row.get('item_row'))
        if row.invoice not in docs:
            docs[row.invoice] = frappe.get_doc('POS Invoice', row.invoice)
        doc = docs[row.invoice]
        line = next((i for i in doc.items if i.idx == row.get('item_row')), None)
        row.update(customer=doc.customer, gross_profit=None, cost=None, margin=None,
                   company_currency=frappe.get_cached_value('Company', doc.company, 'default_currency'))
        row['profit_status'] = 'Profit Incomplete'
        if row.get('excluded_from_totals') or not line:
            row['profit_note'] = 'Invalid or excluded promotion item evidence'
        elif counts[key] > 1:
            row['profit_note'] = 'Multiple promotions share this item; profit allocation requires review'
        elif row.status not in ('Schedule Valid', 'Return Linked'):
            row['profit_note'] = row.get('reason') or 'Promotion evidence requires review'
        elif abs(flt(row.quantity) - flt(line.qty)) > 0.00001:
            row['profit_note'] = 'Promotion quantity differs from posted line quantity'
        elif abs(flt(row.sales_amount) * flt(doc.conversion_rate) - flt(line.base_net_amount)) > 0.02:
            row['profit_note'] = 'Promotion sales differ from posted line net amount'
        else:
            if key not in costs:
                costs[key] = posted_cost(doc, line)
            row.cost = costs[key]
            if row.cost is None:
                row['profit_note'] = 'Matching posted stock cost unavailable (including unclosed POS or non-stock items)'
            else:
                row.gross_profit = flt(line.base_net_amount) - row.cost
                row.margin = row.gross_profit / flt(line.base_net_amount) * 100 if line.base_net_amount else None
                row.profit_status = 'Complete'
                row['profit_note'] = 'Cost includes all stock on this line, including free goods'
        row['base_sales'] = flt(row.sales_amount) * flt(doc.conversion_rate)
        row['base_discount'] = flt(row.discount_amount) * flt(doc.conversion_rate)
        result.append(row)
    return result


def comparison_sales(filters, targets, *, current=False):
    """Same observed items/UOM, previous equal-length period; includes all offer states."""
    days = date_diff(filters.to_date, filters.from_date) + 1
    end = filters.to_date if current else add_days(filters.from_date, -1)
    start = filters.from_date if current else add_days(end, 1 - days)
    conditions = dict(docstatus=1, pos_sync_source='Offline POS', posting_date=['between', [start, end]])
    for field in ('company', 'pos_branch', 'pos_counter', 'pos_cashier'):
        if filters.get(field):
            conditions[field] = filters[field]
    totals = {key: 0.0 for key in targets}
    offset = 0
    while True:
        invoices = frappe.get_list('POS Invoice', filters=conditions, fields=['name', 'company'],
                                   limit_start=offset, limit_page_length=500)
        for inv in invoices:
            doc = frappe.get_doc('POS Invoice', inv.name)
            for key, items in targets.items():
                if key[2] == doc.company:
                    totals[key] += sum(flt(i.base_net_amount) for i in doc.items if (i.item_code, i.uom) in items)
        if len(invoices) < 500:
            break
        offset += 500
    return totals, start, end


def summarize(rows):
    groups, targets = {}, {}
    for row in rows:
        key = (row.promotion_type, row.promotion, row.company)
        if key not in groups:
            groups[key] = frappe._dict(promotion_type=key[0], promotion=key[1], company=key[2],
                company_currency=row.company_currency, sales_bills=set(), return_bills=set(), customers=set(),
                base_sales=0, base_discount=0, cost=0, gross_profit=0, incomplete=0, review_rows=0)
            targets[key] = set()
        group = groups[key]
        group['return_bills' if row.is_return else 'sales_bills'].add(row.invoice)
        if not row.is_return and row.customer:
            group.customers.add(row.customer)
        if row.profit_status != 'Complete':
            group.incomplete += 1
        if row.get('excluded_from_totals'):
            group.review_rows += 1
            continue
        targets[key].add((row.item_code, row.uom))
        group.base_sales += row.base_sales
        group.base_discount += row.base_discount
        group.cost += flt(row.cost)
        group.gross_profit += flt(row.gross_profit)
    for group in groups.values():
        for field in ('sales_bills', 'return_bills', 'customers'):
            group[field] = len(group[field])
        group.average_bill = group.base_sales / group.sales_bills if group.sales_bills else None
        group.profit_status = 'Profit Incomplete' if group.incomplete else 'Complete'
        if group.incomplete:
            group.cost = group.gross_profit = group.margin = None
        else:
            group.margin = group.gross_profit / group.base_sales * 100 if group.base_sales else None
    return groups, targets


def columns(detail=False):
    specs = [('promotion_type', 'Promotion Type', 'Data'), ('promotion', 'Promotion', 'Data'),
             ('company', 'Company', 'Link'), ('company_currency', 'Currency', 'Link')]
    if detail:
        specs += [('invoice', 'POS Invoice', 'Link'), ('posting_date', 'Sale Date', 'Date'),
                  ('pos_branch', 'Branch', 'Data'), ('pos_counter', 'Counter', 'Data'),
                  ('customer', 'Customer', 'Link'), ('item_code', 'Item', 'Link'), ('item_name', 'Item Name', 'Data'),
                  ('quantity', 'Net Quantity (Incl. Free)', 'Float'), ('free_quantity', 'Net Free Quantity', 'Float'),
                  ('uom', 'UOM', 'Data')]
    else:
        specs += [('sales_bills', 'Sales Bills', 'Int'), ('return_bills', 'Return Bills', 'Int'),
                  ('customers', 'Purchasing Customers', 'Int'), ('average_bill', 'Net Sales per Sales Bill', 'Currency')]
    specs += [('base_sales', 'Net Sales (Excl. VAT)', 'Currency'),
              ('base_discount', 'Promotion Discount (Excl. VAT)', 'Currency'),
              ('cost', 'Posted Goods Cost (Incl. Free)', 'Currency'), ('gross_profit', 'Gross Profit', 'Currency'),
              ('margin', 'Gross Margin %', 'Percent'), ('profit_status', 'Profit Status', 'Data')]
    if detail:
        specs += [('status', 'Evidence Check', 'Data'), ('profit_note', 'Profit Notes', 'Data')]
    else:
        specs += [('current_item_sales', 'Current Period Same-Item Sales', 'Currency'),
                  ('previous_sales', 'Previous Period Same-Item Sales', 'Currency'),
                  ('sales_change', 'Difference vs Previous Same-Item Sales %', 'Percent')]
    links = dict(company='Company', company_currency='Currency', invoice='POS Invoice', customer='Customer', item_code='Item')
    return [dict(fieldname=k, label=label, fieldtype=kind, width=180,
                 **({'options': 'company_currency'} if kind == 'Currency' else
                    {'options': links[k]} if kind == 'Link' else {})) for k, label, kind in specs]


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not filters.get('from_date') or not filters.get('to_date'):
        frappe.throw('From Date and To Date are required')
    if getdate(filters.from_date) > getdate(filters.to_date):
        frappe.throw('From Date cannot be after To Date')
    filters.pop('status', None)
    rows = enrich(list(report_rows(filters)))
    detail = filters.get('view') == 'Detail'
    if detail:
        # Excluded evidence remains visible but must not contribute amounts.
        for row in rows:
            if row.get('excluded_from_totals'):
                row.base_sales = row.base_discount = row.quantity = row.free_quantity = None
        return columns(True), rows, None
    groups, targets = summarize(rows)
    if filters.get('compare_previous'):
        previous, _, _ = comparison_sales(filters, targets)
        current, _, _ = comparison_sales(filters, targets, current=True)
        for key, group in groups.items():
            group.previous_sales = previous[key]
            group.current_item_sales = current[key]
            group.sales_change = (current[key] - previous[key]) / previous[key] * 100 if previous[key] > 0 else None
    return columns(), list(groups.values()), None


@frappe.whitelist()
def get_cashiers(txt="", company=None):
    """Suggest recorded cashier identities from invoices the user can read."""
    filters = {
        'docstatus': 1, 'pos_sync_source': 'Offline POS',
        'pos_cashier': ['like', '%' + (txt or '') + '%'],
    }
    if company:
        filters['company'] = company
    return [r.pos_cashier for r in frappe.get_list(
        'POS Invoice', filters=filters, fields=['pos_cashier'],
        group_by='pos_cashier', order_by='pos_cashier asc', limit_page_length=50,
    ) if r.pos_cashier]
