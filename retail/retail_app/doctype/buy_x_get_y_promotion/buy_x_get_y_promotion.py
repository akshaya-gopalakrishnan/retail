import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from retail.promotions.scheme_builder import (
	add_product_to_scheme,
	build_base_scheme,
	ensure_products,
	retire_linked_schemes,
	update_linked_schemes,
	validate_active_dates,
	validate_product_row,
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

		apply_on = None
		for row in buy_rows:
			validate_product_row(row)
			row_apply_on = "Item Code" if row.item else "Item Group"
			apply_on = apply_on or row_apply_on
			if apply_on != row_apply_on:
				frappe.throw(_("Use either Items or Item Groups for Buy Items in one promotion."))

		for row in free_rows:
			if row.item_group:
				frappe.throw(_("Row #{0}: Free Item must be an Item.").format(row.idx))
			if not row.item:
				frappe.throw(_("Row #{0}: Select the Free Item.").format(row.idx))

	def sync_promotional_scheme(self):
		retire_linked_schemes(self)
		buy_rows = self.get_buy_rows()
		free_rows = self.get_free_rows()
		apply_on = "Item Code" if buy_rows[0].item else "Item Group"
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
