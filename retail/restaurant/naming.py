"""Independent, locked numeric counters for restaurant setup records."""
import frappe
from frappe.model.naming import getseries


def next_numeric_id(doctype):
    while True:
        name = getseries("retail-restaurant-id:" + doctype, 1)
        if not frappe.db.exists(doctype, name):
            return name
