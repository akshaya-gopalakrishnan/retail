"""One-time setup for all Item Master customizations."""

from retail.domains.item.naming import install_item_code_defaults
from retail.domains.item.average_purchase_rate import (
	clear_average_purchase_rate_description,
	ensure_item_price_list_field,
)
from retail.domains.item.item_price_sync import (
	disable_legacy_last_purchase_rate_script,
	ensure_standard_purchase_rate_field,
)
from retail.domains.item.packing_rate import ensure_packing_purchase_rate_script
from retail.domains.item.vat_pricing import ensure_item_vat_pricing_fields


def execute():
	"""Apply the complete Item Master configuration in one idempotent step."""
	install_item_code_defaults()
	clear_average_purchase_rate_description()
	ensure_item_price_list_field()
	disable_legacy_last_purchase_rate_script()
	ensure_standard_purchase_rate_field()
	ensure_packing_purchase_rate_script()
	ensure_item_vat_pricing_fields()
