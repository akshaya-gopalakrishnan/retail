"""Create site-owned report layouts once and read them under report print access."""

from pathlib import Path

import frappe
from frappe import _
from frappe.desk.query_report import get_report_doc
from retail.retail_app.report.pos_report_utils import POS_REPORTS

POS_PRINT_REPORTS = (*POS_REPORTS, "POS Invoice Profit", "POS Settlement Audit", "Counter Performance")


REPORT_FORMATS = {
	"Daily Sales Summary": "Daily Sales Summary - A4",
	"Accounts Receivable": "Accounts Receivable - A4",
	"Accounts Payable": "Accounts Payable - A4",
	**{name: f"{name} - A4" for name in POS_PRINT_REPORTS},
}


def ensure_report_print_formats():
	if not frappe.db.table_exists("Print Format"):
		return
	root = Path(__file__).parent / "templates" / "report_print_formats"
	for report_name, format_name in REPORT_FORMATS.items():
		if not frappe.db.exists("Report", report_name) or frappe.db.exists("Print Format", format_name):
			continue
		slug = "pos_report" if report_name in POS_PRINT_REPORTS else frappe.scrub(report_name)
		frappe.get_doc({
			"doctype": "Print Format",
			"name": format_name,
			"print_format_for": "Report",
			"report": report_name,
			"module": "Retail-app",
			"standard": "No",
			"custom_format": 1,
			"print_format_type": "JS",
			"html": (root / f"{slug}.html").read_text(),
			"css": (root / f"{slug}.css").read_text(),
		}).insert(ignore_permissions=True)


@frappe.whitelist()
def get_report_format(report_name, format_name=None):
	if report_name not in REPORT_FORMATS:
		frappe.throw(_("Report print format is not configured."), frappe.PermissionError)
	report = get_report_doc(report_name)
	if not frappe.has_permission(report.ref_doctype, "read") or not frappe.has_permission(report.ref_doctype, "print"):
		frappe.throw(_("You do not have permission to print this report."), frappe.PermissionError)

	# Printing a permitted report does not grant access to the Print Format editor.
	# Read only a layout explicitly attached to this report, including for users
	# who can print reports but cannot read the Print Format administration screen.
	layout = frappe.get_doc("Print Format", format_name or REPORT_FORMATS[report_name])
	if (layout.disabled or layout.print_format_for != "Report" or layout.report != report_name
		or layout.print_format_type != "JS" or layout.raw_printing):
		frappe.throw(_("Please select an enabled print format for this report."), frappe.ValidationError)
	return {"name": layout.name, "html": layout.html, "css": layout.css}
