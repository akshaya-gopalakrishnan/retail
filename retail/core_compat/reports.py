"""Keep native report names, permissions, exports and prepared-report execution."""
from pathlib import Path

import frappe
from frappe.core.doctype.report.report import Report
from frappe.desk.query_report import get_script as standard_get_script


class RetailReport(Report):
    def execute_module(self, filters):
        if self.name in ("Accounts Receivable", "Accounts Payable"):
            from retail.core_compat.accounts_receivable import ReceivablePayableReport

            payable = self.name == "Accounts Payable"
            return ReceivablePayableReport(filters).run({
                "account_type": "Payable" if payable else "Receivable",
                "naming_by": ["Buying Settings", "supp_master_name"] if payable
                else ["Selling Settings", "cust_master_name"],
            })
        if self.name in ("Accounts Receivable Summary", "Accounts Payable Summary"):
            from retail.core_compat.accounts_receivable_summary import AccountsReceivableSummary

            payable = self.name == "Accounts Payable Summary"
            return AccountsReceivableSummary(filters).run({
                "account_type": "Payable" if payable else "Receivable",
                "naming_by": ["Buying Settings", "supp_master_name"] if payable
                else ["Selling Settings", "cust_master_name"],
            })
        if self.name == "Item-wise Sales Register":
            from erpnext.accounts.report.item_wise_sales_register.item_wise_sales_register import _execute
            from retail.report_transaction_identity import enrich_report

            result = _execute(frappe._dict(filters or {}), additional_table_columns=[{
                "fieldname": "name", "label": "Source Item Row", "fieldtype": "Data",
                "hidden": 1, "_doctype": "Sales Invoice Item",
            }])
            for row in result[1]:
                if isinstance(row, dict) and row.get("invoice") and row.get("name"):
                    row["retail_source_detail"] = row["name"]
            return enrich_report(self.name, result, filters)
        if self.name == "Gross Profit":
            from retail.core_compat.gross_profit import execute

            return execute(frappe._dict(filters or {}))
        from retail.report_transaction_identity import enrich_report

        return enrich_report(self.name, super().execute_module(filters), filters)


@frappe.whitelist()
def get_script(report_name):
    result = standard_get_script(report_name)
    if report_name in ("Accounts Receivable", "Accounts Payable"):
        filename = frappe.scrub(report_name) + ".js"
        result["script"] = Path(__file__).with_name(filename).read_text() + "\n//# sourceURL=retail_" + filename
    return result
