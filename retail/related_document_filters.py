"""Shared read-only transaction connections for sales and purchase list filters."""

import json
from collections import defaultdict
from dataclasses import dataclass

import frappe
from frappe import _
from frappe.model import get_permitted_fields, table_fields


# Transaction links only: shared suppliers, items, accounts, etc. are not edges.
DOCTYPES = (
	"Purchase Invoice", "Purchase Receipt", "Purchase Order", "Supplier Quotation",
	"Material Request", "Sales Order", "Delivery Note", "Sales Invoice", "Quotation",
	"Payment Entry", "Payment Request", "Journal Entry", "Landed Cost Voucher", "Asset",
	"Auto Repeat",
)
MAX_DOCUMENTS = 500
LIST_DOCTYPES = (
	"Quotation", "Sales Order", "Delivery Note", "Sales Invoice",
	"Supplier Quotation", "Purchase Order", "Purchase Receipt", "Purchase Invoice",
)


@dataclass(frozen=True)
class Link:
	parent: str
	table: str
	field: str
	target: str | None
	type_field: str | None = None
	parentfield: str | None = None


def readable_doctypes():
	return [dt for dt in DOCTYPES if frappe.has_permission(dt, "read")]


@frappe.whitelist()
@frappe.read_only()
def search(txt="", query=None, doctype="Purchase Invoice"):
	"""One autocomplete across transaction types, using native list permissions."""
	validate_list(doctype)
	if not isinstance(txt, str) or len(txt) > 140:
		frappe.throw(_("Invalid related document search"), frappe.ValidationError)
	txt = txt.strip()
	# Treat wildcard characters as part of the ID, not as an unrestricted pattern.
	pattern = "%" + txt.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
	matches = []
	for dt in readable_doctypes():
		if txt:
			for row in frappe.get_list(dt, filters={"name": txt}, fields=["name"], limit_page_length=1):
				matches.append((dt, row.name))
		for row in frappe.get_list(dt, filters=[["name", "like", pattern], ["name", "!=", txt]], fields=["name"],
			order_by="modified desc", limit_page_length=8):
			matches.append((dt, row.name))
	matches.sort(key=lambda match: (match[1].casefold() != txt.casefold(),
		not match[1].casefold().startswith(txt.casefold()), match[1], match[0]))
	return [{"value": json.dumps([dt, name]), "label": f"{name} ({_(dt)})"}
		for dt, name in matches[:20]]


def normalize(value):
	try:
		source = json.loads(value) if isinstance(value, str) else value
	except (ValueError, TypeError):
		source = None
	if (not isinstance(source, list) or len(source) != 2 or source[0] not in DOCTYPES
		or not isinstance(source[1], str) or not source[1].strip() or len(source[1]) > 140
		or "\n" in source[1] or "\r" in source[1]):
		frappe.throw(_("Select a related document from the suggestions"), frappe.ValidationError)
	return source[0], source[1]


def transaction_links(doctypes):
	"""Discover readable Link/Dynamic Link fields, including child tables."""
	links = []
	for dt in doctypes:
		meta = frappe.get_meta(dt)
		tables = [(meta, None)]
		levels = meta.get_permlevel_access("read")
		for df in meta.fields:
			if df.fieldtype in table_fields and (df.permlevel or 0) in levels:
				tables.append((frappe.get_meta(df.options), df.fieldname))
		for table, parentfield in tables:
			permitted = set(get_permitted_fields(table.name, parenttype=dt, permission_type="read"))
			for df in table.fields:
				if df.fieldname not in permitted or df.get("is_virtual"):
					continue
				if df.fieldtype == "Link" and df.options in doctypes:
					links.append(Link(dt, table.name, df.fieldname, df.options, parentfield=parentfield))
				elif df.fieldtype == "Dynamic Link" and df.options in permitted:
					links.append(Link(dt, table.name, df.fieldname, None, df.options, parentfield))
	return links


def limited_list(doctype, **kwargs):
	rows = frappe.get_list(doctype, order_by=None, limit_page_length=MAX_DOCUMENTS + 1,
		distinct=True, **kwargs)
	if len(rows) > MAX_DOCUMENTS:
		too_many_documents()
	return rows


def too_many_documents():
	frappe.throw(_("Too many connected documents. Choose a more specific related document."),
		frappe.ValidationError)


def validate_list(doctype):
	if doctype not in LIST_DOCTYPES:
		frappe.throw(_("Unsupported related document list"), frappe.ValidationError)
	frappe.has_permission(doctype, "read", throw=True)


def connected_documents(value, doctype="Purchase Invoice"):
	"""Walk both directions; every step uses the logged-in user's list permissions."""
	validate_list(doctype)
	source_type, source_name = normalize(value)
	doctypes = readable_doctypes()
	if source_type not in doctypes:
		frappe.throw(_("You cannot read the selected related document"), frappe.PermissionError)
	frappe.has_permission(source_type, "read", doc=source_name, throw=True)
	if not limited_list(source_type, filters={"name": source_name}, fields=["name"]):
		frappe.throw(_("You cannot read the selected related document"), frappe.PermissionError)
	links = transaction_links(doctypes)
	seen = defaultdict(set)
	frontier = {source_type: {source_name}}
	while frontier:
		for dt, names in frontier.items():
			seen[dt].update(names)
		if sum(map(len, seen.values())) > MAX_DOCUMENTS:
			too_many_documents()
		candidates = defaultdict(set)
		for link in links:
			base = [[link.table, "parentfield", "=", link.parentfield]] if link.parentfield else []
			if link.parent in frontier:
				fields = [f"`tab{link.table}`.`{link.field}` as related_name"]
				if link.type_field:
					fields.append(f"`tab{link.table}`.`{link.type_field}` as related_type")
				rows = limited_list(link.parent, fields=fields,
					filters=base + [[link.parent, "name", "in", sorted(frontier[link.parent])]])
				for row in rows:
					target = row.get("related_type") if link.type_field else link.target
					if target in doctypes and row.get("related_name"):
						candidates[target].add(row.related_name)
			for dt, names in frontier.items():
				if link.target and link.target != dt:
					continue
				conditions = base + [[link.table, link.field, "in", sorted(names)]]
				if link.type_field:
					conditions.append([link.table, link.type_field, "=", dt])
				rows = limited_list(link.parent, fields=["name"], filters=conditions)
				candidates[link.parent].update(row.name for row in rows)
		frontier = {}
		for dt, names in candidates.items():
			names -= seen[dt]
			if names:
				# Outbound links can point to records the user cannot read.
				visible = limited_list(dt, filters={"name": ["in", sorted(names)]}, fields=["name"])
				if visible:
					frontier[dt] = {row.name for row in visible}
	return sorted(seen[doctype])


def purchase_invoices(value):
	"""Keep the original PI helper available to existing callers."""
	return connected_documents(value, doctype="Purchase Invoice")
