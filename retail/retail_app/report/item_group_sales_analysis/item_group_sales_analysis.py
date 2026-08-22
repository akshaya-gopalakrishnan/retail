from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate


LEVEL_LABELS = ("Department", "Sub Department", "Category", "Sub Category", "Family")
AMOUNT_FIELDS = ("quantity", "amount", "discount", "tax", "net_total")
ROOT_GROUPS = {"", None, "All Item Groups"}


def execute(filters=None):
	filters = get_filters(filters)
	rows = get_sales_rows(filters)
	group_map = get_item_group_map()
	data = build_report_data(rows, group_map, filters)
	columns = get_columns(filters, data)
	return columns, data


def get_filters(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", getdate())
	filters.setdefault("to_date", getdate())
	filters.setdefault("report_view", "Department + Sub Department + Category")
	filters.setdefault("sales_source", "Both")
	return filters


def get_sales_rows(filters):
	queries = []
	values = {}
	if filters.sales_source in ("Both", "POS Invoice"):
		pos_conditions, pos_values = get_conditions(filters, "pi", "pii", include_branch=True)
		values.update(pos_values)
		queries.append(get_sales_query("POS Invoice", "tabPOS Invoice", "tabPOS Invoice Item", pos_conditions))
	if filters.sales_source in ("Both", "Sales Invoice"):
		sales_conditions, sales_values = get_conditions(filters, "si", "sii", include_branch=False)
		values.update(sales_values)
		queries.append(get_sales_query("Sales Invoice", "tabSales Invoice", "tabSales Invoice Item", sales_conditions))

	if not queries:
		return []

	return frappe.db.sql(
		" union all ".join(queries),
		values,
		as_dict=True,
	)


def get_sales_query(source, parent_table, item_table, conditions):
	invoice_alias = "pi" if source == "POS Invoice" else "si"
	item_alias = "pii" if source == "POS Invoice" else "sii"
	return f"""
		select
			{frappe.db.escape(source)} as sales_source,
			{item_alias}.item_code,
			{item_alias}.item_name,
			coalesce({item_alias}.item_group, item.item_group) as item_group,
			count(distinct {invoice_alias}.name) as invoice_count,
			sum(case when {invoice_alias}.is_return = 1 then -abs(coalesce({item_alias}.stock_qty, {item_alias}.qty, 0)) else abs(coalesce({item_alias}.stock_qty, {item_alias}.qty, 0)) end) as quantity,
			sum(case when {invoice_alias}.is_return = 1 then -abs(coalesce({item_alias}.base_net_amount, {item_alias}.net_amount, 0)) else abs(coalesce({item_alias}.base_net_amount, {item_alias}.net_amount, 0)) end) as amount,
			sum(case when {invoice_alias}.is_return = 1 then -abs(coalesce({item_alias}.discount_amount, 0) + coalesce({item_alias}.distributed_discount_amount, 0)) else abs(coalesce({item_alias}.discount_amount, 0) + coalesce({item_alias}.distributed_discount_amount, 0)) end) as discount,
			sum(case when {invoice_alias}.is_return = 1 then -abs(coalesce({item_alias}.tax_amount, 0)) else abs(coalesce({item_alias}.tax_amount, 0)) end) as tax,
			sum(case when {invoice_alias}.is_return = 1 then -abs(coalesce({item_alias}.base_net_amount, {item_alias}.net_amount, 0) + coalesce({item_alias}.tax_amount, 0)) else abs(coalesce({item_alias}.base_net_amount, {item_alias}.net_amount, 0) + coalesce({item_alias}.tax_amount, 0)) end) as net_total
		from `{item_table}` {item_alias}
		inner join `{parent_table}` {invoice_alias} on {invoice_alias}.name = {item_alias}.parent
		left join `tabItem` item on item.name = {item_alias}.item_code
		where {conditions}
		group by {item_alias}.item_code, {item_alias}.item_name, coalesce({item_alias}.item_group, item.item_group)
	"""


def get_conditions(filters, invoice_alias, item_alias, include_branch=False):
	conditions = [f"{invoice_alias}.docstatus = 1"]
	values = {}

	if filters.get("from_date"):
		conditions.append(f"{invoice_alias}.posting_date >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append(f"{invoice_alias}.posting_date <= %(to_date)s")
		values["to_date"] = filters.to_date
	if filters.get("company"):
		conditions.append(f"{invoice_alias}.company = %(company)s")
		values["company"] = filters.company
	if include_branch and filters.get("branch"):
		conditions.append(f"{invoice_alias}.pos_branch = %(branch)s")
		values["branch"] = filters.branch
	if filters.get("item_code"):
		conditions.append(f"{item_alias}.item_code = %(item_code)s")
		values["item_code"] = filters.item_code
	if filters.get("item_group"):
		descendants = get_descendant_item_groups(filters.item_group)
		conditions.append(f"coalesce({item_alias}.item_group, item.item_group) in %(item_groups)s")
		values["item_groups"] = tuple(descendants or [filters.item_group])

	return " and ".join(conditions), values


def get_descendant_item_groups(item_group):
	group = frappe.db.get_value("Item Group", item_group, ["lft", "rgt"], as_dict=True)
	if not group:
		return [item_group]

	return frappe.get_all(
		"Item Group",
		filters={"lft": (">=", group.lft), "rgt": ("<=", group.rgt)},
		pluck="name",
	)


def get_item_group_map():
	return {
		row.name: row
		for row in frappe.get_all(
			"Item Group",
			fields=["name", "parent_item_group", "is_group", "lft", "rgt"],
			order_by="lft asc",
		)
	}


def build_report_data(rows, group_map, filters):
	view = filters.report_view
	if view == "Full Tree":
		return build_tree_data(rows, group_map, filters)

	grouped = {}
	for row in rows:
		path = get_group_path(row.item_group, group_map)
		key = get_summary_key(row, path, filters)
		if key not in grouped:
			grouped[key] = make_summary_row(row, path, filters)
		add_amounts(grouped[key], row)

	data = list(grouped.values())
	data.sort(key=lambda row: (row.get("department") or "", row.get("sub_department") or "", row.get("category") or "", row.get("sub_category") or "", row.get("family") or "", row.get("full_path") or "", row.get("item_name") or ""))
	return data


def get_summary_key(row, path, filters):
	view = filters.report_view
	if view == "Department Wise":
		return tuple(path[:1])
	if view == "Department + Sub Department":
		return tuple(path[:2])
	if view == "Department + Sub Department + Category":
		return tuple(path[:3])
	if view == "Item Wise" or filters.get("show_item_details"):
		return (tuple(path), row.item_code)
	return tuple(path)


def make_summary_row(row, path, filters):
	out = frappe._dict()
	set_path_fields(out, path)
	out.full_path = " > ".join(path)
	if filters.report_view == "Item Wise" or filters.get("show_item_details"):
		out.item_code = row.item_code
		out.item_name = row.item_name
	out.invoice_count = 0
	for field in AMOUNT_FIELDS:
		out[field] = 0
	return out


def build_tree_data(rows, group_map, filters):
	group_totals = defaultdict(lambda: frappe._dict({field: 0 for field in AMOUNT_FIELDS}))
	group_paths = {}
	item_rows = []

	for row in rows:
		path = get_group_path(row.item_group, group_map)
		for index in range(len(path)):
			key = tuple(path[: index + 1])
			group_paths[key] = path[: index + 1]
			add_amounts(group_totals[key], row)
		if filters.get("show_item_details"):
			item_rows.append((path, row))

	data = []
	for key in sorted(group_paths):
		path = group_paths[key]
		out = frappe._dict(group_totals[key])
		out.group_or_item = path[-1]
		out.full_path = " > ".join(path)
		out.indent = len(path) - 1
		out.invoice_count = ""
		data.append(out)

	if filters.get("show_item_details"):
		for path, row in item_rows:
			out = frappe._dict()
			out.group_or_item = row.item_name or row.item_code
			out.item_code = row.item_code
			out.full_path = " > ".join(path)
			out.indent = len(path)
			out.invoice_count = row.invoice_count
			for field in AMOUNT_FIELDS:
				out[field] = flt(row.get(field))
			data.append(out)

	return data


def get_group_path(item_group, group_map):
	if not item_group:
		return [_("No Item Group")]

	path = []
	seen = set()
	current = item_group
	while current and current not in ROOT_GROUPS and current not in seen:
		seen.add(current)
		group = group_map.get(current)
		if not group:
			path.append(current)
			break
		path.append(group.name)
		current = group.parent_item_group

	return list(reversed(path)) or [_("No Item Group")]


def set_path_fields(out, path):
	for index, label in enumerate(LEVEL_LABELS):
		out[frappe.scrub(label)] = path[index] if len(path) > index else ""


def add_amounts(target, source):
	target.invoice_count = flt(target.get("invoice_count")) + flt(source.get("invoice_count"))
	for field in AMOUNT_FIELDS:
		target[field] = flt(target.get(field)) + flt(source.get(field))


def get_columns(filters, data):
	if filters.report_view == "Full Tree":
		columns = [
			{"label": _("Group / Item"), "fieldname": "group_or_item", "fieldtype": "Data", "width": 260},
			{"label": _("Full Path"), "fieldname": "full_path", "fieldtype": "Data", "width": 360},
		]
		if filters.get("show_item_details"):
			columns.append({"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140})
	else:
		columns = get_path_columns(filters, data)
		if filters.report_view == "Item Wise" or filters.get("show_item_details"):
			columns.extend(
				[
					{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
					{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
				]
			)

	columns.extend(
		[
			{"label": _("Quantity"), "fieldname": "quantity", "fieldtype": "Float", "width": 100},
			{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
			{"label": _("Discount"), "fieldname": "discount", "fieldtype": "Currency", "width": 120},
			{"label": _("Tax"), "fieldname": "tax", "fieldtype": "Currency", "width": 110},
			{"label": _("Net Total"), "fieldname": "net_total", "fieldtype": "Currency", "width": 120},
		]
	)
	return columns


def get_path_columns(filters, data):
	view_level_count = {
		"Department Wise": 1,
		"Department + Sub Department": 2,
		"Department + Sub Department + Category": 3,
	}.get(filters.report_view, get_max_used_level(data))

	columns = []
	for label in LEVEL_LABELS[:view_level_count]:
		columns.append(
			{
				"label": _(label),
				"fieldname": frappe.scrub(label),
				"fieldtype": "Link",
				"options": "Item Group",
				"width": 180,
			}
		)
	if filters.report_view == "Full Path Summary":
		columns.append({"label": _("Full Path"), "fieldname": "full_path", "fieldtype": "Data", "width": 360})
	return columns


def get_max_used_level(data):
	max_level = 1
	for row in data:
		for index, label in enumerate(LEVEL_LABELS, start=1):
			if row.get(frappe.scrub(label)):
				max_level = max(max_level, index)
	return max_level
