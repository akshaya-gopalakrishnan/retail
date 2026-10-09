"""Align historical failure labels with the POS Sale operation label."""
import frappe


def execute():
    # Durable operation receipts are immutable; only ordinary failure logs
    # created by the legacy exception path are eligible for this correction.
    frappe.db.sql("""
        update `tabPOS Sync Log`
        set sync_type = 'POS Sale'
        where status = 'Failed'
          and sync_type in ('Sales Invoice', 'Credit Sales Invoice')
          and coalesce(operation_key, '') = ''
    """)
