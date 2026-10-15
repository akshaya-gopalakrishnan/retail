import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from retail.promotions.schedule import sync_scheme_hours

from retail.promotions.scheme_builder import (
	add_product_to_scheme,
	build_base_scheme,
	ensure_products,
	retire_linked_schemes,
	update_linked_schemes,
	validate_active_dates,
)


class BuyXGetYPromotion(Document):
	def validate(self):
		validate_active_dates(self)
		ensure_products(self.products)
		self.validate_products()

	def on_update(self):
		self.sync_promotional_scheme()

	def on_trash(self):
		retire_linked_schemes(self)

	def validate_products(self):
		if flt(self.buy_qty) <= 0:
			frappe.throw(_("Buy Qty must be greater than zero."))
		if flt(self.free_qty) <= 0:
			frappe.throw(_("Free Qty must be greater than zero."))

		buy_rows = self.get_buy_rows()
		free_rows = self.get_free_rows()
		if not buy_rows:
			frappe.throw(_("Add at least one Buy Item."))
		if not self.same_product_only and not free_rows:
			frappe.throw(_("Add at least one Free Item."))

		scope = self.get("promotion_scope") or ("CATEGORY" if buy_rows[0].item_group else "BRAND" if buy_rows[0].get("brand") else "ITEM")
		self.promotion_scope = scope
		target = {"ITEM": "item", "CATEGORY": "item_group", "BRAND": "brand"}.get(scope)
		if not target:
			frappe.throw(_("Select ITEM, CATEGORY or BRAND."))
		for row in buy_rows:
			if any(row.get(field) for field in ("item", "item_group", "brand") if field != target):
				frappe.throw(_("Row #{0}: Only the selected promotion scope is allowed.").format(row.idx))
			if not row.get(target):
				frappe.throw(_("Row #{0}: Select {1}.").format(row.idx, scope))
		for row in self.products:
			if row.add_to not in ("Buy Item", "Free Item"):
				frappe.throw(_("Row #{0}: Select Buy Item or Free Item.").format(row.idx))

		for row in free_rows:
			if row.item_group or row.get("brand"):
				frappe.throw(_("Row #{0}: Free Item must be an Item.").format(row.idx))
			if not row.item:
				frappe.throw(_("Row #{0}: Select the Free Item.").format(row.idx))

	def sync_promotional_scheme(self):
		retire_linked_schemes(self)
		buy_rows = self.get_buy_rows()
		free_rows = self.get_free_rows()
		apply_on = {"ITEM": "Item Code", "CATEGORY": "Item Group", "BRAND": "Brand"}[self.promotion_scope]
		scheme = build_base_scheme(self, apply_on)

		for row in buy_rows:
			add_product_to_scheme(scheme, row)

		if self.same_product_only:
			scheme.append("product_discount_slabs", self.get_product_slab())
		else:
			for row in free_rows:
				slab = self.get_product_slab()
				slab.update({"free_item": row.item, "free_item_uom": row.uom})
				scheme.append("product_discount_slabs", slab)

		scheme.name = f"{self.name}-{frappe.generate_hash(length=6)}"
		scheme.insert(ignore_permissions=True)
		sync_scheme_hours(self, scheme)
		self.append("linked_schemes", {"promotional_scheme": scheme.name})
		update_linked_schemes(self)

	def get_product_slab(self):
		return {
			"disable": self.disabled,
			"rule_description": self.description,
			"min_qty": flt(self.buy_qty),
			"free_qty": flt(self.free_qty),
			"same_item": 1 if self.same_product_only else 0,
			"free_item_rate": 0,
			"warehouse": self.warehouse,
			"priority": str(self.priority) if self.priority else None,
		}

	def get_buy_rows(self):
		return [row for row in self.products if row.add_to == "Buy Item"]

	def get_free_rows(self):
		return [row for row in self.products if row.add_to == "Free Item"]
