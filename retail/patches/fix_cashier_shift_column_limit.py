"""Include Frappe's hidden Tags column so closing timestamps remain visible."""


def execute():
    from retail.patches.show_cashier_shift_dates import execute as configure
    configure()
