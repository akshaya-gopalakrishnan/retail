frappe.query_reports["Shift Closing Variance"] = {
	filters: get_pos_report_filters({ include_cashier: true, include_shift: true }),
};

{
 const settings = frappe.query_reports["Shift Closing Variance"];
 const previous = settings.onload;
 settings.onload = async function(report) {
  window.retail_setup_pos_printing(report);
  if (previous) return previous.call(this, report);
 };
}
