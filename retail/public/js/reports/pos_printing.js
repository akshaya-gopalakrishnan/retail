// Install on the report instance; QueryReport is reused across report routes.
window.retail_setup_pos_printing = function (report) {
	if (report._retail_pos_printing) return;
	const supported = new Set(["POS Sales Summary", "POS Transaction Log", "POS Item-wise Sales", "POS Category Item Group Sales", "Item Group Sales Analysis", "POS Hourly Sales", "POS Return Report", "Cashier Wise Sales", "Counter Wise Sales", "Shift Closing Variance", "POS Payment Mode Summary", "POS Discount Report", "POS Price Override Report", "External POS Rate Audit", "POS Daily Closing Summary", "POS Cash Movement Report", "POS Invoice Profit", "POS Settlement Audit", "Counter Performance"]);
	const original_format = report.get_custom_format;
	const original_template = report.get_print_template;
	report.get_custom_format = async function (settings) {
		if (!supported.has(this.report_name)) return original_format.call(this, settings);
		const layout = await frappe.xcall("retail.report_print_formats.get_report_format", {
			report_name: this.report_name,
			format_name: settings.print_format || `${this.report_name} - A4`,
		});
		const bytes = new TextEncoder().encode(layout.css || "");
		const css = btoa(Array.from(bytes, byte => String.fromCharCode(byte)).join(""));
		return `<style>{%= new TextDecoder().decode(Uint8Array.from(atob("${css}"), byte => byte.charCodeAt(0))) %}</style>${layout.html}`;
	};
	report.get_print_template = function (settings, custom_format) {
		return supported.has(this.report_name) && custom_format
			? custom_format : original_template.call(this, settings, custom_format);
	};
	report._retail_pos_printing = true;
};
