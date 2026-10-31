"""Read-only native list of customer totals, calculated from the loyalty ledger."""
import frappe
from frappe.model.document import Document
from frappe.utils import cint, evaluate_filters, getdate

from retail.loyalty_summary import get_summary, get_entries
from retail.loyalty import available_buckets
from retail.loyalty_display import balances

DOCTYPE = 'Customer Loyalty Balance'
POINT_FIELDS = ('earned_points', 'used_points', 'expired_points', 'available_points')


def consolidate(rows, names=None):
    customers = {}
    for row in rows:
        key = (row['company'], row['customer'])
        if key not in customers:
            customers[key] = frappe._dict(
                doctype=DOCTYPE,
                company=key[0], customer=key[1], customer_name=row.get('customer_name', ''),
                as_of_date=row['as_of_date'], docstatus=0, loyalty_programs=[],
                creation=row.get('creation'), modified=row.get('modified'),
                **{field: 0 for field in POINT_FIELDS})
        result = customers[key]
        for field in POINT_FIELDS:
            result[field] += cint(row[field])
        if row['loyalty_program'] and row['loyalty_program'] not in result.loyalty_programs:
            result.loyalty_programs.append(row['loyalty_program'])
        if row.get('modified') and (not result.modified or row['modified'] > result.modified):
            result.modified = row['modified']
    for index, key in enumerate(sorted(customers), 1):
        result = customers[key]
        result.name = names[key] if names is not None else str(index)
        result.loyalty_programs = ', '.join(sorted(result.loyalty_programs))
    return list(customers.values())


def invoice_details(entries, as_of):
    """One invoice row, even when redemption consumes multiple earning buckets."""
    entries = [entry for entry in entries if entry.posting_date
        and getdate(entry.posting_date) <= getdate(as_of)]
    programs = {}
    for entry in entries:
        programs.setdefault(entry.loyalty_program, []).append(entry)
    invoices = {}
    for program, movements in programs.items():
        movements.sort(key=lambda entry: (str(entry.expiry_date or '9999-12-31'),
            str(entry.posting_date), entry.name))
        totals = balances(movements, movements, as_of)
        available = {bucket.name: count for bucket, count in available_buckets(movements, as_of)}
        for entry in movements:
            if not entry.get('invoice') or not entry.get('invoice_type'):
                continue
            key = (entry.invoice_type, entry.invoice)
            if key not in invoices:
                invoices[key] = frappe._dict(invoice_type=key[0], invoice=key[1],
                    posting_date=entry.posting_date, loyalty_programs=set(),
                    **{field: 0 for field in POINT_FIELDS})
            row = invoices[key]
            row.loyalty_programs.add(program or '')
            points = cint(entry.loyalty_points)
            if not entry.redeem_against and points >= 0:
                row.earned_points += points
                row.expired_points += totals[entry.name]['expired_points']
                row.available_points += available.get(entry.name, 0)
            else:
                # Returns restore points: a negative used value records that credit.
                row.used_points -= points
    result = sorted(invoices.values(), key=lambda row: (str(row.posting_date), row.invoice_type, row.invoice), reverse=True)
    for row in result:
        row.loyalty_programs = ', '.join(sorted(row.loyalty_programs))
    return result


def visible_rows(args):
    frappe.has_permission(DOCTYPE, 'read', throw=True)
    frappe.has_permission('Loyalty Point Entry', 'read', throw=True)
    rows = []
    for company in frappe.get_list('Company', pluck='name', limit_page_length=0):
        rows.extend(get_summary(company))
    from retail.customer_loyalty_names import names
    rows = consolidate(rows, names(rows))
    filters = frappe.parse_json(args.get('filters') or [])
    or_filters = frappe.parse_json(args.get('or_filters') or [])
    if isinstance(or_filters, dict):
        or_filters = [{field: value} for field, value in or_filters.items()]
    return [row for row in rows if evaluate_filters(row, filters)
        and (not or_filters or any(evaluate_filters(row, [condition] if isinstance(condition, (list, tuple))
            else condition) for condition in or_filters))]


class CustomerLoyaltyBalance(Document):
    @staticmethod
    def get_list(args):
        rows = visible_rows(args)
        for order in reversed((args.get('order_by') or 'name asc').split(',')):
            parts = order.strip().rsplit(' ', 1)
            descending = len(parts) > 1 and parts[-1].lower() == 'desc'
            expression = parts[0] if len(parts) > 1 and parts[-1].lower() in ('asc', 'desc') else order.strip()
            field = expression.split('.')[-1].strip('`')
            if rows and field not in rows[0]:
                frappe.throw('Unsupported loyalty balance sort field.')
            rows.sort(key=lambda row: (row.get(field) is None,
                cint(row.name) if field == 'name' else row.get(field)),
                reverse=descending)
        start = cint(args.get('start') or args.get('limit_start'))
        length = cint(args.get('page_length', args.get('limit_page_length', 20)))
        rows = rows[start:start + length] if length else rows[start:]
        if args.get('pluck'):
            return [row.get(args['pluck']) for row in rows]
        if args.get('as_list'):
            fields = args.get('fields') or ['name']
            return [[row.get(field.split('.')[-1].strip('`')) for field in fields] for row in rows]
        return rows

    @staticmethod
    def get_count(args):
        return len(visible_rows(args))

    @staticmethod
    def get_stats(args):
        frappe.has_permission('Loyalty Point Entry', 'read', throw=True)
        return {}

    def load_from_db(self):
        row = next((row for row in visible_rows({}) if row.name == self.name), None)
        if not row:
            frappe.throw('Customer loyalty balance not found.', frappe.DoesNotExistError)
        super(Document, self).__init__(row)
        details = invoice_details(get_entries(self.company, self.customer), self.as_of_date)
        self.set('invoices', details)
        self.invoice_count = len(details)

    def db_insert(self, *args, **kwargs):
        frappe.throw('Loyalty balances are calculated from ledger entries and cannot be edited.')

    db_update = db_insert
    delete = db_insert
