"""Multiple BOMs in Repack, using native stock valuation and additional-cost GL rows."""

from collections import defaultdict
import json
import math

import frappe
from frappe import _
from frappe.utils import cint, flt
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry


GROUP = "custom_repack_group"


def install():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    frappe.reload_doc("retail_app", "doctype", "retail_repack_bom")
    visible = "eval:doc.purpose === 'Repack' && doc.custom_multiple_boms"
    create_custom_fields({
        "Stock Entry": [
            dict(fieldname="custom_multiple_boms", label="Multiple BOMs", fieldtype="Check",
                 insert_after="from_bom", default="0", depends_on="eval:doc.purpose === 'Repack'"),
            dict(fieldname="custom_repack_boms", label="Repack BOMs", fieldtype="Table",
                 options="Retail Repack BOM", insert_after="get_items", depends_on=visible,
                 description="Quantities are in the finished item's Stock UOM. Packing cost is the total extra charge for that BOM row, in company currency; do not repeat packaging materials already in the BOM. BOM operation costs are not added automatically."),
            dict(fieldname="custom_repack_cost_account", label="Packing Cost Account", fieldtype="Link",
                 options="Account", insert_after="custom_repack_boms", depends_on=visible,
                 description="Expense account credited for the extra packing charges."),
            dict(fieldname="custom_get_repack_items", label="Get Items from BOMs", fieldtype="Button",
                 insert_after="custom_repack_cost_account", depends_on=visible),
            dict(fieldname="custom_repack_signature", fieldtype="Long Text", hidden=1, read_only=1,
                 insert_after="custom_get_repack_items"),
        ],
        "Stock Entry Detail": [
            dict(fieldname=GROUP, label="Repack BOM Row", fieldtype="Int", read_only=1,
                 insert_after="bom_no", depends_on="eval:parent.custom_multiple_boms", no_copy=0),
        ],
        "Landed Cost Taxes and Charges": [
            dict(fieldname=GROUP, label="Repack BOM Row", fieldtype="Int", hidden=1, read_only=1),
        ],
    }, update=True, ignore_validate=True)


def _positive(value, label, allow_zero=False):
    number = flt(value)
    if not math.isfinite(number) or number < 0 or (number == 0 and not allow_zero):
        frappe.throw(_("{0} must be {1}.").format(label, _("zero or greater") if allow_zero else _("greater than zero")))
    return number


def _signature(doc):
    # Charges may be edited without regenerating materials; quantities/BOMs may not.
    return json.dumps([
        [r.bom_no, flt(r.qty), r.source_warehouse or doc.from_warehouse,
         r.target_warehouse or doc.to_warehouse, cint(r.use_multi_level_bom)]
        for r in doc.get("custom_repack_boms") or []
    ], separators=(",", ":"))


def _check_mode(doc):
    if doc.purpose != "Repack" or doc.work_order or doc.get("custom_is_van_stock_entry"):
        frappe.throw(_("Multiple BOMs are available only for independent Repack Stock Entries."))
    if not doc.company:
        frappe.throw(_("Select Company first."))
    if doc.from_bom or doc.bom_no or flt(doc.process_loss_qty) or flt(doc.process_loss_percentage):
        frappe.throw(_("Clear the single BOM and process loss fields before using Multiple BOMs."))
    if not doc.get("custom_repack_boms"):
        frappe.throw(_("Add at least one Repack BOM row."))


def _get_boms(doc):
    boms = {}
    for r in doc.custom_repack_boms:
        _positive(r.qty, _("BOM row {0}: Quantity").format(r.idx))
        _positive(r.packing_cost, _("BOM row {0}: Packing Cost").format(r.idx), allow_zero=True)
        bom = frappe.get_doc("BOM", r.bom_no)
        bom.check_permission("read")
        if bom.docstatus != 1 or not bom.is_active or bom.company != doc.company:
            frappe.throw(_("BOM row {0}: select an active, submitted BOM for this company.").format(r.idx))
        if bom.scrap_items or flt(bom.process_loss_percentage):
            frappe.throw(_("BOM row {0}: BOMs with scrap or process loss require a separate Stock Entry.").format(r.idx))
        if cint(r.use_multi_level_bom):
            # Exploding a BOM must not silently discard a sub-assembly's scrap/loss.
            pending, visited = [bom], set()
            while pending:
                current = pending.pop()
                if current.name in visited:
                    continue
                visited.add(current.name)
                if current.scrap_items or flt(current.process_loss_percentage):
                    frappe.throw(_("BOM row {0}: an exploded sub-BOM has scrap or process loss; use a separate Stock Entry.").format(r.idx))
                for component in current.items:
                    if component.bom_no and not component.do_not_explode:
                        sub = frappe.get_doc("BOM", component.bom_no)
                        sub.check_permission("read")
                        pending.append(sub)
        item = frappe.get_cached_doc("Item", bom.item)
        if not item.is_stock_item or item.disabled or item.has_variants:
            frappe.throw(_("BOM row {0}: the finished item must be an enabled stock item.").format(r.idx))
        r.finished_item = bom.item
        r.stock_uom = item.stock_uom
        boms[r.idx] = bom
    return boms


