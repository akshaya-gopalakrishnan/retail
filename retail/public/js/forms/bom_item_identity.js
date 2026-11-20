/* Display current Item barcodes without rewriting existing BOM documents. */
(() => {
    async function refreshIdentity(frm) {
        const codes=[...new Set([frm.doc.item,...(frm.doc.items||[]).map(row=>row.item_code)].filter(Boolean))];
        if(!codes.length)return;
        const {message}=await frappe.call({method:'retail.bom_item_identity.get_item_identities',args:{items:codes}});
        const identities=new Map((message||[]).map(item=>[item.name,item]));
        const main=identities.get(frm.doc.item);
        if(main){frm.doc.custom_item_barcode=main.custom_barcode||'';frm.refresh_field('custom_item_barcode');}
        for(const row of frm.doc.items||[]){
            const item=identities.get(row.item_code);
            if(item)row.custom_item_barcode=item.custom_barcode||'';
        }
        frm.refresh_field('items');
    }
    frappe.ui.form.on('BOM',{
        refresh(frm){
            const grid=frm.fields_dict.items.grid;
            grid.update_docfield_property('item_name','in_list_view',1);
            window.retail?.scrollable_grid?.enable(frm,'items');
            return refreshIdentity(frm);
        },
        item:refreshIdentity,
    });
    frappe.ui.form.on('BOM Item',{item_code:refreshIdentity});
})();
