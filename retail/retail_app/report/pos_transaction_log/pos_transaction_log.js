frappe.query_reports["POS Transaction Log"] = {
	filters: get_pos_report_filters({ include_status: true }),
};

{
 const settings = frappe.query_reports["POS Transaction Log"];
 const previous = settings.onload;
 settings.onload = async function(report) {
  window.retail_setup_pos_printing(report);
  if (previous) return previous.call(this, report);
 };
}
