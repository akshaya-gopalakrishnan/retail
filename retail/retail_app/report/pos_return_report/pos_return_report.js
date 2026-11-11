frappe.query_reports["POS Return Report"] = {
	filters: get_pos_report_filters({ include_customer: true }),
};

{
 const settings = frappe.query_reports["POS Return Report"];
 const previous = settings.onload;
 settings.onload = async function(report) {
  window.retail_setup_pos_printing(report);
  if (previous) return previous.call(this, report);
 };
}
