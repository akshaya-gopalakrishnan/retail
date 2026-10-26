"""Additional downloads on the existing Promo Price endpoint.

Keep the legacy ``promotions`` array exclusively for Promo Price. Schemes are
configuration; their generated Pricing Rules are the executable representation.
"""

from collections import defaultdict

import frappe
from frappe.utils import cint, getdate, nowdate

from retail.promotions.api_payload import matching_item_groups
from retail.promotions.history import version


def additional_promotions(counter, modified_after=None):
	from retail.api.gift_vouchers import get_gift_voucher_promotions
	from retail.api.pos_sync import get_pos_buy_x_get_y_promotions

	args = dict(branch=counter.branch, counter_code=counter.counter_code,
		modified_after=modified_after)
	sources = _retail_scheme_sources()
	return {
		"buy_x_get_y_promotions": get_pos_buy_x_get_y_promotions(**args)["promotions"],
		"gift_voucher_promotions": get_gift_voucher_promotions(args)["promotions"],
		"loyalty_programs": _loyalty_programs(counter, modified_after),
		"pricing_rules": _selling_documents("Pricing Rule", counter, modified_after, sources),
		"promotional_schemes": _selling_documents("Promotional Scheme", counter, modified_after, sources),
		**_loyalty_snapshot(counter),
		**_voucher_snapshot(counter),
	}


def _retail_scheme_sources():
	return {
		row.promotional_scheme: {"source_promotion_type": row.parenttype, "source_promotion": row.parent}
		for row in frappe.get_all("Promotion Linked Scheme",
			filters={"parenttype": ["in", ["Promo Price", "Buy X Get Y Promotion"]]},
			fields=["promotional_scheme", "parenttype", "parent"])
	}


def _scoped_documents(doctype, counter, modified_after, **filters):
	if modified_after:
		filters["modified"] = [">", modified_after]
	for name in frappe.get_all(doctype, filters=filters, pluck="name", order_by="modified, name"):
		doc = frappe.get_doc(doctype, name)
		if doc.get("company") and doc.company != counter.company:
			continue
		if doc.get("warehouse") and doc.warehouse != counter.warehouse:
			continue
		yield doc


def _selling_documents(doctype, counter, modified_after, sources):
	rows = []
	for doc in _scoped_documents(doctype, counter, modified_after, selling=1):
		data = doc.as_dict()
		data["promotion_version"] = version(doc)
		data["enabled"] = int(not cint(doc.get("disable")))
		data["disabled"] = int(not data["enabled"])
		for field in ("valid_from", "valid_upto"):
			data[field] = getdate(doc.get(field)).isoformat() if doc.get(field) else None
		for row in data.get("item_groups") or []:
			row["matching_item_groups"] = matching_item_groups(row.get("item_group"))
		if doc.get("other_item_group"):
			data["other_matching_item_groups"] = matching_item_groups(doc.other_item_group)
		source = sources.get(doc.name if doctype == "Promotional Scheme" else doc.get("promotional_scheme"))
		if source:
			data.update(source)
		# Never apply a scheme AND its rules, or a Retail offer AND its ERP rules.
		data["apply_in_pos"] = int(doctype == "Pricing Rule" and not source)
		rows.append(data)
	return rows


def _loyalty_programs(counter, modified_after):
	fields = ("name", "loyalty_program_name", "loyalty_program_type", "from_date", "to_date",
		"customer_group", "customer_territory", "auto_opt_in", "conversion_factor", "expiry_duration",
		"expense_account", "company", "cost_center", "project", "modified")
	rows = []
	for doc in _scoped_documents("Loyalty Program", counter, modified_after):
		data = {field: doc.get(field) for field in fields}
		for field in ("from_date", "to_date"):
			data[field] = getdate(doc.get(field)).isoformat() if doc.get(field) else None
		data["collection_rules"] = [
			{field: rule.get(field) for field in ("name", "idx", "tier_name", "min_spent", "collection_factor")}
			for rule in doc.get("collection_rules") or []
		]
		rows.append(data)
	return rows


def _loyalty_snapshot(counter):
	"""Replace these snapshots on every download, including incremental requests.

	Loyalty entries can be deleted on cancellation, and balances change when
	points expire without any modified timestamp changing. A delta alone cannot
	represent those events reliably.
	"""
	from retail.loyalty import available_buckets

	as_of = nowdate()
	entries = frappe.get_all("Loyalty Point Entry", filters={"company": counter.company},
		fields=["name", "customer", "loyalty_program", "loyalty_program_tier", "company",
			"loyalty_points", "purchase_amount", "posting_date", "expiry_date", "redeem_against",
			"invoice_type", "invoice", "modified"], order_by="posting_date, name", limit_page_length=0)
	for entry in entries:
		for field in ("posting_date", "expiry_date"):
			entry[field] = getdate(entry[field]).isoformat() if entry.get(field) else None

	grouped = defaultdict(list)
	for entry in entries:
		grouped[(entry.customer, entry.loyalty_program)].append(entry)
	for movements in grouped.values():
		totals = _loyalty_point_totals(movements, as_of)
		totals["available_points"] = sum(balance for _, balance in available_buckets(movements, as_of))
		for entry in movements:
			entry.update(totals)
			entry["as_of_date"] = as_of
	return {
		"loyalty_point_entries": entries,
		"loyalty_snapshot": {"mode": "full", "company": counter.company, "as_of_date": as_of},
	}



