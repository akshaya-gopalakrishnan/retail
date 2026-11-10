"""Permission-checked read bundle for PR/PI Quick Entry; no row calculations/writes."""

import frappe
from frappe.client import get as get_document
from retail.domains.transactions.vat import get_transaction_item_vat_rate
from retail.domains.purchase.selling_price import (
    get_item_selling_vat_rate, get_standard_selling_rate,
)


@frappe.whitelist()
def item_data(item_code, parent_doctype, uom=None, transaction_type=None, item_tax_template=None):
    if parent_doctype not in ("Purchase Receipt", "Purchase Invoice"):
        frappe.throw("Quick Entry item data is available for purchase documents only")
    # Identical permission and field-level filtering to frappe.db.get_doc's API.
    item = get_document("Item", item_code)
    child_doctype = parent_doctype + " Item"
    vat_args = dict(item_code=item_code, child_doctype=child_doctype,
                    parent_doctype=parent_doctype, transaction_type=transaction_type,
                    item_tax_template=item_tax_template)
    lookups = [dict(method="retail.domains.transactions.vat.get_transaction_item_vat_rate",
                    args=vat_args, message=get_transaction_item_vat_rate(**vat_args))]
    rates = {}
    # Native Item handlers first use stock/purchase UOM, then the selected packing.
    # Cache each actual UOM once, while returning both implicit/explicit keys.
    for requested in dict.fromkeys((None, item.get("stock_uom"), item.get("purchase_uom"), uom)):
        actual = requested or item.get("stock_uom") or "Nos"
        if actual not in rates:
            rates[actual] = get_standard_selling_rate(item_code, uom=actual)
        lookups.append(dict(method="retail.domains.purchase.selling_price.get_standard_selling_rate",
                            args=dict(item_code=item_code, uom=requested), message=rates[actual]))
    lookups.append(dict(method="retail.domains.purchase.selling_price.get_item_selling_vat_rate",
                        args=dict(item_code=item_code), message=get_item_selling_vat_rate(item_code)))
    return dict(item=item, lookups=lookups)
