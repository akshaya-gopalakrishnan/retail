frappe.query_reports["POS Sales Summary"] = {
	formatter: (...args) => window.retail_profitability_formatter(...args),
	filters: get_pos_report_filters(),
};

{
 const settings = frappe.query_reports["POS Sales Summary"];
 const previous = settings.onload;
 settings.onload = async function(report) {
  window.retail_setup_pos_printing(report);
  if (previous) return previous.call(this, report);
 };
}
