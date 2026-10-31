def execute():
    from retail.pos_invoice_dates import configure
    from retail.pos_invoice_layout import execute as arrange_layout

    configure()
    arrange_layout()
