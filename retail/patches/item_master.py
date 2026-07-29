"""One-time setup for all Item Master customizations."""

import frappe

from retail.domains.item.naming import install_item_code_defaults
from retail.domains.item.average_purchase_rate import (
	clear_average_purchase_rate_description,
	ensure_item_price_list_field,
)
from retail.domains.item.item_price_sync import (
	disable_legacy_last_purchase_rate_script,
	ensure_item_price_barcode_field,
	ensure_standard_purchase_rate_field,
	sync_item_price_barcodes,
)
from retail.domains.item.packing_rate import ensure_packing_purchase_rate_script
from retail.domains.item.vat_pricing import ensure_item_vat_pricing_fields, ensure_packing_vat_pricing_fields


LEGACY_ITEM_MARGIN_CLIENT_SCRIPTS = ("Margin", "Margin %")


def execute():
	"""Apply the complete Item Master configuration in one idempotent step."""
	install_item_code_defaults()
	clear_average_purchase_rate_description()
	ensure_item_price_list_field()
	disable_legacy_last_purchase_rate_script()
	ensure_standard_purchase_rate_field()
	ensure_item_price_barcode_field()
	ensure_packing_purchase_rate_script()
	ensure_item_vat_pricing_fields()
	ensure_packing_vat_pricing_fields()
	sync_item_price_barcodes()
	remove_legacy_item_margin_scripts()


def remove_legacy_item_margin_scripts():
	for script_name in LEGACY_ITEM_MARGIN_CLIENT_SCRIPTS:
		if frappe.db.exists("Client Script", script_name):
			frappe.delete_doc("Client Script", script_name, force=True, ignore_permissions=True)

	frappe.clear_cache(doctype="Item")
