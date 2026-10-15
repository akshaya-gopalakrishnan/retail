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
        if self.name == "Gross Profit":
            from retail.core_compat.gross_profit import execute

            return execute(frappe._dict(filters or {}))
        return super().execute_module(filters)


@frappe.whitelist()
def get_script(report_name):
    result = standard_get_script(report_name)
    if report_name in ("Accounts Receivable", "Accounts Payable"):
        filename = frappe.scrub(report_name) + ".js"
        result["script"] = Path(__file__).with_name(filename).read_text() + "\n//# sourceURL=retail_" + filename
    return result
