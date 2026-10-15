"""Resolve chart display names in batches without changing series or grouping."""
import frappe

TITLE_FIELDS = {
    "Item": "item_name", "Customer": "customer_name", "Supplier": "supplier_name",
    "Warehouse": "warehouse_name", "POS Branch Counter": "counter_name",
    "Counter": "counter_name", "Van Fleet": "vehicle_name", "Employee": "employee_name",
    "Account": "account_name", "Company": "company_name",
}


def names_for(doctype, values):
    field = TITLE_FIELDS.get(doctype)
    values = list({v for v in values if isinstance(v, str) and v})
    if not field or not values or not frappe.has_permission(doctype, "read"):
        return {}
    rows = frappe.get_list(doctype, filters={"name": ["in", values]},
                           fields=["name", field], limit_page_length=0)
    return {r.name: r.get(field) or r.name for r in rows}


def relabel(data, mapping):
    if not isinstance(data, dict):
        return data
    if "labels" in data:
        data["labels"] = [mapping.get(v, v) for v in data["labels"]]
    for dataset in data.get("datasets", []):
        dataset["name"] = mapping.get(dataset.get("name"), dataset.get("name"))
    return data


def report_labels(result):
    chart = result.get("chart") if isinstance(result, dict) else None
    if not isinstance(chart, dict):
        return result
    data = chart.get("data", chart)
    tokens = set(v for v in data.get("labels", []) if isinstance(v, str))
    tokens.update(d.get("name") for d in data.get("datasets", []) if isinstance(d.get("name"), str))
    if not tokens:
        return result
    mapping = {}
    for column in result.get("columns", []):
        if not isinstance(column, dict) or column.get("fieldtype") != "Link":
            continue
        doctype = column.get("options")
        if doctype not in TITLE_FIELDS:
            continue
        field = column.get("fieldname")
        ids = {row.get(field) for row in result.get("result", []) if isinstance(row, dict)} & tokens
        mapping.update(names_for(doctype, ids))
    relabel(data, mapping)
    return result


@frappe.whitelist()
def warehouse_stock_value(**kwargs):
    from erpnext.stock.dashboard_chart_source.warehouse_wise_stock_value.warehouse_wise_stock_value import get

    data = get(**kwargs)
    if isinstance(data, dict):
        relabel(data, names_for("Warehouse", data.get("labels", [])))
    return data
