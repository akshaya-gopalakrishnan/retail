(() => {
	const settings = frappe.listview_settings["POS Cashier Shift"] ||= {};
	settings.formatters ||= {};
    for (const field of ["opening_time", "closing_time"]) {
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
		if (view.retail_shift_columns) return;
		view.retail_shift_columns = true;
		view.retail_fit_columns = true;
		view.retail_list_activity_width = 70;
		const setup = view.setup_columns;
		view.setup_columns = function () {
			setup.call(this);
			for (const column of this.columns) {
				const field = column.df?.fieldname;
				const widths = {
					name: [100, 95], branch: [150, 90], cashier_name: [130, 90],
					status: [100, 90], business_date: [125, 105],
					opening_time: [185, 100], closing_time: [185, 100],
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
