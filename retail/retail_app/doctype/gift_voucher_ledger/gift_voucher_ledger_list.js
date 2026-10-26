frappe.listview_settings['Gift Voucher Ledger'] = {
    onload(listview) {
        for (const [label, kind] of [['Cards', 'Voucher Card'], ['Vouchers', 'Promotion Voucher'], ['All', null]]) {
            listview.page.add_inner_button(__(label), async () => {
                await listview.filter_area.remove('voucher_kind');
                await listview.filter_area.remove('voucher_card_batch');
                if (kind) await listview.filter_area.add([['Gift Voucher Ledger', 'voucher_kind', '=', kind]]);
                listview.refresh();
            }, __('Show'));
        }
        for (const action of ['Activate', 'Block', 'Archive']) {
            listview.page.add_actions_menu_item(__(action + ' Selected Cards'), async () => {
                const rows = listview.get_checked_items();
                if (!rows.length || rows.some(r => !r.voucher_card_batch)) {
                    frappe.msgprint(__('Select voucher cards from one batch.'));
                    return;
                }
                const batch = rows[0].voucher_card_batch;
                if (rows.some(r => r.voucher_card_batch !== batch)) {
                    frappe.msgprint(__('Select cards from one batch at a time.'));
                    return;
                }
                await frappe.call({method: 'retail.voucher_cards.manage_cards', args: {
                    batch, cards: rows.map(r => r.name), action
                }, freeze: true});
                listview.refresh();
            });
        }
    },
    get_indicator(doc) {
        if (!doc.voucher_card_batch) return;
        if (doc.card_archived) return [__('Archived'), 'gray', 'card_archived,=,1'];
        if (doc.card_blocked) return [__('Blocked'), 'red', 'card_blocked,=,1'];
        const today = frappe.datetime.get_today();
        if (doc.expiry_date && doc.expiry_date < today) return [__('Expired'), 'red', 'expiry_date,<,' + today];
        if (doc.status === 'Draft') return [__('Draft'), 'gray', 'status,=,Draft'];
        if (doc.valid_from && doc.valid_from > today) return [__('Not Yet Valid'), 'orange', 'valid_from,>,' + today];
        const states = {Unused: ['Active', 'green'], 'Partially Used': ['Partially Used', 'orange'], Redeemed: ['Fully Used', 'gray']};
        const state = states[doc.status];
        if (state) return [__(state[0]), state[1], 'status,=,' + doc.status];
    },
    add_fields: ['voucher_kind', 'voucher_card_batch', 'card_archived', 'card_blocked', 'valid_from', 'expiry_date', 'status', 'balance_amount'],
};