def _loyalty_point_totals(entries, as_of):
	"""Summarize earning buckets; restorations reduce used, not increase earned."""
	as_of = getdate(as_of)
	movements = defaultdict(int)
	for entry in entries:
		if entry.redeem_against:
			movements[entry.redeem_against] += cint(entry.loyalty_points)
	totals = dict(earned_points=0, used_points=0, expired_points=0)
	for entry in entries:
		points = cint(entry.loyalty_points)
		if entry.redeem_against or points <= 0:
			continue
		if not entry.posting_date or getdate(entry.posting_date) > as_of:
			continue
		totals["earned_points"] += points
		totals["used_points"] += max(0, -movements[entry.name])
		if entry.expiry_date and getdate(entry.expiry_date) < as_of:
			totals["expired_points"] += max(0, points + movements[entry.name])
	totals["used_points"] += sum(-cint(entry.loyalty_points) for entry in entries
		if not entry.redeem_against and cint(entry.loyalty_points) < 0
		and entry.get("invoice_type") == "POS Invoice" and entry.posting_date
		and getdate(entry.posting_date) <= as_of)
	return totals


def _voucher_snapshot(counter):
	"""Company/warehouse scoped full snapshot, including unusable/deleted cards.

	Do not use modified_after: expiry and manual deletion need replacement semantics.
	Read batches and restrictions in bulk rather than loading a document per card.
	"""
	from frappe.utils import flt, get_system_timezone, now_datetime
	from retail.api.gift_vouchers import invalid_reason

	batches = frappe.get_all("Voucher Card Batch", filters={"company": counter.company},
		fields=["name", "title", "company", "currency", "voucher_amount", "card_count",
			"valid_from", "expiry_date", "use_redemption_hours", "active_from_time", "active_to_time",
			"activate_all_cards", "generation_status", "generated_count", "all_products", "logo", "terms",
			"modified"], order_by="name", limit_page_length=0)
	by_batch = {row.name: row for row in batches}
	if by_batch:
		restrictions = frappe.get_all("Voucher Card Restriction",
			filters={"parent": ["in", list(by_batch)], "parenttype": "Voucher Card Batch"},
			fields=["parent", "idx", "item_code", "brand", "item_group"],
			order_by="parent, idx", limit_page_length=0)
		for restriction in restrictions:
			parent = restriction.pop("parent")
			restriction["matching_item_groups"] = matching_item_groups(restriction.get("item_group"))
			by_batch[parent].setdefault("restrictions", []).append(restriction)
	for batch in batches:
		batch.setdefault("restrictions", [])
		batch["online_redemption_required"] = True
		_activation_payload(batch)

	entries = frappe.get_all("Gift Voucher Ledger", filters={"company": counter.company},
		or_filters=[["warehouse", "=", counter.warehouse], ["warehouse", "is", "not set"]],
		fields=["*"], order_by="name", limit_page_length=0)
	currency = frappe.get_cached_value("Company", counter.company, "default_currency")
	for row in entries:
		# Keep every saved business field, including issue/redeem links and customer details.
		row["voucher_kind"] = "Voucher Card" if row.get("voucher_card_batch") else "Promotion Voucher"
		row["currency"] = row.get("currency") or currency
		row["voucher_amount"] = flt(row.voucher_amount)
		row["balance_amount"] = flt(row.balance_amount)
		row["reason"] = invalid_reason(row)
		row["valid"] = row["reason"] is None
		row["current_status"] = ("Partially Used" if row.status == "Partially Used" else "Active") if row.valid else row.reason
		row["online_redemption_required"] = True
		_activation_payload(row)
		batch = by_batch.get(row.get("voucher_card_batch"))
		if batch:
			row["all_products"] = bool(batch.all_products)
			row["eligibility"] = batch.restrictions
	return {
		"voucher_card_batches": batches,
		"gift_voucher_ledger": entries,
		"voucher_snapshot": {"mode": "full", "company": counter.company,
			"warehouse": counter.warehouse, "as_of": now_datetime(),
			"server_timezone": get_system_timezone(), "online_redemption_required": True},
	}


def _activation_payload(row):
	from frappe.utils import get_time

	row["use_activation_times"] = bool(row.get("use_redemption_hours"))
	for field in ("valid_from", "expiry_date", "issued_date", "redeemed_date"):
		if field in row:
			row[field] = getdate(row[field]).isoformat() if row.get(field) else None
	for field in ("active_from_time", "active_to_time"):
		row[field] = str(get_time(row[field])) if row.get("use_activation_times") else None
