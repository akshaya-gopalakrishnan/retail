// Hydrate the standard model cache before Workspace starts constructing widgets.
(() => {
	function install() {
		const prototype = frappe.views?.Workspace?.prototype;
		if (!prototype || prototype.get_data.retail_widget_preload) return;
		const get_data = prototype.get_data;
		function with_definitions(page) {
			return get_data.apply(this, arguments).then((result) => {
				if (page.name === "Business Home") {
					for (const definition of this.page_data?.retail_widget_definitions || []) {
						try {
							frappe.model.sync(definition);
						} catch (error) {
							// Remove partial entries so with_doc takes its normal fallback.
							for (const doc of definition.docs || []) {
								frappe.model.clear_doc(doc.doctype, doc.name);
							}
						}
					}
					for (const [source, config] of Object.entries(this.page_data?.retail_chart_source_configs || {})) {
						if (frappe.dashboards?.chart_sources?.[source]) continue;
						try {
							frappe.dom.eval(config);
						} catch (error) {
							// Failed configurations follow the normal widget request path.
							if (frappe.dashboards?.chart_sources) delete frappe.dashboards.chart_sources[source];
						}
					}
					delete this.page_data?.retail_widget_definitions;
					delete this.page_data?.retail_chart_source_configs;
				}
				return result;
			});
		}
		with_definitions.retail_widget_preload = true;
		prototype.get_data = with_definitions;
	}
	install();
	$(document).on("startup", install);
})();
