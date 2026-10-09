"""Resolve permanent POS identities without changing the terminal's saved payload."""
import frappe


class MissingPOSDependency(frappe.ValidationError):
	pass


def validate_reference(value, fieldname):
	if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > 140:
		frappe.throw(f"{fieldname} must be a non-empty reference of at most 140 characters without surrounding spaces.")


def validate_identity(doc, fieldname):
	value = doc.get(fieldname)
	if value:
		validate_reference(value, fieldname)
	else:
		doc.set(fieldname, None)  # Multiple legacy records may have a NULL unique key.
	if not doc.is_new() and doc.get_db_value(fieldname) != doc.get(fieldname):
		frappe.throw(f"{fieldname} is permanent and cannot be changed.")


def require_pair(payload):
	shift, session = payload.get("external_shift_reference"), payload.get("external_session_reference")
	if shift or session:
		for field, value in (("external_shift_reference", shift), ("external_session_reference", session)):
			validate_reference(value, field)
	return bool(shift or session)


def resolve(payload, *, new_session=False, shift_only=False):
	"""Check identity, not current lifecycle policy; historical completed sales still post."""
	from retail.api.pos_sync import _cashier_employee

	result = frappe._dict(payload)
	shift_ref, session_ref = payload.get("external_shift_reference"), payload.get("external_session_reference")
	if not (shift_ref or session_ref):
		return result
	if shift_only and shift_ref and not session_ref:
		validate_reference(shift_ref, "external_shift_reference")
	else:
		require_pair(payload)
	shift_name = frappe.db.get_value("POS Cashier Shift", {"external_shift_reference": shift_ref}, "name")
	if not shift_name:
		frappe.throw("Shift opening has not synced. Sync it first, then retry the unchanged payload.", MissingPOSDependency)
	shift = frappe.get_doc("POS Cashier Shift", shift_name)
	for field in ("cashier_shift", "cashier_shift_id"):
		if payload.get(field) and payload[field] != shift.name:
			frappe.throw("External shift reference conflicts with the ERP cashier shift.")
	if payload.get("branch") and payload.get("branch") != shift.branch:
		frappe.throw("External shift reference belongs to another branch.")
	employee = _cashier_employee(payload)
	if employee and employee != shift.cashier_employee:
		frappe.throw("Cashier does not match the external shift reference.")
	result.cashier_shift = shift.name
	result.cashier_employee = shift.cashier_employee
	if not session_ref:
		return result
	session_name = frappe.db.get_value("POS Counter Session", {"external_session_reference": session_ref}, "name")
	if not session_name:
		if new_session:
			if payload.get("counter_session") or payload.get("counter_session_id") or payload.get("pos_shift_no"):
				frappe.throw("A new external session cannot refer to an existing ERP session/opening.")
			return result
		frappe.throw("Counter session opening/resume has not synced. Sync it first, then retry the unchanged payload.", MissingPOSDependency)
	session = frappe.get_doc("POS Counter Session", session_name)
	if session.cashier_shift != shift.name or session.cashier_employee != shift.cashier_employee or session.branch != shift.branch:
		frappe.throw("External counter session does not belong to the cashier shift.")
	for field in ("counter_session", "counter_session_id"):
		if payload.get(field) and payload[field] != session.name:
			frappe.throw("External session reference conflicts with the ERP counter session.")
	if payload.get("counter_code") and payload.get("counter_code") != session.counter_code:
		frappe.throw("External session reference belongs to another counter.")
	terminal = payload.get("pos_terminal_id") or payload.get("terminal_id")
	if terminal and terminal != session.terminal_id:
		frappe.throw("External session reference belongs to another terminal.")
	if payload.get("pos_shift_no") and payload.get("pos_shift_no") != session.pos_opening_entry:
		frappe.throw("External session reference conflicts with the ERP POS opening.")
	if not session.pos_opening_entry:
		frappe.throw("Counter session has no synced POS opening. Review its opening sync.", MissingPOSDependency)
	result.counter_session = session.name
	result.pos_shift_no = session.pos_opening_entry
	return result


