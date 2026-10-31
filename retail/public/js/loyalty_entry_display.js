(() => {
    const columns = [
        ['earned_points', 'Earned Points'], ['used_points', 'Used Points'],
        ['expired_points', 'Expired Points'], ['available_points', 'Available Points'],
    ];
    frappe.ui.form.on('Loyalty Point Entry', {
        async refresh(frm) {
            if (frm.is_new()) return;
            const name = frm.doc.name;
            const { message } = await frappe.call('retail.loyalty_display.get_balances', { names: [name] });
            if (frm.doc.name !== name || !message?.[name]) return;
            const summary = columns.map(([key, label]) =>
                `${__(label)}: <b>${cint(message[name][key])}</b>`).join(' &nbsp; | &nbsp; ');
            // Frappe appends each headline; replace only our previous summary.
            frm.layout.message.find('.retail-loyalty-summary').closest('.form-message').remove();
            frm.dashboard.set_headline(`<span class="retail-loyalty-summary">${summary}</span>`);
        },
    });
    const settings = frappe.listview_settings['Loyalty Point Entry'] ||= {};
    settings.hide_name_filter = true;
    settings.formatters ||= {};
    for (const [key] of columns) {
        settings.formatters[key] = value => `<span>${cint(value)}</span>`;
    }
    const previous = settings.onload;
    settings.onload = function (view) {
        previous?.(view);
        setup_customer_name_filter(view);
        const setup = view.setup_columns;
        view.setup_columns = function () {
            setup.call(this);
            this.columns = this.columns.filter(column =>
                !['loyalty_points', 'restored_points', 'remaining_points'].includes(column.df?.fieldname));
            for (const [fieldname, label] of columns) {
                if (!this.columns.some(c => c.df?.fieldname === fieldname)) {
                    this.columns.push({ type: 'Field', df: { fieldname, label: __(label), fieldtype: 'Int' } });
                }
            }
        };
        view.setup_columns();
        view.render_header(true);
        const render = view.render;
        let request = 0;
        view.render = async function () {
            const sequence = ++request;
            const names = this.data.map(row => row.name);
            if (names.length) {
                const { message } = await frappe.call('retail.loyalty_display.get_balances', { names });
                if (sequence !== request) return;
                this.data.forEach(row => Object.assign(row, message?.[row.name] || {}));
            }
            return render.call(this);
        };
    };

    function setup_customer_name_filter(view) {
        const fieldname = 'custom_customer_name';
        const old = view.page.fields_dict[fieldname];
        const value = old?.get_value() || '';
        old?.$wrapper.remove();
        delete view.page.fields_dict[fieldname];
        const control = view.page.add_field({
            fieldname, fieldtype: 'Autocomplete', label: __('Customer Name'),
            condition: 'like', ignore_validation: true,
            onchange: () => view.filter_area.debounced_refresh_list_view(),
        }, view.filter_area.standard_filters_wrapper);
        control.set_input(value);
        let request = 0;
        const suggest = frappe.utils.debounce(async () => {
            const sequence = ++request;
            const term = control.$input.val() || '';
            try {
                const rows = await frappe.db.get_list('Customer', {
                    fields: ['name', 'customer_name'],
                    filters: [['customer_name', 'like', `%${term}%`]],
                    order_by: 'customer_name asc', limit: 30,
                });
                if (sequence !== request || term !== control.$input.val()) return;
                control.set_data(rows.map(row => ({
                    value: row.customer_name,
                    label: frappe.utils.escape_html(row.customer_name),
                    description: frappe.utils.escape_html(row.name),
                })));
                if (control.$input.is(':focus')) control.awesomplete.evaluate();
            } catch (error) {
                if (sequence === request) control.set_data([]);
            }
        }, 200);
        control.$input.on('input focus', suggest);
    }
})();
