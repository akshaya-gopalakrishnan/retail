"""Add the authenticated user's Sales Person identity to new-session responses."""

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


def on_session_creation(login_manager):
	frappe.local.response.update(get_sales_person_identity(login_manager.user))
