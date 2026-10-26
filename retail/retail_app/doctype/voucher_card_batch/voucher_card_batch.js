frappe.ui.form.on('Voucher Card Batch', {
    onload(frm) {
        if (frm.is_new() && !frm.doc.apply_promotion_to) frm.set_value('apply_promotion_to', 'Item');
    },
    refresh(frm) {
        retail_voucher_card_dropdown_direction(frm);
        retail_voucher_card_eligibility_columns(frm);
        frm.add_custom_button(__('Print Format'), async () => {
            if (frm.is_new() || frm.is_dirty()) await frm.save();
            await retail_voucher_card_print_format(frm);
        });
        if (frm.is_new()) return;
        frm.add_custom_button(__('Print'), async () => {
            const preview = window.open('', '_blank');
            try {
                if (frm.is_dirty()) await frm.save();
                if (frm.is_dirty()) { preview?.close(); return; }
                const format = frm.doc.voucher_print_format || 'Voucher Cards - A4';
                const url = '/printview?doctype=Voucher%20Card%20Batch&name=' + encodeURIComponent(frm.doc.name)
                    + '&format=' + encodeURIComponent(format) + '&no_letterhead=1';
                if (preview) preview.location.href = url;
                else window.open(url, '_blank');
            } catch (error) { preview?.close(); throw error; }
        });
        frm.set_intro(__('Promotional voucher cards use the existing voucher discount flow. Paid prepaid gift-card issuance is not supported here.'), 'blue');
        if (frm.doc.generation_status !== 'Complete') {
            frm.add_custom_button(__(frm.doc.generation_status === 'Draft' ? 'Generate Cards' : 'Resume Generation'), async () => {
                if (frm.is_dirty()) await frm.save();
                await frappe.call({method: 'retail.voucher_cards.generate_cards', args: {batch: frm.doc.name}, freeze: true});
                frm.reload_doc();
            });
        }
        frm.add_custom_button(__('Cards / Current Status'), () => frappe.set_route('List', 'Gift Voucher Ledger', {
            voucher_card_batch: frm.doc.name, card_archived: 0
        }));
        frm.add_custom_button(__('Transaction History'), () => frappe.set_route('List', 'Voucher Card Transaction', {batch: frm.doc.name}), __('History'));
        if (['Queued', 'Generating'].includes(frm.doc.generation_status)) {
            frm.dashboard.show_progress(__('Cards generated'), 100 * (frm.doc.generated_count || 0) / frm.doc.card_count,
                `${frm.doc.generated_count || 0} / ${frm.doc.card_count}`);
            frm.add_custom_button(__('Refresh Progress'), () => frm.reload_doc());
        }
        if (!frm._voucher_progress_handler) {
            frm._voucher_progress_handler = data => {
                if (data.batch === frm.doc.name && !frm.is_dirty()) frm.reload_doc();
            };
            frappe.realtime.on('voucher_card_progress', frm._voucher_progress_handler);
        }
    },
    apply_promotion_to(frm) {
        const target = {Item: 'item_code', Brand: 'brand', Category: 'item_group'}[frm.doc.apply_promotion_to];
        const fields = ['item_code', 'brand', 'item_group'];
        if (target && (frm.doc.restrictions || []).some(row => fields.some(field => field !== target && row[field]))) {
            frm.set_value('apply_promotion_to', frm._voucher_eligibility_scope || '');
            frappe.msgprint(__('Remove existing eligibility rows for other types before changing Apply Promotion To.'));
            return;
        }
        retail_voucher_card_eligibility_columns(frm);
    },
    all_products(frm) {
        retail_voucher_card_eligibility_columns(frm);
    },
    company(frm) {
        if (frm.doc.company) frappe.db.get_value('Company', frm.doc.company, 'default_currency').then(r => frm.set_value('currency', r.message.default_currency));
    }
});

function retail_voucher_card_dropdown_direction(frm) {
    $(frm.wrapper).addClass('voucher-card-batch-form');
    if ($(frm.wrapper).find('style[data-voucher-dropdown]').length) return;
    $('<style data-voucher-dropdown>')
        .text(`
            .voucher-card-batch-form [data-fieldname="restrictions"] .awesomplete > [role="listbox"] {
                top: auto;
                bottom: 100%;
                margin-bottom: 4px;
                max-height: min(40vh, 240px);
                overflow-y: auto;
            }
        `)
        .appendTo(frm.wrapper);
}

