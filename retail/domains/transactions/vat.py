"""VAT-inclusive transaction item handling shared by sales and purchase forms."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils import flt
from retail.domains.transactions.trading_vat import vat_disabled, prepare as prepare_trading_vat

PURCHASE_ITEM_DOCTYPES = {
	"Purchase Order Item",
	"Purchase Receipt Item",
	"Purchase Invoice Item",
	"Supplier Quotation Item",
	"Material Request Item",
	"Subcontracting Order Item",
	"Subcontracting Receipt Item",
}

SALES_ITEM_DOCTYPES = {
	"Sales Order Item",
	"Delivery Note Item",
	"Sales Invoice Item",
	"POS Invoice Item",
	"Quotation Item",
	"Opportunity Item",
}

MIXED_ITEM_DOCTYPES = {
	"Blanket Order Item",
}

VAT_RATE_ITEM_DOCTYPES = PURCHASE_ITEM_DOCTYPES | SALES_ITEM_DOCTYPES | MIXED_ITEM_DOCTYPES

VAT_TAX_DOCTYPES = {
	"Purchase Order": "Purchase Tax",
	"Purchase Receipt": "Purchase Tax",
	"Purchase Invoice": "Purchase Tax",
	"Sales Invoice": "Sales Tax",
	"Sales Order": "Sales Tax",
	"Delivery Note": "Sales Tax",
	"POS Invoice": "Sales Tax",
	"Quotation": "Sales Tax",
}


def set_vat_rates(doc, method=None):
	"""Keep row VAT-inclusive/exclusive helper rates in sync before save."""
	if doc.get("is_consolidated"):
		set_row_vat_amounts(doc)
		return  # Consolidation carries the original POS tax amounts.
	from retail.pos_completed_sale import payload_for
	if payload_for(doc):
		from retail.pos_completed_sale import restore
		restore(doc)
		return
	if prepare_trading_vat(doc):
		doc.calculate_taxes_and_totals()
		_refresh_total_in_words(doc)
		return
	prepare_external_pos_taxes(doc)

	_prefetch_vat_templates(doc)
	for item in doc.get("items", []):
		if not item.get("item_code"):
			continue
		if not item.meta.has_field("custom_rate_including_vat"):
			continue
		if not item.get("item_tax_template") and item.meta.has_field("item_tax_template"):
			template = _get_transaction_item_vat_template(
				item.item_code,
				child_doctype=item.doctype,
				parent_doctype=doc.doctype,
				transaction_type=doc.get("transaction_type"),
				company=doc.get("company"),
				throw=not _is_external_pos(doc),
			)
			if template:
				item.item_tax_template = template

		vat_rate = get_transaction_item_vat_rate(
			item.item_code,
			child_doctype=item.doctype,
			parent_doctype=doc.doctype,
			transaction_type=doc.get("transaction_type"),
			item_tax_template=item.get("item_tax_template"),
			company=doc.get("company"),
			throw=not _is_external_pos(doc),
		)
		exclusive_rate = flt(item.get("rate"))
		inclusive_rate = flt(item.get("custom_rate_including_vat"))
		qty = flt(item.get("qty"))
		inclusive_amount = flt(item.get("custom_amount_including_vat"))
		exclusive_amount = flt(item.get("amount"))

		if inclusive_amount and not inclusive_rate and qty:
			inclusive_rate = inclusive_amount / qty

		if exclusive_amount and not exclusive_rate and qty:
			exclusive_rate = exclusive_amount / qty

		if inclusive_rate and not exclusive_rate:
			exclusive_rate = inclusive_rate / (1 + (vat_rate / 100))

		if exclusive_rate:
			inclusive_rate = exclusive_rate * (1 + (vat_rate / 100))
			item.custom_rate_including_vat = flt(inclusive_rate, item.precision("rate"))
			item.rate = flt(exclusive_rate, item.precision("rate"))
			if item.meta.has_field("amount"):
				item.amount = flt(qty * exclusive_rate, item.precision("amount"))

		if item.meta.has_field("custom_amount_including_vat"):
			amount_precision = item.precision("amount") if item.meta.has_field("amount") else item.precision("rate")
			item.custom_amount_including_vat = flt(
				qty * flt(item.get("custom_rate_including_vat")),
				amount_precision,
			)

	apply_transaction_vat_taxes(doc)
	set_row_vat_amounts(doc)


def set_row_vat_amounts(doc, method=None):
	"""Store row VAT in document currency from quantity and exclusive rate."""
	import json
	from retail.pos_completed_sale import payload_for, restore
	if payload_for(doc):
		restore(doc)
		return

	if vat_disabled(doc):
		for item in doc.get("items") or []:
			item.custom_vat_amount = 0
		return
	for item in doc.get("items") or []:
		if not item.meta.has_field("custom_vat_amount"):
			continue
		if not item.get("item_code"):
			item.custom_vat_amount = 0
			continue
		rates = item.get("item_tax_rate")
		rates = json.loads(rates) if isinstance(rates, str) and rates else rates
		if rates:
			rate = sum(flt(value) for value in rates.values())
		else:
			rate = get_transaction_item_vat_rate(
				item.get("item_code"), child_doctype=item.doctype,
				parent_doctype=doc.doctype, transaction_type=doc.get("transaction_type"),
				item_tax_template=item.get("item_tax_template"),
				company=doc.get("company"),
			)
		amount = flt(item.get("qty")) * flt(item.get("rate"))
		item.custom_vat_amount = flt(flt(amount) * rate / 100, item.precision("custom_vat_amount"))


def _is_external_pos(doc):
	return doc.doctype == "POS Invoice" and doc.get("pos_sync_source") == "Offline POS"


def prepare_external_pos_taxes(doc, method=None):
	"""Set item-owned VAT before ERPNext validates payment and invoice totals."""
	if not _is_external_pos(doc):
		return
	from retail.pos_completed_sale import payload_for, prepare
	if payload_for(doc):
		prepare(doc)
		return
	doc.taxes_and_charges = None
	doc.set("taxes", [])
	for item in doc.get("items") or []:
		item.item_tax_template = frappe.get_cached_value("Item", item.item_code, "custom_tax")
	for group in _get_transaction_vat_groups(doc, "Sales Tax").values():
		doc.append("taxes", {
			"charge_type": "On Net Total",
			"account_head": group["account_head"],
			"description": group["description"],
			"included_in_print_rate": 0,
			# ERPNext rebuilds item maps during calculation. Missing accounts must
			# therefore fall back to zero on the invoice tax row itself.
			"rate": 0,
			"cost_center": doc.get("cost_center"),
		})
	_apply_item_vat_tax_rates(doc)


def apply_transaction_vat_taxes(doc):
	"""Mirror item VAT templates into the standard Taxes table for ERPNext totals."""
	if prepare_trading_vat(doc):
		doc.calculate_taxes_and_totals()
		return
	tax_label = VAT_TAX_DOCTYPES.get(doc.doctype)
	if not tax_label or not doc.meta.has_field("taxes"):
		return

	doc.set(
		"taxes",
		[row for row in (doc.get("taxes") or []) if not _is_managed_vat_row(row, tax_label)],
	)

	_apply_item_vat_tax_rates(doc)
	for group in _get_transaction_vat_groups(doc, tax_label).values():

		doc.append(
			"taxes",
			{
				"charge_type": "On Net Total",
				"account_head": group["account_head"],
				"description": group["description"],
				"category": "Total",
				"add_deduct_tax": "Add",
				"included_in_print_rate": 0,
				"rate": 0 if _is_external_pos(doc) else group["rate"],
				"cost_center": doc.get("cost_center"),
			},
		)

	_disable_rounded_total(doc)
	doc.calculate_taxes_and_totals()
	if not _is_external_pos(doc):
		_apply_explicit_vat_totals(doc, tax_label)
	_refresh_total_in_words(doc)


@frappe.whitelist()
def get_transaction_vat_tax_rows(doc):
	"""Return managed VAT rows for live ERPNext totals calculation."""
	doc = frappe.get_doc(frappe.parse_json(doc))
	if vat_disabled(doc):
		from retail.domains.transactions.trading_vat import vat_accounts
		accounts = list(vat_accounts(doc))
		source_rates = {row.name: row.rate for row in doc.items}
		prepare_trading_vat(doc)
		return {"vat_disabled": True, "vat_accounts": accounts, "tax_rows": [],
		        "item_values": {row.name: {"source_rate": source_rates[row.name], "rate": row.rate,
		            "price_list_rate": row.price_list_rate, "discount_amount": row.discount_amount} for row in doc.items},
		        "item_tax_rates": {row.name: "{}" for row in doc.items}}
	tax_label = VAT_TAX_DOCTYPES.get(doc.doctype)
	if not tax_label or not doc.meta.has_field("taxes"):
		return {"tax_rows": [], "item_tax_rates": {}}
	_prefetch_vat_templates(doc)

	rows = []
	for group in _get_transaction_vat_groups(doc, tax_label).values():
		rows.append(
			{
				"charge_type": "On Net Total",
				"account_head": group["account_head"],
				"description": group["description"],
				"category": "Total",
				"add_deduct_tax": "Add",
				"included_in_print_rate": 0,
				"rate": group["rate"],
				"cost_center": doc.get("cost_center"),
			}
		)

	return {
		"tax_rows": rows,
		"item_tax_rates": _get_item_vat_tax_rates(doc),
	}


@frappe.whitelist()
def recalculate_vat_totals_for_document(doctype, name):
	"""Recalculate VAT rows and totals for one existing transaction document."""
	if doctype not in VAT_TAX_DOCTYPES:
		frappe.throw(frappe._("VAT total recalculation is not enabled for {0}.").format(doctype))

	doc = frappe.get_doc(doctype, name)
	set_vat_rates(doc)

	if doc.docstatus == 1:
		doc.flags.ignore_validate_update_after_submit = True

	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {
		"grand_total": doc.grand_total,
		"total_taxes_and_charges": doc.total_taxes_and_charges,
	}


def ensure_transaction_vat_rate_fields():
	"""Add VAT helper rate fields to transaction item rows."""
	fields = {
		item_doctype: [
			{
				"fieldname": "custom_rate_including_vat",
				"label": "Rate Including VAT",
				"fieldtype": "Currency",
				"options": "currency",
				"insert_after": "rate",
				"in_list_view": 1,
				"columns": 2,
			},
			{
				"fieldname": "custom_vat_amount",
				"label": "VAT Amount",
				"fieldtype": "Currency",
				"options": "currency",
				"insert_after": "amount",
				"read_only": 1,
				"in_list_view": 1,
				"columns": 2,
			},
			{
				"fieldname": "custom_amount_including_vat",
				"label": "Amount Including VAT",
				"fieldtype": "Currency",
				"options": "currency",
				"insert_after": "custom_rate_including_vat",
				"in_list_view": 1,
				"columns": 2,
			},
		]
		for item_doctype in sorted(VAT_RATE_ITEM_DOCTYPES)
	}
	create_custom_fields(
		fields,
		ignore_validate=True,
	)
	for item_doctype in VAT_RATE_ITEM_DOCTYPES:
		_set_item_table_field_property(item_doctype, "rate", "label", "Rate Exclusive VAT", "Data")
		if frappe.get_meta(item_doctype).has_field("amount"):
			_set_item_table_field_property(item_doctype, "amount", "read_only", 0, "Check")
		_set_custom_field_property(item_doctype, "custom_amount_including_vat", "read_only", 0)
		_set_custom_field_property(item_doctype, "custom_vat_amount", "read_only", 1)
		_set_item_table_field_property(item_doctype, "custom_vat_amount", "read_only", 1, "Check")
		_delete_obsolete_vat_fields(item_doctype)
		frappe.db.updatedb(item_doctype)
		frappe.clear_cache(doctype=item_doctype)


@frappe.whitelist()
def get_purchase_item_vat_rate(item_code, throw=False):
	return get_transaction_item_vat_rate(
		item_code,
		child_doctype="Purchase Order Item",
		throw=throw,
	)


@frappe.whitelist()
def get_transaction_item_vat_rate(
	item_code,
	child_doctype=None,
	parent_doctype=None,
	transaction_type=None,
	item_tax_template=None,
	throw=False,
	company=None, is_pos=0, is_consolidated=0, return_against=None,
	docstatus=0, custom_trading_vat_disabled=0,
):
	context = frappe._dict(doctype=parent_doctype, company=company, is_pos=int(is_pos or 0),
	    is_consolidated=int(is_consolidated or 0), return_against=return_against,
	    docstatus=docstatus, custom_trading_vat_disabled=custom_trading_vat_disabled)
	if vat_disabled(context):
		return 0.0
	template = _get_transaction_item_vat_template(
		item_code,
		child_doctype=child_doctype,
		parent_doctype=parent_doctype,
		transaction_type=transaction_type,
		item_tax_template=item_tax_template,
		company=company,
		throw=throw,
	)
	if not template:
		return 0.0

	from retail.domains.item.vat_pricing import get_item_tax_rate

	return flt(get_item_tax_rate(template))


@frappe.whitelist()
def get_transaction_item_vat_rates(
	parent_doctype,
	company=None,
	transaction_type=None,
	is_pos=0,
	is_consolidated=0,
	return_against=None,
	docstatus=0,
	custom_trading_vat_disabled=0,
	rows=None,
):
	"""Return one VAT percent per line, using a single Item read for the batch."""
	rows = frappe.parse_json(rows) or []
	if not isinstance(rows, list):
		rows = []
	pending = [frappe.parse_json(row) if isinstance(row, str) else (row or {}) for row in rows]
	context = frappe._dict(
		doctype=parent_doctype,
		company=company,
		is_pos=int(is_pos or 0),
		is_consolidated=int(is_consolidated or 0),
		return_against=return_against,
		docstatus=docstatus,
		custom_trading_vat_disabled=custom_trading_vat_disabled,
	)
	if vat_disabled(context):
		return [0.0] * len(pending)
	_prefetch_vat_templates(frappe._dict(
		doctype=parent_doctype,
		company=company,
		transaction_type=transaction_type,
		items=[
			frappe._dict(item_code=row.get("item_code"), item_tax_template=row.get("item_tax_template"))
			for row in pending
		],
	))
	return [
		get_transaction_item_vat_rate(
			row.get("item_code"),
			child_doctype=row.get("child_doctype"),
			parent_doctype=parent_doctype,
			transaction_type=transaction_type,
			item_tax_template=row.get("item_tax_template"),
			throw=False,
			company=company,
			is_pos=is_pos,
			is_consolidated=is_consolidated,
			return_against=return_against,
			docstatus=docstatus,
			custom_trading_vat_disabled=custom_trading_vat_disabled,
		)
		for row in pending
	]


def _get_transaction_vat_groups(doc, tax_label):
	groups = {}
	for item in doc.get("items") or []:
		if not item.get("item_code"):
			continue

		template = _get_transaction_item_vat_template(
			item.item_code,
			child_doctype=item.doctype,
			parent_doctype=doc.doctype,
			transaction_type=doc.get("transaction_type"),
			item_tax_template=item.get("item_tax_template"),
			company=doc.get("company"),
		)
		if not template:
			continue

		for tax in _get_item_tax_template_details(template):
			rate = flt(tax.tax_rate)
			if not rate:
				continue

			key = tax.tax_type
			if key not in groups:
				groups[key] = {
					"account_head": tax.tax_type,
					"description": f"{tax_label} [{tax.tax_type}]",
					"rates": set(),
				}
			groups[key]["rates"].add(rate)

	for group in groups.values():
		rates = group.pop("rates", set())
		group["rate"] = rates.pop() if len(rates) == 1 else 0

	return groups


def _apply_item_vat_tax_rates(doc):
	for item in doc.get("items") or []:
		if item.meta.has_field("item_tax_rate"):
			item.item_tax_rate = frappe.as_json(_get_vat_tax_rate_map_for_item(doc, item))


def _apply_explicit_vat_totals(doc, tax_label):
	"""Keep managed VAT totals stable after ERPNext recalculates the document."""
	if not doc.get("taxes"):
		return

	vat_amounts = {}
	for item in doc.get("items") or []:
		if not item.get("item_code"):
			continue

		template = _get_transaction_item_vat_template(
			item.item_code,
			child_doctype=item.doctype,
			parent_doctype=doc.doctype,
			transaction_type=doc.get("transaction_type"),
			item_tax_template=item.get("item_tax_template"),
			company=doc.get("company"),
		)
		if not template:
			continue

		net_amount = flt(item.get("net_amount") or item.get("amount"))
		for tax in _get_item_tax_template_details(template):
			rate = flt(tax.tax_rate)
			if rate:
				vat_amounts[tax.tax_type] = flt(vat_amounts.get(tax.tax_type)) + flt(net_amount * rate / 100)

	conversion_rate = flt(doc.get("conversion_rate")) or 1
	total_vat = 0
	running_total = flt(doc.get("net_total") or doc.get("total"))
	for tax in doc.get("taxes") or []:
		if not _is_managed_vat_row(tax, tax_label):
			continue

		amount = flt(vat_amounts.get(tax.account_head), tax.precision("tax_amount"))
		total_vat += amount
		running_total += amount
		tax.tax_amount = amount
		tax.tax_amount_after_discount_amount = amount
		tax.base_tax_amount = flt(amount * conversion_rate, tax.precision("base_tax_amount"))
		tax.base_tax_amount_after_discount_amount = tax.base_tax_amount
		tax.total = running_total
		tax.base_total = flt(running_total * conversion_rate, tax.precision("base_total"))

	if total_vat:
		doc.total_taxes_and_charges = flt(total_vat, doc.precision("total_taxes_and_charges"))
		doc.base_total_taxes_and_charges = flt(total_vat * conversion_rate, doc.precision("base_total_taxes_and_charges"))
		doc.taxes_and_charges_added = doc.total_taxes_and_charges
		doc.base_taxes_and_charges_added = doc.base_total_taxes_and_charges
		doc.taxes_and_charges_deducted = 0
		doc.base_taxes_and_charges_deducted = 0
		doc.grand_total = flt(flt(doc.get("net_total") or doc.get("total")) + doc.total_taxes_and_charges, doc.precision("grand_total"))
		doc.base_grand_total = flt(doc.grand_total * conversion_rate, doc.precision("base_grand_total"))


def _get_item_vat_tax_rates(doc):
	rates = {}
	for item in doc.get("items") or []:
		if not item.get("name"):
			continue
		rates[item.name] = frappe.as_json(_get_vat_tax_rate_map_for_item(doc, item))
	return rates


def _get_vat_tax_rate_map_for_item(doc, item):
	template = _get_transaction_item_vat_template(
		item.item_code,
		child_doctype=item.doctype,
		parent_doctype=doc.doctype,
		transaction_type=doc.get("transaction_type"),
		item_tax_template=item.get("item_tax_template"),
		company=doc.get("company"),
	)
	if not template:
		return {}

	return {
		tax.tax_type: flt(tax.tax_rate)
		for tax in _get_item_tax_template_details(template)
		if flt(tax.tax_rate)
	}


def _item_template_cache():
	cache = getattr(frappe.local, "_retail_item_vat_templates", None)
	if cache is None:
		cache = {}
		frappe.local._retail_item_vat_templates = cache
	return cache


def _prefetch_vat_templates(doc):
	"""One Item read for every line that still needs its VAT template."""
	field = _get_vat_template_field(parent_doctype=doc.doctype, transaction_type=doc.get("transaction_type"))
	if not field:
		return
	_company_default_vat_template(doc.get("company"), field)
	codes = list(dict.fromkeys(
		item.item_code for item in (doc.get("items") or [])
		if item.get("item_code") and not item.get("item_tax_template")
	))
	cache = _item_template_cache()
	missing = [code for code in codes if (code, field) not in cache]
	if not missing:
		return
	if field not in ("custom_tax", "custom_purchase_tax_template"):
		return
	rows = frappe.db.sql(
		f"select name, `{field}` as template from `tabItem` where name in %(names)s",
		{"names": missing},
		as_dict=True,
	)
	found = set()
	for row in rows:
		cache[(row.name, field)] = row.template
		found.add(row.name)
	for code in missing:
		if code not in found:
			cache[(code, field)] = None


def _company_default_vat_template(company, template_field):
	"""Company VAT default for the sales or purchase side of this document."""
	from retail.domains.item.vat_pricing import COMPANY_VAT_FIELDS

	company_field = COMPANY_VAT_FIELDS.get(template_field)
	if not company or not company_field or not frappe.db.has_column("Company", company_field):
		return None
	cache = _item_template_cache()
	key = ("company", company, company_field)
	if key not in cache:
		cache[key] = frappe.db.get_value("Company", company, company_field) or None
	return cache[key]


def _get_transaction_item_vat_template(
	item_code,
	child_doctype=None,
	parent_doctype=None,
	transaction_type=None,
	item_tax_template=None,
	company=None,
	throw=False,
):
	if item_tax_template:
		return item_tax_template

	template_field = _get_vat_template_field(child_doctype, parent_doctype, transaction_type)
	if not template_field:
		return None

	cache = _item_template_cache()
	key = (item_code, template_field)
	if key not in cache:
		cache[key] = frappe.db.get_value("Item", item_code, template_field)
	template = cache[key] or _company_default_vat_template(company, template_field)
	if not template and throw:
		label = "Purchase VAT Template" if template_field == "custom_purchase_tax_template" else "Sales VAT Template"
		frappe.throw(
			frappe._("Set {0} on the Item or the Company default for item {1}.").format(label, item_code)
		)

	return template


def _get_vat_template_field(child_doctype=None, parent_doctype=None, transaction_type=None):
	if child_doctype in MIXED_ITEM_DOCTYPES or parent_doctype == "Blanket Order":
		return (
			"custom_purchase_tax_template"
			if transaction_type == "Purchasing"
			else "custom_tax"
		)
	if child_doctype in PURCHASE_ITEM_DOCTYPES or parent_doctype in {
		"Purchase Order",
		"Purchase Receipt",
		"Purchase Invoice",
		"Supplier Quotation",
		"Material Request",
		"Subcontracting Order",
		"Subcontracting Receipt",
	}:
		return "custom_purchase_tax_template"
	if child_doctype in SALES_ITEM_DOCTYPES or parent_doctype in {
		"Sales Order",
		"Delivery Note",
		"Sales Invoice",
		"POS Invoice",
		"Quotation",
		"Opportunity",
	}:
		return "custom_tax"
	return None


def _set_item_table_field_property(doctype, fieldname, property_name, value, property_type):
	property_setter_name = f"{doctype}-{fieldname}-{property_name}"
	if frappe.db.exists("Property Setter", property_setter_name):
		frappe.db.set_value("Property Setter", property_setter_name, "value", value, update_modified=False)
		return

	make_property_setter(
		doctype,
		fieldname,
		property_name,
		value,
		property_type,
		validate_fields_for_doctype=False,
	)


def _set_custom_field_property(doctype, fieldname, property_name, value):
	field_name = f"{doctype}-{fieldname}"
	if frappe.db.exists("Custom Field", field_name):
		frappe.db.set_value("Custom Field", field_name, property_name, value, update_modified=False)


def _delete_obsolete_vat_fields(doctype):
	field_name = f"{doctype}-custom_rate_exclusive_vat"
	if frappe.db.exists("Custom Field", field_name):
		frappe.delete_doc(
			"Custom Field",
			field_name,
			ignore_permissions=True,
			force=True,
		)


def _get_item_tax_template_details(template):
	from retail.domains.item.vat_pricing import get_item_tax_template_rows

	return get_item_tax_template_rows(template)


def _get_item_exclusive_amount(item):
	if item.get("rate") not in (None, ""):
		return flt(item.get("qty")) * flt(item.get("rate"))

	return flt(item.get("amount"))


def _is_managed_vat_row(row, tax_label):
	description = (row.get("description") or "").strip()
	return description.startswith(f"{tax_label} [")


def _disable_rounded_total(doc):
	if doc.meta.has_field("disable_rounded_total"):
		doc.disable_rounded_total = 1


def _refresh_total_in_words(doc):
	if hasattr(doc, "set_total_in_words"):
		doc.set_total_in_words()
