from retail.domains.item.scale_export_service import ensure_default_scale_export_template
from retail.domains.item.scale_item_validation import ensure_scale_item_setup
from retail.retail_app.doctype.scale_barcode_format.scale_barcode_format import (
	ensure_default_scale_barcode_format,
)


def execute():
	ensure_scale_item_setup()
	ensure_default_scale_barcode_format()
	ensure_default_scale_export_template()
