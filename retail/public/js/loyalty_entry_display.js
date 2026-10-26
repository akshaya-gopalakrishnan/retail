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
    settings.formatters ||= {};
    for (const [key] of columns) {
        settings.formatters[key] = value => `<span>${cint(value)}</span>`;
    }
    const previous = settings.onload;
    settings.onload = function (view) {
        previous?.(view);
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
})();
