"""Add user identity, effective roles and Retail area access to login responses."""

import frappe


def get_sales_person_identity(user):
	identity = {"sales_person_id": None, "sales_person_name": None}
	if user and user != "Guest":
		employees = frappe.get_all(
			"Employee", filters={"user_id": user, "status": "Active"},
			pluck="name", limit_page_length=2,
		)
		# Ambiguous mappings must never select an arbitrary person's identity.
		if len(employees) == 1:
			people = frappe.get_all(
				"Sales Person",
				filters={"employee": employees[0], "enabled": 1, "is_group": 0},
				fields=["custom_document_code", "sales_person_name", "custom_display_name"], limit_page_length=2,
			)
			if len(people) == 1:
				identity.update(
					sales_person_id=people[0].custom_document_code or None,
					sales_person_name=people[0].get("custom_display_name") or people[0].sales_person_name,
				)
	return identity


def get_login_access():
	"""Read the same Sales/Van Sales area gates as Desk; never grant permissions."""
	if frappe.session.user == "Guest":
		return {"roles": [], "permissions": {"sales": False, "van_sales": False}}
	from retail.workspace_permissions import (
		_get_blocked_modules,
		_get_role_allowed_sidebar_workspaces,
		_workspace_sidebar_is_allowed,
	)
	blocked = _get_blocked_modules()
	workspaces = _get_role_allowed_sidebar_workspaces()
	return {
		"roles": sorted(set(frappe.get_roles())),
		"permissions": {
			key: bool(_workspace_sidebar_is_allowed({"title": title}, blocked, workspaces))
			for key, title in (("sales", "Sales"), ("van_sales", "Van Sales"))
		},
	}


def on_session_creation(login_manager):
	frappe.local.response.update(get_sales_person_identity(login_manager.user))
	# Guest sessions are also created before API-token authentication. Do not
	# attach a false Guest access snapshot to an otherwise authenticated RPC.
	if login_manager.user != "Guest" or "roles" in frappe.local.response or "permissions" in frappe.local.response:
		frappe.local.response.update(get_login_access())
