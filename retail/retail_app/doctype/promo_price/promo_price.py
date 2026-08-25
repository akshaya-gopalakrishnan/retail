import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from retail.promotions.scheme_builder import (
	add_product_to_scheme,
	build_new_scheme,
	ensure_products,
	retire_linked_schemes,
	update_linked_schemes,
	validate_active_dates,
	validate_product_row,
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
		apply_on = None
		for row in self.products:
			validate_product_row(row)
			row_apply_on = "Item Code" if row.item else "Item Group"
			apply_on = apply_on or row_apply_on
			if apply_on != row_apply_on:
				frappe.throw(_("Use either Items or Item Groups in one Promo Price."))

			has_price = flt(row.promo_price) or flt(row.promo_price_including_tax)
			if has_price and flt(row.discount_percent):
				frappe.throw(_("Row #{0}: Use Promo Price or Discount %, not both.").format(row.idx))

			if not has_price and not flt(row.discount_percent):
				frappe.throw(_("Row #{0}: Enter Promo Price or Discount %.").format(row.idx))

	def sync_promotional_scheme(self):
		retire_linked_schemes(self)
		for row in self.products:
			apply_on = "Item Code" if row.item else "Item Group"
			scheme = build_new_scheme(self, apply_on)
			scheme.name = f"{self.name}-{row.idx}-{frappe.generate_hash(length=6)}"
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
			self.append("linked_schemes", {"promotional_scheme": scheme.name})

		update_linked_schemes(self)
