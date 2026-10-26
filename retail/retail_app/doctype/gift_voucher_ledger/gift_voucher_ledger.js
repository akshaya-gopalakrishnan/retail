frappe.ui.form.on('Gift Voucher Ledger', {
    refresh(frm) {
        if (!frm.doc.voucher_card_batch) return;
        frm.disable_save();
        if (frm.doc.card_archived) frm.set_intro(__('Archived card. History is retained.'), 'orange');
        else if (frm.doc.card_blocked) frm.set_intro(__('Blocked card. Redemption is disabled.'), 'red');
        frm.add_custom_button(__('Transaction History'), () => frappe.set_route('List', 'Voucher Card Transaction', {voucher: frm.doc.name}));
        for (const action of ['Activate', 'Block', 'Archive']) {
            frm.add_custom_button(__(action), async () => {
                await frappe.call({method: 'retail.voucher_cards.manage_cards', args: {
                    batch: frm.doc.voucher_card_batch, cards: [frm.doc.name], action
                }, freeze: true});
                frm.reload_doc();
            }, __('Card Actions'));
        }
    }
});
