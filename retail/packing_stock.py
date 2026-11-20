"""Read-only packing movements, anchored to posted stock ledger quantities.

The saved source UOM/factor identify a packing; current Item conversions must
never rewrite history. Unattributed stock issues prevent a physical-pack claim.
"""
from collections import defaultdict

import frappe
from frappe.utils import flt

# These source child tables retain the transaction UOM and conversion factor.
# Other stock vouchers (including reconciliation) remain stock-UOM movements.
SOURCES = (
    ("Purchase Receipt", "Purchase Receipt Item"),
    ("Purchase Invoice", "Purchase Invoice Item"),
    ("Delivery Note", "Delivery Note Item"),
    ("Sales Invoice", "Sales Invoice Item"),
    ("POS Invoice", "POS Invoice Item"),
    ("Stock Entry", "Stock Entry Detail"),
)


def packing_key(uom, factor):
    return (uom or "", round(flt(factor), 9))


def get_packing_movements(item_codes):
    """One bounded aggregate query; source rows join by their primary keys.

    Transfers retain both warehouse legs. Only SLE quantities are summed, so
    invoices without stock updates and POS source documents are never added
    on top of their stock-posting vouchers. Cancelled entries are excluded.
    """
    if not item_codes:
        return []
    joins, uoms, factors = [], [], []
    for index, (voucher, child) in enumerate(SOURCES):
        alias = f"source_{index}"
        joins.append(
            f"left join `tab{child}` {alias} on sle.voucher_type = '{voucher}' "
            f"and {alias}.name = sle.voucher_detail_no "
            f"and {alias}.parent = sle.voucher_no and {alias}.item_code = sle.item_code"
        )
        # Missing/invalid conversion is unknown, not an assumed factor of one.
        uoms.append(f"case when {alias}.conversion_factor > 0 then nullif({alias}.uom, '') end")
        factors.append(f"case when {alias}.conversion_factor > 0 then {alias}.conversion_factor end")
    return frappe.db.sql(
        f"""select sle.item_code, sle.warehouse,
            coalesce({', '.join(uoms)}, '') as uom,
            coalesce({', '.join(factors)}, 0) as factor,
            sum(case when sle.actual_qty > 0 then sle.actual_qty else 0 end) as in_stock_qty,
            sum(case when sle.actual_qty < 0 then -sle.actual_qty else 0 end) as out_stock_qty
        from `tabStock Ledger Entry` sle
        {' '.join(joins)}
        where sle.item_code in %(item_codes)s and sle.is_cancelled = 0
            and sle.actual_qty != 0
        group by 1, 2, 3, 4""",
        {"item_codes": tuple(dict.fromkeys(item_codes))},
        as_dict=True,
    )


def apply_packing_stock(rows, movements):
    """Attach recorded pack counts without changing parent stock-UOM totals.

    Alternate barcodes for one UOM/factor share one balance. A loose issue,
    unknown source, removed packing, or negative packing balance makes the
    remaining physical packing count unprovable; expose null in that case.
    """
    definitions = defaultdict(set)
    stock_uoms = {}
    for row in rows:
        stock_uoms[row.item_code] = row.stock_uom
        if row.get("uom") and flt(row.get("conversion_factor")) > 0:
            definitions[row.item_code].add(packing_key(row.uom, row.conversion_factor))

    totals = defaultdict(lambda: [0.0, 0.0])
    uncertain = set()
    ledger_balance = defaultdict(float)
    item_totals = defaultdict(lambda: [0.0, 0.0])
    for movement in movements:
        item = movement.item_code
        incoming, outgoing = flt(movement.in_stock_qty), flt(movement.out_stock_qty)
        ledger_balance[item] += incoming - outgoing
        item_totals[item][0] += incoming
        item_totals[item][1] += outgoing
        key = packing_key(movement.uom, movement.factor)
        factor = flt(movement.factor)
        if movement.uom == stock_uoms.get(item) and factor == 1 and outgoing:
            uncertain.add(item)
        if factor > 0 and key in definitions[item]:
            totals[(item, key)][0] += incoming / factor
            totals[(item, key)][1] += outgoing / factor
            if outgoing > incoming + 1e-8:
                uncertain.add(item)
        elif not (movement.uom == stock_uoms.get(item) and factor == 1 and outgoing == 0):
            # Loose receipts cannot consume a box; loose issues can. Unknown
            # receipts/adjustments cannot be attributed to a physical packing.
            uncertain.add(item)

    for row in rows:
        row.in_qty, row.out_qty = item_totals[row.item_code]
        if not row.get("uom"):
            row.packing_in_qty = row.in_qty
            row.packing_out_qty = row.out_qty
            row.packing_recorded_balance = row.real_stock_qty
            row.packing_balance_known = True
            row.packing_stock_qty = row.real_stock_qty
            continue
        if flt(row.get("conversion_factor")) <= 0:
            row.packing_balance_known = False
            row.packing_stock_qty = None
            row.packing_in_qty = None
            row.packing_out_qty = None
            row.packing_recorded_balance = None
            continue
        incoming, outgoing = totals[(row.item_code, packing_key(row.uom, row.conversion_factor))]
        known = row.item_code not in uncertain and abs(
            ledger_balance[row.item_code] - flt(row.real_stock_qty)
        ) < 1e-6
        row.packing_in_qty = incoming
        row.packing_out_qty = outgoing
        row.packing_recorded_balance = incoming - outgoing
        row.packing_balance_known = known
        row.packing_stock_qty = incoming - outgoing if known else None
