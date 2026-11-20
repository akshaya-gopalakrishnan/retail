"""Whole Bill eligibility with native per-row pricing and priority resolution."""
import copy
from functools import wraps

import frappe
from frappe.utils import cint, flt


def whole_bill_schemes(rules):
	schemes = list({r.get("promotional_scheme") for r in rules if r.get("promotional_scheme")})
	if not schemes:
		return set()
	links = frappe.get_all("Promotion Linked Scheme", filters={
		"parenttype": "Promo Price", "promotional_scheme": ["in", schemes],
	}, fields=["parent", "promotional_scheme"])
	if not links:
		return set()
	parents = frappe.get_all("Promo Price", filters={
		"name": ["in", list({link.parent for link in links})], "promotion_scope": "WHOLE BILL",
	}, pluck="name")
	return {link.promotional_scheme for link in links if link.parent in parents}


def bill_totals(doc, args):
	"""Use original row prices, including the current edit, never discounted rates."""
	quantity = amount = 0
	for row in doc.get("items") or []:
		if not row.get("item_code") or row.get("is_free_item") or row.get("custom_foc_parent"):
			continue
		current = args if args.get("child_docname") and row.get("name") == args.get("child_docname") else row
		qty = flt(current.get("qty"))
		price = current.get("price_list_rate")
		if price is None:
			price = current.get("rate")
		amount += qty * flt(price)
		quantity += qty * (flt(current.get("conversion_factor")) or 1)
	precision = doc.precision("total") if callable(getattr(doc, "precision", None)) else 2
	return quantity, round(amount, precision if precision is not None else 2)


def choose_rules(core, args, doc, rules, schemes):
	quantity, amount = bill_totals(doc, args)
	eligible = []
	for source in rules:
		rule = copy.deepcopy(source)
		if rule.get("promotional_scheme") in schemes:
			if not core.filter_pricing_rules_for_qty_amount(quantity, amount, [rule], args):
				continue
			# Thresholds have been checked against the bill. Native evaluation now
			# resolves this row's priority, without copying its winner onto peers.
			rule.mixed_conditions = 0
			rule.apply_rule_on_other_items = []
			for field in ("min_qty", "max_qty", "min_amt", "max_amt"):
				rule[field] = 0
		if core.filter_pricing_rules(args, [rule], doc):
			eligible.append(rule)
	if not eligible:
		return []
	# Every rule has passed its own eligibility calculation. Do not let the
	# first candidate's mixed threshold mode change another candidate's result.
	selection = copy.deepcopy(eligible)
	for rule in selection:
		rule.mixed_conditions = rule.is_cumulative = rule.apply_rule_on_other = 0
		for field in ("min_qty", "max_qty", "min_amt", "max_amt"):
			rule[field] = 0
	# Retail promotion priority is a rank: 1 wins; unset priorities follow
	# explicitly ranked promotions. Keep native conflict handling for ties.
	best = min(cint(rule.priority) or 9999 for rule in selection)
	selection = [rule for rule in selection if (cint(rule.priority) or 9999) == best]
	by_name = {rule.name: rule for rule in eligible}
	if core.apply_multiple_pricing_rules(selection):
		return [by_name[rule.name] for group in core.sorted_by_priority(selection, args, doc)
			for rule in (group if isinstance(group, list) else [group])]
	selected = core.filter_pricing_rules(args, selection, doc)
	return [by_name[selected.name]] if selected else []


def install():
	from erpnext.accounts.doctype.pricing_rule import utils as core
	if getattr(core.get_pricing_rules, "_retail_whole_bill", False):
		return
	original = core.get_pricing_rules

	@wraps(original)
	def get_pricing_rules(args, doc=None):
		parent = args.get("parenttype") or args.get("doctype")
		if parent not in ("Sales Invoice", "Delivery Note") or not doc or "retail" not in frappe.get_installed_apps():
			return original(args, doc)
		rules, values = [], {}
		for scope in ("Item Code", "Item Group", "Brand"):
			rules.extend(core._get_pricing_rules(scope, args, values))
		schemes = whole_bill_schemes(rules)
		if not rules:
			return original(args, doc)
		rules = core.filter_pricing_rule_based_on_condition(rules, doc)
		return choose_rules(core, args, doc, rules, schemes)

	get_pricing_rules._retail_whole_bill = True
	core.get_pricing_rules = get_pricing_rules


def boot(bootinfo):
	bootinfo.retail_has_whole_bill_promotions = bool(frappe.db.exists("Promo Price", {
		"promotion_scope": "WHOLE BILL", "disabled": 0,
	}))


def configure():
	"""Repair generated definitions without resaving promotions or invoices."""
	parents = frappe.get_all("Promo Price", filters={"promotion_scope": "WHOLE BILL"}, pluck="name")
	if not parents:
		return
	links = frappe.get_all("Promotion Linked Scheme", filters={
		"parenttype": "Promo Price", "parent": ["in", parents],
	}, pluck="promotional_scheme")
	for scheme in links:
		frappe.db.set_value("Promotional Scheme", scheme, "mixed_conditions", 1, update_modified=False)
		frappe.clear_document_cache("Promotional Scheme", scheme)
		for name in frappe.get_all("Pricing Rule", filters={"promotional_scheme": scheme}, pluck="name"):
			frappe.db.set_value("Pricing Rule", name, "mixed_conditions", 1, update_modified=False)
			frappe.clear_document_cache("Pricing Rule", name)
