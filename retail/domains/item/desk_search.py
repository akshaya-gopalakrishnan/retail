"""Retail Item dropdown and list search, retaining native permission queries."""
import frappe
from frappe.desk import reportview
from frappe.desk.reportview import get_match_cond
from frappe.model.db_query import DatabaseQuery
from frappe.utils import cint
from frappe.utils.data import sbool
from erpnext.controllers.queries import item_query as native_item_query
from retail.domains.item.name_search import condition, ranking


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def item_query(doctype, txt, searchfield, start, page_len, filters, as_dict=False, **kwargs):
	if not txt.strip():
		return native_item_query(doctype, txt, searchfield, start, page_len, filters, as_dict)
	frappe.has_permission('Item', 'read', throw=True)
	values = {}
	match = condition('`tabItem`.item_name', txt, values)
	rank = ranking('`tabItem`.item_name', txt, values)
	values.update(text='%' + txt + '%', exact=txt)
	# Enumerate in rank order, then retain the native query's eligibility rules.
	candidate_sql = f"""select name from `tabItem` where
		({match} or name like %(text)s or custom_barcode like %(text)s
		or exists (select 1 from `tabItem Barcode` b where b.parent = `tabItem`.name and b.barcode like %(text)s))
		{get_match_cond('Item')} order by case when name = %(exact)s or custom_barcode = %(exact)s then 0 else 1 end, {rank}, name
		limit 200 offset %(offset)s"""
	filters = frappe.parse_json(filters) if isinstance(filters, str) else filters
	results = []
	offset = 0
	while True:
		values['offset'] = offset
		rows = frappe.db.sql(candidate_sql, values)
		if not rows:
			break
		codes = [r[0] for r in rows]
		offset += len(rows)
		# The native API expects dict filters, as do standard Item Link controls.
		if isinstance(filters, list):
			from frappe.desk.search import search_widget
			allowed = search_widget('Item', '', filters=[*filters, ['Item', 'name', 'in', codes]],
				query='erpnext.controllers.queries.item_query', page_length=len(codes), as_dict=as_dict)
		else:
			native_filters = dict(filters or {})
			if 'name' in native_filters:
				original = native_filters['name']
				op, value = original if isinstance(original, (tuple, list)) else ('=', original)
				codes = frappe.get_list('Item', filters=[['name', 'in', codes], ['name', op, value]], pluck='name', limit_page_length=200)
			native_filters['name'] = ['in', codes]
			allowed = native_item_query('Item', '', searchfield, 0, 200, native_filters, as_dict)
		by_code = {(r.name if as_dict else r[0]): r for r in allowed}
		results.extend(by_code[code] for code in codes if code in by_code)
		if len(results) >= cint(start) + cint(page_len):
			break
	return results[cint(start):cint(start) + cint(page_len)]


def list_query():
	args = reportview.get_form_params()
	if args.doctype != 'Item' or args.get('group_by'):
		return None
	filters = args.get('filters') or []
	if not isinstance(filters, list):
		return None
	searches = [f for f in filters if len(f) == 4 and f[0] == 'Item'
		and f[1] in ('name', 'item_name') and f[2] == 'like' and isinstance(f[3], str)]
	if not searches:
		return None
	args.filters = [f for f in filters if f not in searches]
	args.fields = list(args.fields or ['name'])
	if '`tabItem`.`item_name`' not in args.fields and 'item_name' not in args.fields:
		args.fields.append('`tabItem`.`item_name`')
	start = max(0, cint(args.get('start') or args.get('limit_start')))
	length = min(500, max(1, cint(args.get('page_length') or args.get('limit_page_length') or 20)))
	for key in ('start', 'page_length', 'limit', 'limit_start', 'limit_page_length'):
		args.pop(key, None)
	args.order_by = '`tabItem`.`name` asc'
	# Native comment counts operate on result rows, not the SQL returned by run=False.
	query_args = dict(args, with_comment_count=False)
	query = reportview.execute(**query_args, run=False)
	values = {}
	conditions = []
	for i, f in enumerate(searches):
		text = f[3].strip('%')
		name_match = condition('items.item_name', text, values, f'list{i}')
		values[f'code{i}'] = f[3]
		conditions.append(f"({name_match} or items.name like %(code{i})s)")
	rank = ranking('items.item_name', searches[0][3].strip('%'), values)
	return args, f"select * from ({query}) items where {' and '.join(conditions)}", rank, values, start, length


@frappe.whitelist()
@frappe.read_only()
def get():
	prepared = list_query()
	if not prepared:
		return reportview.get()
	args, query, rank, values, start, length = prepared
	values.update(start=start, length=length)
	rows = frappe.db.sql(f'{query} order by {rank}, items.name limit %(length)s offset %(start)s', values, as_dict=True)
	if sbool(args.get('with_comment_count')):
		DatabaseQuery('Item').add_comment_count(rows)
	return reportview.compress(rows, args=args)


@frappe.whitelist()
@frappe.read_only()
def get_count():
	prepared = list_query()
	if not prepared:
		return reportview.get_count()
	_, query, _, values, _, _ = prepared
	return frappe.db.sql(f'select count(*) from ({query}) counted', values)[0][0]


@frappe.whitelist()
@frappe.read_only()
def names(txt=''):
	"""Item-list name suggestions, including disabled/non-purchase master items."""
	frappe.has_permission('Item', 'read', throw=True)
	values = {}
	match = condition('items.item_name', str(txt or '')[:140], values)
	rank = ranking('items.item_name', str(txt or '')[:140], values)
	query = frappe.get_list('Item', fields=['item_name'], distinct=True,
		limit_page_length=0, order_by='item_name asc', run=False)
	return frappe.db.sql(f'select item_name from ({query}) items where {match} order by {rank}, item_name limit 30', values, pluck=True)
