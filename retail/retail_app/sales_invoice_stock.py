import frappe


def ensure_stock_update(doc, method=None):
    if isinstance(doc, dict):
        doc = frappe._dict(doc)
        doc.items = [frappe._dict(row) for row in doc.get("items", [])]

    stock_items = []
    for row in doc.get("items", []):
        if row.item_code and frappe.get_cached_value("Item", row.item_code, "is_stock_item"):
            stock_items.append(row)

    if not stock_items:
        return

    doc.update_stock = 1

    for row in stock_items:
        if not row.warehouse:
            row.warehouse = get_default_warehouse(doc.company, row.item_code)


def get_default_warehouse(company, item_code=None):
    if item_code:
        warehouse = get_item_stock_warehouse(company, item_code)
        if warehouse:
            return warehouse

    warehouse = frappe.db.get_single_value("Stock Settings", "default_warehouse")
    if warehouse and is_company_warehouse(warehouse, company):
        return warehouse

    abbr = frappe.db.get_value("Company", company, "abbr")
    if abbr:
        warehouse = frappe.db.exists("Warehouse", f"Stores - {abbr}")
        if warehouse and is_company_warehouse(warehouse, company):
            return warehouse

    return frappe.db.get_value(
        "Warehouse",
        {
            "company": company,
            "is_group": 0,
            "disabled": 0,
        },
        "name",
        order_by="name asc",
    )


def get_item_stock_warehouse(company, item_code):
    for row in frappe.db.get_all(
        "Bin",
        filters={
            "item_code": item_code,
            "actual_qty": [">", 0],
        },
        fields=["warehouse"],
        order_by="actual_qty desc",
    ):
        if is_company_warehouse(row.warehouse, company):
            return row.warehouse


def is_company_warehouse(warehouse, company):
    return frappe.db.get_value("Warehouse", warehouse, "company") == company
