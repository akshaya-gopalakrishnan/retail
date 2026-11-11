frappe.query_reports["POS Cash Movement Report"] = {
	filters: get_pos_report_filters({ include_cashier: true, include_movement_type: true }),
};

{
 const settings = frappe.query_reports["POS Cash Movement Report"];
 const previous = settings.onload;
 settings.onload = async function(report) {
  window.retail_setup_pos_printing(report);
  if (previous) return previous.call(this, report);
 };
}
