(() => {
	const settings = frappe.listview_settings["POS Counter Session"] ||= {};
	settings.formatters ||= {};
    for (const field of ["started_at", "ended_at"]) {
        settings.formatters[field] = function (value, df, doc) {
            if (!value) return "";
            const formatted = frappe.format(value, df, null, doc);
            const [date, ...time] = formatted.split(" ");
            const escape = frappe.utils.escape_html;
            return `<a class="filterable" data-filter="${field},=,${escape(value)}"
                title="${escape(formatted)}" style="display:inline-block;max-width:100%;white-space:normal;line-height:1.35">
                <span style="white-space:nowrap">${escape(date)}</span>
                <span style="white-space:nowrap">${escape(time.join(" "))}</span></a>`;
        };
    }
    const onload = settings.onload;
	settings.onload = function (view) {
		onload?.call(this, view);
		if (view.retail_session_columns) return;
		view.retail_session_columns = true;
		view.retail_fit_columns = true;
		view.retail_list_activity_width = 70;
		const setup = view.setup_columns;
		view.setup_columns = function () {
			setup.call(this);
			for (const column of this.columns) {
				const field = column.df?.fieldname;
				const widths = {
					name: [100, 90], branch: [130, 70], counter_code: [125, 70], cashier_shift: [110, 70],
					status: [100, 75], business_date: [125, 100],
					started_at: [185, 90], ended_at: [185, 90],
				};
				if (widths[field]) {
					[column.retail_compact_width, column.retail_min_width] = widths[field];
				}
			}
		};
		view.setup_columns();
		view.render_header(true);
	};
})();
