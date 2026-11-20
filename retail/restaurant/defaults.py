import frappe


def single_branch():
    branches = frappe.get_all("Branch", pluck="name", limit_page_length=2)
    return branches[0] if len(branches) == 1 else None


def boot(bootinfo):
    bootinfo.retail_restaurant_default_branch = single_branch()