function retail_voucher_card_eligibility_columns(frm) {
    const fields = {Item: 'item_code', Brand: 'brand', Category: 'item_group'};
    const used = Object.entries(fields).filter(([, field]) => (frm.doc.restrictions || []).some(row => row[field]));
    // Infer older batches without rewriting their eligibility or saved document.
    const scope = frm.doc.apply_promotion_to || (used.length === 1 ? used[0][0] : (used.length ? '' : 'Item'));
    const target = fields[scope];
    frm._voucher_eligibility_scope = frm.doc.apply_promotion_to || '';
    const grid = frm.fields_dict.restrictions.grid;
    for (const field of Object.values(fields)) {
        grid.update_docfield_property(field, 'hidden', target && field !== target ? 1 : 0);
    }
    grid.reset_grid();
}


async function retail_voucher_card_print_format(frm) {
    await frappe.model.with_doctype('Print Format');
    const can_edit = frappe.perm.has_perm('Print Format', 0, 'write');
    let dialog, loaded;
    const load_design = async () => {
        if (!dialog) return;
        const name = dialog.get_value('print_format');
        if (!name) return;
        const format = await frappe.db.get_doc('Print Format', name);
        if (dialog.get_value('print_format') !== name) return;
        loaded = format;
        await dialog.set_values({design_html: format.html || '', design_css: format.css || ''});
    };
    const save = async () => {
        const values = dialog.get_values();
        if (!values) return false;
        if (!loaded || loaded.name !== values.print_format) {
            frappe.throw(__('Wait for the selected print format to load.'));
        }
        if ((values.design_html || '') !== (loaded.html || '') || (values.design_css || '') !== (loaded.css || '')) {
            await frappe.call({method: 'frappe.client.set_value', args: {
                doctype: 'Print Format', name: loaded.name,
                fieldname: {html: values.design_html || '', css: values.design_css || ''}
            }, freeze: true});
            loaded.html = values.design_html || '';
            loaded.css = values.design_css || '';
        }
        await frm.set_value({...Object.fromEntries(['logo', 'terms', 'print_from', 'print_to', 'label_width', 'label_height']
            .map(field => [field, values[field]])), voucher_print_format: values.print_format});
        await frm.save();
        return !frm.is_dirty();
    };
    dialog = new frappe.ui.Dialog({
        title: __('Voucher Card Print Format'), size: 'extra-large',
        fields: [
            {fieldname: 'print_format', fieldtype: 'Link', label: __('Print Format'), options: 'Print Format',
                reqd: 1, default: frm.doc.voucher_print_format || 'Voucher Cards - A4', onchange: load_design,
                get_query: () => ({filters: {doc_type: 'Voucher Card Batch', standard: 'No', disabled: 0}})},
            {fieldtype: 'Section Break', label: __('Printing')},
            {fieldname: 'logo', fieldtype: 'Attach Image', label: __('Logo'), default: frm.doc.logo,
                options: {doctype: frm.doctype, docname: frm.doc.name, fieldname: 'logo'}},
            {fieldname: 'terms', fieldtype: 'Small Text', label: __('Terms'), default: frm.doc.terms},
            {fieldtype: 'Column Break'},
            {fieldname: 'print_from', fieldtype: 'Int', label: __('Print from Card Number'), reqd: 1, default: frm.doc.print_from},
            {fieldname: 'print_to', fieldtype: 'Int', label: __('Print to Card Number'), reqd: 1, default: frm.doc.print_to,
                description: __('Print up to 500 cards per range.')},
            {fieldname: 'label_width', fieldtype: 'Float', label: __('Label Width (mm)'), reqd: 1, default: frm.doc.label_width},
            {fieldname: 'label_height', fieldtype: 'Float', label: __('Label Height (mm)'), reqd: 1, default: frm.doc.label_height},
            {fieldtype: 'Section Break', label: __('HTML'),
                description: __('HTML and CSS belong to the selected print format and apply to all batches using that format.')},
            {fieldname: 'design_html', fieldtype: 'Code', label: __('HTML'), options: 'HTML', read_only: !can_edit},
            {fieldtype: 'Section Break', label: __('CSS')},
            {fieldname: 'design_css', fieldtype: 'Code', label: __('CSS'), options: 'CSS', read_only: !can_edit}
        ],
        primary_action_label: __('Save'),
        primary_action: async () => { if (await save()) dialog.hide(); },
        secondary_action_label: __('Save & Preview'),
        secondary_action: async () => {
            const preview = window.open('', '_blank');
            try {
                if (!await save()) { preview?.close(); return; }
                const url = '/printview?doctype=Voucher%20Card%20Batch&name=' + encodeURIComponent(frm.doc.name)
                    + '&format=' + encodeURIComponent(dialog.get_value('print_format')) + '&no_letterhead=1';
                if (preview) preview.location.href = url;
                else window.open(url, '_blank');
            } catch (error) { preview?.close(); throw error; }
        }
    });
    dialog.show();
    await load_design();
}
