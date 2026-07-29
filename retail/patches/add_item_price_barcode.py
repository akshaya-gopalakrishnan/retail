from retail.domains.item.average_purchase_rate import ensure_item_price_list_field
from retail.domains.item.item_price_sync import ensure_item_price_barcode_field, sync_item_price_barcodes


def execute():
	ensure_item_price_barcode_field()
	ensure_item_price_list_field()
	sync_item_price_barcodes()
