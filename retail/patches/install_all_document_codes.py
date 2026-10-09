def execute():
    from retail.short_codes import install
    from retail.document_codes import install as install_public_codes
    install(["Employee", "Item", "Driver"])
    install_public_codes()
