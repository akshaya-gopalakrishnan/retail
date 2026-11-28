"""Database-backed customer upsert checks; all test writes are rolled back."""

from unittest.mock import patch

import frappe


def run_integration():
	from retail.api import pos_sync as api

	assert frappe.local.site == "retail-test.localhost"
	original_user = frappe.session.user
	frappe.set_user("Administrator")
	try:
		company = frappe.db.get_value("Company", {}, "name")
		base = {"external_customer_id": "CREDIT-TEST-" + frappe.generate_hash(length=10),
			"customer_name": "Credit API test",
			"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
			"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name")}
		with patch.object(api, "_assert_pos_user"), patch.object(api, "_counter", return_value=frappe._dict(company=company)):
			created = api.upsert_customer(dict(base, is_credit_customer=1, credit_limit=5000))
			assert created.get("action") == "Created", created
			name = created["customer"]
			assert created["is_credit_customer"] == 1 and created["credit_limit"] == 5000
			doc = frappe.get_doc("Customer", name)
			assert doc.custom_is_credit_customer == 1
			assert [(r.company, r.credit_limit) for r in doc.credit_limits] == [(company, 5000)]
			omitted = api.upsert_customer({"external_customer_id": base["external_customer_id"]})
			assert omitted["is_credit_customer"] == 1 and omitted["credit_limit"] == 5000
			zero = api.upsert_customer(dict(base, is_credit_customer=0, credit_limit=0))
			assert zero["action"] == "Updated", zero
			assert zero["is_credit_customer"] == zero["credit_limit"] == 0
			doc.reload()
			assert doc.custom_is_credit_customer == 0 and doc.credit_limits[0].credit_limit == 0
			assert len(doc.credit_limits) == 1
			line = "Long customer address " * 30
			address_result = api.upsert_customer(dict(base, address_line=line))
			assert address_result.get("address_line") == line, address_result
			doc.reload()
			address_name = doc.customer_primary_address
			assert frappe.db.get_value("Address", address_name, "address_line1") == line
			assert not frappe.db.get_value("Address", address_name, "city")
			assert not frappe.db.get_value("Address", address_name, "country")
			updated = api.upsert_customer(dict(base, address_line="Updated address"))
			assert updated.get("address_line") == "Updated address", updated
			doc.reload()
			assert doc.customer_primary_address == address_name
			assert api.upsert_customer(base)["address_line"] == "Updated address"
		for invalid in ({"credit_limit": -1}, {"credit_limit": "abc"},
			{"credit_limit": "nan"}, {"is_credit_customer": 2}):
			try:
				api._customer_credit_values(invalid)
			except frappe.ValidationError:
				pass
			else:
				raise AssertionError(invalid)
		return {"status": "passed", "checks": "create, update, omitted values, explicit zero, invalid values, long address create/update"}
	finally:
		frappe.db.rollback()
		frappe.set_user(original_user)
