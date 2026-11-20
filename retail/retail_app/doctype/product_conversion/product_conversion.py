import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from retail import product_conversion as conversion


class ProductConversion(Document):
    def autoname(self):
        self.name = conversion.next_conversion_name()

    def validate(self):
        if self.docstatus == 2:
            return
        conversion.normalize(self)
        conversion.check_extra_accounts(self)
        self.status = 'Posted' if self.docstatus == 1 else 'Draft'
        if self.docstatus == 0:
            self.stock_entry = None
            self.master_cost_updates = None
            for row in self.items:
                row.master_cost_updated = 0

    @frappe.whitelist()
    def refresh_costs(self):
        self.check_permission('write' if not self.is_new() else 'create')
        if self.docstatus:
            frappe.throw(_('Costs can only be refreshed on a draft.'))
        conversion.normalize(self)

    @frappe.whitelist()
    def add_product(self, values):
        self.check_permission('write' if not self.is_new() else 'create')
        if self.docstatus:
            frappe.throw(_('Products can only be added to a draft.'))
        values = frappe._dict(frappe.parse_json(values))
        qty = conversion._positive(values.qty, _('Quantity to Generate'))
        key = frappe.generate_hash(length=12)
        if values.source_type == 'BOM':
            from retail.repack import _get_boms
            temp = frappe.new_doc('Stock Entry')
            temp.company = self.company
            config = temp.append('custom_repack_boms', dict(bom_no=values.bom_no, qty=qty,
                packing_cost=0, use_multi_level_bom=values.use_multi_level_bom))
            bom = _get_boms(temp)[1]
            temp.from_warehouse = self.source_warehouse
            temp.bom_no = bom.name
            temp.use_multi_level_bom = values.use_multi_level_bom
            materials = temp.get_bom_raw_materials(qty)
            if not materials:
                frappe.throw(_('This BOM has no stock materials.'))
            output = bom.item
            for material in materials.values():
                stock_qty = flt(material.qty) * (flt(material.get('conversion_factor')) or 1)
                self.append('materials', dict(row_key=key, item_code=material.item_code,
                    qty_per_unit=stock_qty / qty, qty=stock_qty,
                    warehouse=self.source_warehouse or material.get('from_warehouse')))
            main = next(iter(materials.values())).item_code
        elif values.source_type == 'Main Item':
            conversion.stock_item(values.main_item)
            per_unit = conversion._positive(values.qty_per_unit, _('Main Item Consumption per Finished Unit'))
            output, main = values.item_code, values.main_item
            self.append('materials', dict(row_key=key, item_code=main, qty_per_unit=per_unit,
                                         qty=per_unit * qty, warehouse=self.source_warehouse, is_main_item=1))
        else:
            frappe.throw(_('Select BOM or Main Item.'))
        conversion.stock_item(output)
        self.append('items', dict(row_key=key, source_type=values.source_type,
            bom_no=values.bom_no if values.source_type == 'BOM' else None,
            use_multi_level_bom=values.use_multi_level_bom, main_item=main,
            main_qty_per_unit=values.qty_per_unit if values.source_type == 'Main Item' else None,
            item_code=output, qty=qty, labour_cost=values.labour_cost or 0,
            packing_cost=values.packing_cost or 0, update_item_master=values.update_item_master or 0))
        conversion.normalize(self)

    @frappe.whitelist()
    def update_consumption(self, values):
        self.check_permission('write' if not self.is_new() else 'create')
        if self.docstatus:
            frappe.throw(_('Consumption can only be edited on a draft.'))
        values = frappe._dict(frappe.parse_json(values))
        product = next((r for r in self.items if r.row_key == values.row_key), None)
        if not product:
            frappe.throw(_('Choose a product row.'))
        self.set('materials', [r for r in self.materials if r.row_key != product.row_key])
        for row in values.rows:
            if not row.get('item_code'):
                continue
            qty = conversion._positive(row.get('qty'), _('Quantity to Consume'))
            self.append('materials', dict(row_key=product.row_key, item_code=row['item_code'],
                qty=qty, qty_per_unit=qty/flt(product.qty), warehouse=row.get('warehouse') or self.source_warehouse,
                batch_no=row.get('batch_no'), serial_no=row.get('serial_no'),
                is_main_item=int(row['item_code'] == product.main_item and product.source_type != 'BOM')))
        if product.source_type != 'BOM':
            product.main_qty_per_unit = sum(flt(r.qty_per_unit) for r in self.materials
                if r.row_key == product.row_key and r.item_code == product.main_item)
        conversion.normalize(self)

    @frappe.whitelist()
    def add_material(self, values):
        self.check_permission('write' if not self.is_new() else 'create')
        if self.docstatus:
            frappe.throw(_('Materials can only be added to a draft.'))
        values = frappe._dict(frappe.parse_json(values))
        product = next((r for r in self.items if r.row_key == values.row_key), None)
        if not product:
            frappe.throw(_('Choose a product row.'))
        qty = conversion._positive(values.qty, _('Quantity to Consume'))
        self.append('materials', dict(row_key=product.row_key, item_code=values.item_code,
            qty=qty, qty_per_unit=qty / flt(product.qty), warehouse=values.warehouse or self.source_warehouse,
            batch_no=values.batch_no, serial_no=values.serial_no))
        conversion.normalize(self)

    def before_submit(self):
        if self.stock_entry or frappe.db.exists('Stock Entry', {'custom_product_conversion': self.name, 'docstatus': ['!=', 2]}):
            frappe.throw(_('This conversion already has a Stock Entry.'))
        frappe.has_permission('Stock Entry', 'create', throw=True)
        frappe.has_permission('Stock Entry', 'submit', throw=True)
        from collections import defaultdict
        required = defaultdict(float)
        for material in self.materials:
            required[(material.item_code, material.warehouse)] += flt(material.qty)
        for (code, warehouse), qty in required.items():
            available = flt(frappe.db.get_value('Bin', {'item_code': code, 'warehouse': warehouse}, 'actual_qty'))
            if qty > available + 0.000001:
                frappe.throw(_('Insufficient stock for {0} in {1}: required {2}, available {3}.').format(code, warehouse, qty, available))
        for item in self.items:
            if item.update_item_master:
                frappe.get_doc('Item', item.item_code).check_permission('write')

    def on_submit(self):
        previous = frappe.flags.get('product_conversion_posting')
        frappe.flags.product_conversion_posting = self.name
        try:
            entry = conversion.build_stock_entry(self)
            entry.insert()
            entry.submit()
            entry.reload()
            conversion.apply_actual_costs(self, entry)
            conversion.update_master_costs(self)
            self.stock_entry = entry.name
            self.status = 'Posted'
            self.db_update()
            for row in self.items + self.materials:
                row.db_update()
        finally:
            frappe.flags.product_conversion_posting = previous

    def before_cancel(self):
        # The linked entry must be cancelled in this same transaction.
        if self.stock_entry:
            entry = frappe.get_doc('Stock Entry', self.stock_entry)
            entry.check_permission('cancel')
            entry.ignore_linked_doctypes = ['Product Conversion']
            previous = frappe.flags.get('product_conversion_posting')
            frappe.flags.product_conversion_posting = self.name
            try:
                if entry.docstatus == 1:
                    entry.cancel()
            finally:
                frappe.flags.product_conversion_posting = previous

    def on_cancel(self):
        conversion.restore_master_costs(self)
        self.db_set('status', 'Cancelled')