def _check_warehouse(name, company):
    if not name:
        frappe.throw(_("Set source and target warehouses in each BOM row or in Default Warehouse."))
    warehouse = frappe.get_doc("Warehouse", name)
    warehouse.check_permission("read")
    if warehouse.company != company or warehouse.is_group or warehouse.disabled:
        frappe.throw(_("Warehouse {0} must be an enabled warehouse for this company.").format(name))


def _sync_packing_costs(doc):
    amounts = {r.idx: _positive(r.packing_cost, _("Packing Cost"), allow_zero=True)
               for r in doc.custom_repack_boms if flt(r.packing_cost)}
    currency = frappe.get_cached_value("Company", doc.company, "default_currency")
    if amounts:
        account = frappe.get_doc("Account", doc.get("custom_repack_cost_account")) if doc.get("custom_repack_cost_account") else None
        if not account or account.company != doc.company or account.is_group or account.disabled or account.root_type != "Expense" or account.account_currency != currency:
            frappe.throw(_("Select an enabled Packing Cost Account under Expenses, in the company currency."))
        account.check_permission("read")
    doc.set("additional_costs", [r for r in doc.get("additional_costs") or [] if not r.get(GROUP)])
    for r in doc.custom_repack_boms:
        if r.idx in amounts:
            doc.append("additional_costs", {
                GROUP: r.idx, "expense_account": doc.custom_repack_cost_account,
                "description": _("Packing cost: BOM row {0} ({1})").format(r.idx, r.bom_no),
                "amount": amounts[r.idx], "base_amount": amounts[r.idx],
                "account_currency": currency, "exchange_rate": 1,
            })


def _group_items(doc):
    configs = doc.custom_repack_boms
    if doc.get("custom_product_conversion"):
        configs = [frappe._dict(r) for r in frappe.parse_json(doc.get("custom_conversion_groups") or "[]")]
    groups = {r.idx: {"config": r, "inputs": [], "outputs": []} for r in configs}
    for item in doc.items:
        group = groups.get(cint(item.get(GROUP)))
        if not group:
            frappe.throw(_("Every item must belong to a Repack BOM row. Use Get Items from BOMs to rebuild."))
        if bool(item.s_warehouse) == bool(item.t_warehouse) or item.is_scrap_item:
            frappe.throw(_("Repack items must have either a source or a target warehouse."))
        _positive(item.qty, _("Item Quantity"))
        _positive(item.conversion_factor, _("Conversion Factor"))
        group["inputs" if item.s_warehouse else "outputs"].append(item)
    for group in groups.values():
        config, outputs = group["config"], group["outputs"]
        if not group["inputs"] or not outputs:
            frappe.throw(_("Every BOM row must have materials and a finished item. Use Get Items from BOMs."))
        if any(r.item_code != config.finished_item or r.bom_no != config.bom_no for r in outputs):
            frappe.throw(_("Finished items must match their Repack BOM row."))
        output_qty = sum(flt(r.qty) * flt(r.conversion_factor) for r in outputs)
        if abs(output_qty - flt(config.qty)) > 0.000001:
            frappe.throw(_("Finished quantity differs from its BOM row. Change the BOM quantity and reload items."))
        for item in outputs:
            item.is_finished_item = 1
            item.set_basic_rate_manually = 1
        for item in group["inputs"]:
            item.is_finished_item = 0
    output_codes = {r.item_code for g in groups.values() for r in g["outputs"]}
    if any(r.item_code in output_codes for g in groups.values() for r in g["inputs"]):
        frappe.throw(_("An output item cannot also be consumed in the same multi-BOM Repack. Use sequential Stock Entries."))
    return groups


def _allocate(total, rows, weights, precision_field):
    """Keep currency totals intact when an output is split into batch rows."""
    denominator = sum(weights)
    used = 0.0
    for index, row in enumerate(rows):
        share = total - used if index == len(rows) - 1 else total * weights[index] / denominator
        amount = flt(share, row.precision(precision_field))
        used += amount
        yield row, amount


