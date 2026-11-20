"""Install barcode display fields on existing BOMs."""


def execute():
    from retail.bom_item_identity import install

    install()
