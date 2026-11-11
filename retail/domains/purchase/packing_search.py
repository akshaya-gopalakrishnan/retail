"""Permission-aware packing choices for purchase item controls."""

import frappe
from frappe.desk.reportview import get_match_cond
from frappe.desk.search import search_widget
from frappe.utils import cint
from retail.domains.item.name_search import condition as name_condition, ranking

RESULT_LIMIT = 5
CANDIDATE_LIMIT = 20
SEARCH_BATCH_SIZE = 200


@frappe.whitelist()
def search(txt="", start=0, filters=None, query=None, reference_doctype=None, page_length=20):
	frappe.has_permission("Item", "read", throw=True)
	# Apply Item user permissions to both branches, including child packing matches.
	match = get_match_cond("Item")
	filters = frappe.parse_json(filters) if isinstance(filters, str) else filters
	txt = str(txt or "").strip()[:140]
	values = {}
	name_match = name_condition("`tabItem`.item_name", txt, values)
	packing_match = name_condition("p.packing_name", txt, values, "packing_word")
	name_rank = ranking("item_name", txt, values)
	sql = f"""
		select * from (
			select `tabItem`.name as item_code, `tabItem`.item_name,
				`tabItem`.item_name as packing_name,
				coalesce(`tabItem`.custom_barcode, '') as barcode,
				`tabItem`.stock_uom as uom, `tabItem`.stock_uom as packing_uom,
				1 as conversion_factor, '' as packing_id
			from `tabItem`
			where `tabItem`.disabled = 0 and `tabItem`.is_purchase_item = 1
				and `tabItem`.has_variants = 0 {match}
				and (`tabItem`.name like %(txt)s or {name_match}
					or `tabItem`.custom_barcode like %(txt)s)
			union all
			select `tabItem`.name, `tabItem`.item_name, p.packing_name,
				coalesce(p.barcode, ''), p.uom, coalesce(nullif(p.packing_uom, ''), p.uom),
				p.conversion_factor, p.name
			from `tabItem` inner join `tabRetail Packing Detail` p
				on p.parent = `tabItem`.name and p.parenttype = 'Item'
			where `tabItem`.disabled = 0 and `tabItem`.is_purchase_item = 1
				and `tabItem`.has_variants = 0 and coalesce(p.disabled, 0) = 0
				and p.conversion_factor > 0 and coalesce(p.uom, '') != '' {match}
				and (`tabItem`.name like %(txt)s or {name_match}
					or `tabItem`.custom_barcode like %(txt)s or p.barcode like %(txt)s
					or {packing_match} or p.packing_uom like %(txt)s)
		) choices
		order by
			case when barcode = %(exact)s then 0
				when item_code = %(exact)s then 1
				when item_name = %(exact)s then 2
				when packing_name = %(exact)s then 3
				when barcode like %(prefix)s then 4 else 5 end,
			{name_rank},
			item_name, item_code, conversion_factor, packing_id
		limit %(batch_size)s offset %(start)s
		"""
	if not txt:
		# The initial list reads Item only: no packing join, wildcard scan or UNION.
		sql = f"""
			select `tabItem`.name as item_code, `tabItem`.item_name,
				`tabItem`.item_name as packing_name,
				coalesce(`tabItem`.custom_barcode, '') as barcode,
				`tabItem`.stock_uom as uom, `tabItem`.stock_uom as packing_uom,
				1 as conversion_factor, '' as packing_id
			from `tabItem`
			where `tabItem`.disabled = 0 and `tabItem`.is_purchase_item = 1
				and `tabItem`.has_variants = 0 {match}
			order by `tabItem`.modified desc, `tabItem`.name desc
			limit %(batch_size)s offset %(start)s
		"""
	# Resolve packing text first, then ask the native Item query which parents
	# satisfy this control's filters, party restrictions and permissions.
	results = []
	offset = 0
	start = max(0, cint(start))
	page_length = min(50, max(1, cint(page_length))) if txt else RESULT_LIMIT
	batch_size = SEARCH_BATCH_SIZE if txt else CANDIDATE_LIMIT
	# Stop as soon as this page is filled; later packings remain accessible by start.
	while len(results) < start + page_length:
		rows = frappe.db.sql(sql, {
			**values, "txt": "%" + txt + "%", "exact": txt, "prefix": txt + "%",
			"start": offset, "batch_size": batch_size,
		}, as_dict=True)
		if not rows:
			break
		codes = list(dict.fromkeys(row.item_code for row in rows))
		if isinstance(filters, list):
			native_filters = [*filters, ["Item", "name", "in", codes]]
		else:
			native_filters = dict(filters or {})
			if "name" in native_filters:
				condition = native_filters["name"]
				operator, value = condition if isinstance(condition, (list, tuple)) else ("=", condition)
				codes = frappe.get_list("Item", filters=[
					["name", "in", codes], ["name", operator, value],
				], pluck="name", limit_page_length=batch_size)
			native_filters["name"] = ["in", codes]
		if codes:
			allowed = {row[0] for row in search_widget(
				"Item", "", query=query, searchfield="name", filters=native_filters,
				page_length=len(codes), reference_doctype=reference_doctype,
			)}
			results.extend(row for row in rows if row.item_code in allowed)
		offset += len(rows)
		if len(rows) < batch_size:
			break
	return results[start:start + page_length]
