// Restored/incomplete rows can reach Save without native item-account defaults.
// Resolve only missing accounts; never reload item prices, quantities or taxes.
frappe.ui.form.on("Sales Invoice", {
    async validate(frm) {
        const doc = frm.doc;
        if (Number(doc.docstatus || 0) !== 0 ||
            ["is_pos", "is_consolidated", "custom_is_van_sale"].some(field => Number(doc[field]))) return;
        const missing = (doc.items || []).filter(row => row.item_code && !row.income_account);
        if (!missing.length || !doc.company) return;
        const company = doc.company;
        const codes = new Map(missing.map(row => [row.name, row.item_code]));
        const result = await frappe.call({
            method: "retail.domains.sales.invoice_accounts.get_missing_income_accounts",
            type: "POST", args: {doc},
        });
        if (frm.doc !== doc || doc.company !== company || missing.some(row =>
            !doc.items.includes(row) || row.item_code !== codes.get(row.name))) {
            frappe.throw(__("The invoice changed while resolving account defaults. Please save again."));
        }
        const accounts = new Map((result.message || []).map(entry => [entry.name, entry]));
        for (const row of missing) {
            const entry = accounts.get(row.name);
            if (!row.income_account && entry?.item_code === row.item_code && entry.income_account) {
                await frappe.model.set_value(row.doctype, row.name, "income_account", entry.income_account);
            }
        }
    },
});
