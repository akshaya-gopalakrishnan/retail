"""Separate future POS accounting IDs without renaming existing invoices."""


def execute():
    from retail.short_codes import install
    install(doctypes=["Sales Invoice", "POS Invoice"])