def authorize(sync_type, payload):
	"""Authorize before returning a stored receipt, even after a shift has closed."""
	from retail.api.pos_sync import _counter, _cashier_shift_doc, _counter_session_doc

	if sync_type == "Shift Opening":
		require_pair(payload)
		resolved = payload
	elif sync_type in ("Sales Invoice", "Credit Sales Invoice", "Return"):
		resolved = resolve_completed(payload)
	else:
		resolved = resolve(payload, new_session=sync_type == "Shift Resume", shift_only=sync_type in ("Shift Closing", "Shift Reopen"))
	if sync_type in ("Shift Pause", "Shift Closing", "Shift Reopen"):
		shift = _cashier_shift_doc(resolved.get("cashier_shift") or resolved.get("cashier_shift_id"))
		session_name = resolved.get("counter_session") or resolved.get("counter_session_id")
		if not session_name:
			session_name = frappe.db.get_value("POS Counter Session", {"cashier_shift": shift.name}, "name", order_by="creation desc")
		session = _counter_session_doc(session_name)
		if session.cashier_shift != shift.name:
			frappe.throw("Counter session does not belong to this cashier shift.")
		if payload.get("branch") and payload.get("branch") != session.branch:
			frappe.throw("Counter session belongs to another branch.")
		if payload.get("counter_code") and payload.get("counter_code") != session.counter_code:
			frappe.throw("Counter session belongs to another counter.")
		return _counter(session.branch, session.counter_code)
	if sync_type == "Day Closing":
		from retail.pos_day_corrections import authorize_day_close
		if not payload.get("branch"):
			frappe.throw("Branch is required.")
		authorize_day_close(payload["branch"], payload.get("business_date") or payload.get("posting_date") or frappe.utils.today())
		return None
	counter = _counter(payload.get("branch"), payload.get("counter_code"),
		completed=sync_type in ("Sales Invoice", "Credit Sales Invoice", "Return"))
	if sync_type in ("Shift Opening", "Shift Resume") and payload.get("external_shift_reference"):
		terminal = payload.get("pos_terminal_id") or payload.get("terminal_id")
		if terminal and counter.terminal_id and terminal != counter.terminal_id:
			frappe.throw("Terminal does not match the configured counter.")
	return counter


def echo(payload, response):
	for field in ("external_shift_reference", "external_session_reference"):
		if payload.get(field):
			response[field] = payload[field]
	return response


def resolve_completed(payload):
	"""Missing lifecycle dependencies are advisory; existing identity mismatches reject."""
	from retail.api.pos_sync import _cashier_employee
	result = frappe._dict(payload)
	require_pair(payload)
	employee = _cashier_employee(payload)
	for doctype, external, internal in (
		("POS Cashier Shift", "external_shift_reference", "cashier_shift"),
		("POS Counter Session", "external_session_reference", "counter_session"),
	):
		ref = payload.get(external)
		name = frappe.db.get_value(doctype, {external: ref}, "name") if ref else payload.get(internal)
		if not name:
			continue
		doc = frappe.get_doc(doctype, name)
		if employee and doc.cashier_employee != employee:
			frappe.throw("Cashier does not match the permanent POS identity.")
		if payload.get("branch") and doc.branch != payload["branch"]:
			frappe.throw("Permanent POS identity belongs to another branch.")
		for field in (internal, internal + "_id"):
			if payload.get(field) and payload[field] != name:
				frappe.throw("External POS identity conflicts with the ERP identity.")
		if doctype == "POS Counter Session":
			if payload.get("counter_code") and doc.counter_code != payload["counter_code"]:
				frappe.throw("Permanent session belongs to another counter.")
			terminal = payload.get("pos_terminal_id") or payload.get("terminal_id")
			if terminal and doc.terminal_id != terminal:
				frappe.throw("Permanent session belongs to another terminal.")
			if payload.get("external_shift_reference") and frappe.db.get_value(
				"POS Cashier Shift", doc.cashier_shift, "external_shift_reference") != payload["external_shift_reference"]:
				frappe.throw("Permanent session belongs to another shift.")
			result.pos_shift_no = doc.pos_opening_entry
		result[internal] = name
		result.cashier_employee = doc.cashier_employee
	return result
