import frappe
from frappe import _
from frappe.utils import cint


PRIVILEGE_LABELS = {
	"CHANGE_BILL_SETTLEMENT": "Change Bill Settlement / Credit Collections",
	"REOPEN_DAY_CLOSING": "Reopen Day Closing",
	"ADJUST_DAY_CLOSING_PAYMENTS": "Adjust Day Closing Counted Payments",
	"CHANGE_SETTLED_BILL_MOP": "Change Settled Bill Payment Method",
	"VOID_ITEMS": "Void Items",
	"CHANGE_QTY": "Change Quantity",
	"CHANGE_PRICE": "Change Price",
	"CHANGE_WAITER": "Change Waiter",
	"CHANGE_DELIVERYBY": "Change Delivery Person",
	"CHANGE_SALESMAN": "Change Salesperson",
	"CANCEL_BILL": "Cancel Bill",
	"REFUND_BILL": "Refund Bill",
	"HOLD_BILL": "Hold Bill",
	"RECALL_BILL": "Recall Bill",
	"INVRECALL_BILL": "Invoice Recall Bill",
	"ITEMS_EXCHANGE": "Exchange Items",
	"ADJUSTMENT": "Adjustment",
	"DISCOUNT_ITEM": "Item Discount",
	"DISCOUNT_BILL": "Bill Discount",
	"COUPON": "Coupon",
	"LOYALTY": "Loyalty",
	"REDEEM": "Redeem",
	"DELETE_CUSTOMER": "Delete Customer",
	"CREDIT_CUSTOMER": "Credit Customer",
	"CREDIT_CUSTOMER_LIMIT": "Customer Credit Limit",
	"CREDIT_CUSTOMER_PAYMENT": "Customer Credit Payment",
	"CREDIT_NOTE_ISSUE": "Issue Credit Note",
	"CREDIT_NOTE_RECALL": "Recall Credit Note",
	"SEND_EMAIL": "Send Email",
	"OPEN_DRAWER": "Open Cash Drawer",
	"CASHIN_CASHOUT": "Cash In / Cash Out",
	"CLOCKIN_CLOCKOUT": "Clock In / Clock Out",
	"SHIFT_CLOSING": "Shift Closing",
	"DAY_CLOSING": "Day Closing",
	"PRINT_SHIFT_CLOSING": "Print Shift Closing",
	"SALES_REPORT": "Sales Report",
	"INVOICE_LOOKUP": "Invoice Lookup",
	"COST_VIEW": "View Cost",
	"WARRANTY_LOOKUP": "Warranty Lookup",
	"PRICE_ENQUIRY": "Price Enquiry",
	"PRODUCT_INFO": "Product Information",
}


def profile_privileges(profile_name):
	profile = frappe.get_doc("POS Operator Privilege", profile_name) if profile_name else None
	return {
		code: bool(profile and not cint(profile.disabled) and cint(profile.get(code.lower())))
		for code in PRIVILEGE_LABELS
	}


def add_operator_privileges(rows):
	profiles = {}
	for row in rows:
		name = row.get("pos_operator_privilege")
		if name not in profiles:
			profiles[name] = profile_privileges(name)
		row["privilege_profile"] = name
		row["privileges"] = dict(profiles[name]) if not row.get("disabled") else dict.fromkeys(PRIVILEGE_LABELS, False)
	return rows


def validate_employee_assignment(doc, method=None):
	previous = doc.get_doc_before_save()
	old_profile = previous.get("pos_operator_privilege") if previous else None
	if doc.get("pos_operator_privilege") != old_profile:
		from retail.access_control import require_super_admin

		require_super_admin()


@frappe.whitelist()
def get_privilege_preview(employee, profile_name=None):
	frappe.get_doc("Employee", employee).check_permission("read")
	return [
		{"label": PRIVILEGE_LABELS[code], "allowed": allowed}
		for code, allowed in profile_privileges(profile_name).items()
	]
