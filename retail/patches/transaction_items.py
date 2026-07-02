"""Shared metadata customisations for buying and selling transaction item rows."""

from retail.domains.foc import ensure_foc_fields


def execute():
	ensure_transaction_item_fields()


def ensure_transaction_item_fields():
	ensure_foc_fields()
