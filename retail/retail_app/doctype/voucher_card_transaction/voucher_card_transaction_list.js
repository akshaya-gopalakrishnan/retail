frappe.listview_settings['Voucher Card Transaction'] = {
    onload(listview) {
        listview.page.add_inner_button(__('Cards / Current Status'), () => {
            const filters = {};
            for (const filter of listview.filter_area.get()) {
                if (filter[1] === 'batch' && filter[2] === '=') filters.voucher_card_batch = filter[3];
                if (filter[1] === 'voucher' && filter[2] === '=') filters.name = filter[3];
            }
            frappe.set_route('List', 'Gift Voucher Ledger', filters);
        });
    }
};
