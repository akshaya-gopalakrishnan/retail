import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from retail.promotions.schedule import sync_scheme_hours
from retail.promotions.promo_price import get_purchase_prices, synchronize_discount

from retail.promotions.scheme_builder import (
	add_product_to_scheme,
	build_new_scheme,
	ensure_products,
	retire_linked_schemes,
	update_linked_schemes,
	validate_active_dates,
)


class PromoPrice(Document):
	def validate(self):
		validate_active_dates(self)
		ensure_products(self.products)
		self.validate_products()

	def on_update(self):
		self.sync_promotional_scheme()

	def on_trash(self):
		retire_linked_schemes(self)

	def validate_products(self):
		scope = self.get("promotion_scope") or ("CATEGORY" if self.products[0].item_group else "ITEM")
		self.promotion_scope = scope
		target = {"ITEM": "item", "CATEGORY": "item_group", "BRAND": "brand", "WHOLE BILL": None}.get(scope)
		if scope not in ("ITEM", "CATEGORY", "BRAND", "WHOLE BILL"):
			frappe.throw(_("Select a valid promotion scope."))
		if scope == "WHOLE BILL" and len(self.products) != 1:
			frappe.throw(_("Whole Bill requires one promotion row for all items."))
		for row in self.products:
			if any(row.get(field) for field in ("item", "item_group", "brand") if field != target):
				frappe.throw(_("Row #{0}: Only the selected promotion scope is allowed.").format(row.idx))
			if target and not row.get(target):
				frappe.throw(_("Row #{0}: Select {1}.").format(row.idx, scope))
			synchronize_discount(row)
			if row.item:
				row.update(get_purchase_prices(row.item, row.uom))
			else:
				row.purchase_price = row.purchase_price_including_tax = 0

			has_price = flt(row.promo_price) or flt(row.promo_price_including_tax)
			if has_price and flt(row.discount_percent):
				frappe.throw(_("Row #{0}: Use Promo Price or Discount %, not both.").format(row.idx))

			if not has_price and not flt(row.discount_percent):
				frappe.throw(_("Row #{0}: Enter Promo Price or Discount %.").format(row.idx))

	def sync_promotional_scheme(self):
		retire_linked_schemes(self)
		for row in self.products:
			apply_on = "Brand" if row.get("brand") else "Item Code" if row.item else "Item Group"
			scheme = build_new_scheme(self, apply_on)
			scheme.name = f"{self.name}-{row.idx}-{frappe.generate_hash(length=6)}"
			if self.promotion_scope == "WHOLE BILL":
				for group in frappe.get_all("Item Group", fields=["name", "parent_item_group"]):
					if not group.parent_item_group:
						scheme.append("item_groups", {"item_group": group.name})
			else:
				add_product_to_scheme(scheme, row)
			scheme.append(
				"price_discount_slabs",
				{
					"disable": self.disabled,
					"rule_description": self.description,
					"min_qty": flt(self.min_qty),
					"max_qty": flt(row.max_qty) or flt(self.max_qty),
					"min_amount": flt(self.min_sales_value),
					"rate_or_discount": "Discount Percentage" if flt(row.discount_percent) else "Rate",
					"rate": flt(row.promo_price) or flt(row.promo_price_including_tax),
					"discount_percentage": flt(row.discount_percent),
					"for_price_list": row.price_list,
					"warehouse": self.warehouse,
					"priority": str(self.priority) if self.priority else None,
				},
			)
			scheme.insert(ignore_permissions=True)
			sync_scheme_hours(self, scheme)
			self.append("linked_schemes", {"promotional_scheme": scheme.name})

		update_linked_schemes(self)