class RetailStockEntry(StockEntry):
    def validate(self):
        if self.get("custom_product_conversion"):
            from retail.product_conversion import validate_stock_entry

            validate_stock_entry(self)
            _group_items(self)
        elif self.get("custom_multiple_boms"):
            _check_mode(self)
            _get_boms(self)
            if self.get("custom_repack_signature") != _signature(self):
                frappe.throw(_("BOMs, quantities or default warehouses changed. Click Get Items from BOMs again."))
            _group_items(self)
            _sync_packing_costs(self)
        elif any(r.get(GROUP) for r in self.get("items") or []) or any(r.get(GROUP) for r in self.get("additional_costs") or []):
            frappe.throw(_("Keep Multiple BOMs enabled while BOM-generated items or packing costs exist."))
        super().validate()

    @frappe.whitelist()
    def get_items(self):
        if not self.get("custom_multiple_boms"):
            return super().get_items()
        if self.docstatus != 0:
            frappe.throw(_("Items can only be loaded into a draft Stock Entry."))
        self.check_permission("write" if not self.is_new() else "create")
        _check_mode(self)
        boms = _get_boms(self)
        if any(r.item_code and not r.get(GROUP) for r in self.items):
            frappe.throw(_("Clear the existing Items table before loading multiple BOMs."))
        if any(r.serial_and_batch_bundle for r in self.items):
            frappe.throw(_("Remove the assigned Serial and Batch Bundles before rebuilding items."))
        self.set("items", [])
        for config in self.custom_repack_boms:
            source = config.source_warehouse or self.from_warehouse
            target = config.target_warehouse or self.to_warehouse
            _check_warehouse(source, self.company)
            _check_warehouse(target, self.company)
            # Core clears document defaults when source-only and target-only
            # rows coexist. Keep the resolved warehouses on the BOM rows so
            # subsequent saves and reloads retain the same recipe settings.
            config.source_warehouse = source
            config.target_warehouse = target
            # Reuse ERPNext's BOM expansion, UOM conversion, defaults and row builder.
            temp = frappe.new_doc("Stock Entry")
            temp.update(dict(company=self.company, purpose="Repack", from_warehouse=source,
                             to_warehouse=target, bom_no=config.bom_no, fg_completed_qty=config.qty,
                             use_multi_level_bom=config.use_multi_level_bom))
            materials = temp.get_bom_raw_materials(config.qty)
            if not materials:
                frappe.throw(_("BOM row {0} has no stock materials.").format(config.idx))
            temp.add_to_stock_entry_detail(materials)
            for material in temp.items:
                material.t_warehouse = None
            temp.load_items_from_bom()
            for row in temp.items:
                values = row.as_dict()
                for field in ("name", "parent", "parenttype", "parentfield", "idx", "docstatus", "creation", "modified", "owner", "modified_by"):
                    values.pop(field, None)
                values[GROUP] = config.idx
                values["bom_no"] = boms[config.idx].name
                self.append("items", values)
        _group_items(self)
        _sync_packing_costs(self)
        self.custom_repack_signature = _signature(self)
        self.set_missing_values()

    def set_basic_rate(self, reset_outgoing_rate=True, raise_error_if_no_rate=True):
        if not (self.get("custom_multiple_boms") or self.get("custom_product_conversion")) or self.purpose != "Repack":
            return super().set_basic_rate(reset_outgoing_rate, raise_error_if_no_rate)
        groups = _group_items(self)
        super().set_basic_rate(reset_outgoing_rate, raise_error_if_no_rate)
        # Also runs during ledger reposts, using ERPNext's refreshed outgoing rates.
        for group in groups.values():
            material_cost = sum(flt(r.basic_amount) for r in group["inputs"])
            outputs = group["outputs"]
            for row, amount in _allocate(material_cost, outputs, [flt(r.transfer_qty) for r in outputs], "basic_amount"):
                row.basic_amount = amount
                row.basic_rate = amount / flt(row.transfer_qty)

    def set_rate_for_outgoing_items(self, reset_outgoing_rate=True, raise_error_if_no_rate=True):
        if self.get('custom_product_conversion') and self.get('name') and not reset_outgoing_rate and self.docstatus != 2:
            from retail.product_conversion import apply_ledger_source_rates

            apply_ledger_source_rates(self)
        cost = super().set_rate_for_outgoing_items(reset_outgoing_rate, raise_error_if_no_rate)
        if self.get('custom_product_conversion') and reset_outgoing_rate:
            from retail.product_conversion import apply_sequential_source_rates

            apply_sequential_source_rates(self, raise_error_if_no_rate)
            cost = sum(flt(r.basic_amount) for r in self.items if r.s_warehouse)
        return cost

    def distribute_additional_costs(self):
        if not (self.get("custom_multiple_boms") or self.get("custom_product_conversion")) or self.purpose != "Repack":
            return super().distribute_additional_costs()
        groups = _group_items(self)
        targeted, shared = defaultdict(float), 0.0
        for cost in self.additional_costs:
            if cost.get(GROUP):
                if cint(cost.get(GROUP)) not in groups:
                    frappe.throw(_("Packing cost refers to a missing BOM row. Reload items."))
                targeted[cint(cost.get(GROUP))] += flt(cost.base_amount)
            else:
                shared += flt(cost.base_amount)
        self.total_additional_costs = sum(flt(c.base_amount) for c in self.additional_costs)
        outputs = [r for g in groups.values() for r in g["outputs"]]
        base_total = sum(flt(r.basic_amount) for r in outputs)
        for row in self.items:
            row.additional_cost = 0
        for key, group in groups.items():
            rows = group["outputs"]
            for row, amount in _allocate(targeted[key], rows, [flt(r.transfer_qty) for r in rows], "amount"):
                row.additional_cost = amount
        weights = [flt(r.basic_amount) if base_total else flt(r.transfer_qty) for r in outputs]
        for row, amount in _allocate(shared, outputs, weights, "amount"):
            row.additional_cost += amount
