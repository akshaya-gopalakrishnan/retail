"""Retail promotion dates and optional recurring daily hours (site local time)."""
import frappe
from frappe.utils import getdate, get_time, now_datetime


def seconds(value):
	value = get_time(value)
	return value.hour * 3600 + value.minute * 60 + value.second + value.microsecond / 1_000_000


def time_expression(promotion, value):
	start, end = promotion.get('active_from_time'), promotion.get('active_to_time')
	checks = []
	if start is not None and start != '':
		checks.append(f'{value} >= {seconds(start)}')
	if end is not None and end != '':
		checks.append(f'{value} <= {seconds(end)}')
	operator = ' or ' if len(checks) == 2 and seconds(start) > seconds(end) else ' and '
	return '(' + operator.join(checks) + ')' if checks else ''


def is_active(promotion, doc):
	now = now_datetime()
	date = getdate(doc.get('posting_date') or doc.get('transaction_date') or now)
	if promotion.get('active_from') and date < getdate(promotion.active_from):
		return False
	if promotion.get('active_to') and date > getdate(promotion.active_to):
		return False
	expression = time_expression(promotion, 'value')
	if not expression:
		return True
	posting_time = doc.get('posting_time')
	value = seconds(now.time() if posting_time is None or posting_time == '' else posting_time)
	return bool(frappe.safe_eval(expression, None, {'value': value}))


def pricing_rule_condition(promotion):
	# Literal formatting handles both Frappe's timedelta and API time strings.
	parts = "('%s' % posting_time).split(':')"
	value = f'(int({parts}[0])*3600 + int({parts}[1])*60 + float({parts}[2]))'
	return time_expression(promotion, value)


def sync_scheme_hours(promotion, scheme):
	condition = pricing_rule_condition(promotion)
	for name in frappe.get_all('Pricing Rule', filters={'promotional_scheme': scheme.name}, pluck='name'):
		frappe.db.set_value('Pricing Rule', name, {
			'condition': condition,
			'valid_from': promotion.get('active_from') or None,
			'valid_upto': promotion.get('active_to') or None,
		})
		frappe.clear_document_cache('Pricing Rule', name)
