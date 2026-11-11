frappe.query_reports["POS Category Item Group Sales"] = {
	formatter: (...args) => window.retail_profitability_formatter(...args),
	filters: get_pos_report_filters({ include_item_group: true }),
};

{
 const settings = frappe.query_reports["POS Category Item Group Sales"];
 const previous = settings.onload;
 settings.onload = async function(report) {
  window.retail_setup_pos_printing(report);
  if (previous) return previous.call(this, report);
 };
}
