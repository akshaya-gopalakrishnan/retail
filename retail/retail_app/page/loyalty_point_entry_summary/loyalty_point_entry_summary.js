frappe.pages['loyalty-point-entry-summary'].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({parent: wrapper, title: __('Loyalty Point Entry'), single_column: true});
    const controls = {};
    const form = $('<div class="retail-loyalty-balance-form"></div>').appendTo(page.body);
    $('<style>').text(`
        .retail-loyalty-balance-form { max-width: 860px; margin: 24px auto; padding: 24px;
            background: var(--fg-color); border: 1px solid var(--border-color); border-radius: var(--border-radius-lg); }
        .retail-loyalty-balance-form .loyalty-form-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 24px; }
        .retail-loyalty-balance-form .loyalty-program-balance { border-top: 1px solid var(--border-color); margin-top: 16px; padding-top: 20px; }
        @media (max-width: 640px) {
            .retail-loyalty-balance-form { margin: 12px; padding: 16px; }
            .retail-loyalty-balance-form .loyalty-form-fields { grid-template-columns: minmax(0, 1fr); }
        }
    `).appendTo(form);
    const filters = $('<div class="loyalty-form-fields"></div>').appendTo(form);
    const body = $('<div aria-live="polite"></div>').appendTo(form);
    let generation = 0;
    let ready = false;
    const refresh = async () => {
        if (!ready) return;
        const request = ++generation;
        const company = controls.company.get_value();
        const customer = controls.customer.get_value();
        if (!company || !customer) {
            body.text(__('Select a Company and Customer to view loyalty balances.'));
            return;
        }
        body.text(__('Loading…'));
        try {
            const {message: rows} = await frappe.call({method: 'retail.loyalty_summary.get_summary', args: {
                company, customer, loyalty_program: controls.loyalty_program.get_value(),
            }});
            if (request !== generation) return;
            body.empty();
            $('<p class="text-muted"></p>').text(__('Balances as of {0}', [frappe.datetime.str_to_user(frappe.datetime.get_today())])).appendTo(body);
            if (!rows?.length) {
                $('<p></p>').text(__('No loyalty points found.')).appendTo(body);
                return;
            }
            rows.forEach(row => {
                const section = $('<div class="loyalty-program-balance"></div>').appendTo(body);
                const fields = $('<div class="loyalty-form-fields"></div>').appendTo(section);
                for (const [fieldname, label, fieldtype, options] of [
                    ['customer_name', 'Customer Name', 'Data'],
                    ['loyalty_program', 'Loyalty Program', 'Link', 'Loyalty Program'],
                    ['earned_points', 'Earned Points', 'Int'], ['used_points', 'Used Points', 'Int'],
                    ['expired_points', 'Expired Points', 'Int'], ['available_points', 'Available Points', 'Int'],
                ]) {
                    const control = frappe.ui.form.make_control({
                        parent: $('<div></div>').appendTo(fields), render_input: true,
                        df: {fieldname, label: __(label), fieldtype, options, read_only: 1},
                    });
                    control.set_value(row[fieldname] ?? (fieldtype === 'Int' ? 0 : ''));
                }
            });
        } catch (error) {
            if (request === generation) body.text(__('Unable to load loyalty balances. Please try again.'));
        }
    };
    for (const [fieldname, label, options] of [
        ['company', 'Company', 'Company'], ['customer', 'Customer', 'Customer'],
        ['loyalty_program', 'Loyalty Program', 'Loyalty Program'],
    ]) {
        controls[fieldname] = frappe.ui.form.make_control({
            parent: $('<div></div>').appendTo(filters), render_input: true,
            df: {fieldname, label: __(label), fieldtype: 'Link', options,
                reqd: fieldname !== 'loyalty_program', onchange: refresh},
        });
    }
    controls.company.set_value(frappe.defaults.get_default('company') || '');
    page.set_primary_action(__('Refresh'), refresh);
    wrapper.refresh_loyalty_summary = refresh;
    ready = true;
    refresh();
};

frappe.pages['loyalty-point-entry-summary'].on_page_show = wrapper => wrapper.refresh_loyalty_summary?.();
