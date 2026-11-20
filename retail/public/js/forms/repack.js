/* Multiple BOM controls live in Stock Entry's existing BOM Info section. */
(() => {
    const enabled = (frm) => frm.doc.purpose === "Repack" && !!frm.doc.custom_multiple_boms;
    function refresh(frm) {
        const multi = enabled(frm);
        // Core refresh handlers also toggle these fields; use metadata conditions
        // while active and restore each original condition when leaving the mode.
        for (const name of ["from_bom", "bom_no", "fg_completed_qty", "use_multi_level_bom", "get_items"]) {
            const field = frm.fields_dict[name];
            if (!field) continue;
            if (!("retail_repack_depends_on" in field.df)) {
                field.df.retail_repack_depends_on = field.df.depends_on || "";
            }
            frm.set_df_property(name, "depends_on", multi ? "eval:false" : field.df.retail_repack_depends_on);
        }
        if (multi) {
            frm.remove_custom_button(__("Bill of Materials"), __("Get Items From"));
        }
        frm.set_df_property("custom_get_repack_items", "hidden", frm.doc.docstatus !== 0);
        // Use the width of BOM Info rather than squeezing the table into its
        // original right-hand column. Restore the native columns in normal mode.
        const section = frm.layout.sections_dict.bom_info_section;
        if (section && !("retail_repack_collapsible_depends_on" in section.df)) {
            section.df.retail_repack_collapsible_depends_on = section.df.collapsible_depends_on || "";
        }
        if (section) section.df.collapsible_depends_on = multi ? "custom_multiple_boms" : section.df.retail_repack_collapsible_depends_on;
        if (multi) section?.collapse(false);
        for (const column of section?.columns || []) {
            column.wrapper.css({flex: multi ? "0 0 100%" : "", maxWidth: multi ? "100%" : ""});
        }
    }
    async function load(frm) {
        const run = async () => {
            await frm.call({doc: frm.doc, method: "get_items", freeze: true,
                freeze_message: __("Loading Repack BOMs...")});
            frm.refresh_fields();
            frm.dirty();
        };
        if ((frm.doc.items || []).some(r => r.item_code)) {
            return frappe.confirm(__("Rebuild the BOM-generated items? Item quantities, batches and serial selections will be replaced."), run);
        }
        return run();
    }
    frappe.ui.form.on("Stock Entry", {
        setup(frm) {
            frm.set_query("bom_no", "custom_repack_boms", () => ({filters: {
                company: frm.doc.company, docstatus: 1, is_active: 1,
            }}));
            for (const field of ["source_warehouse", "target_warehouse"]) {
                frm.set_query(field, "custom_repack_boms", () => ({filters: {
                    company: frm.doc.company, is_group: 0, disabled: 0,
                }}));
            }
            frm.set_query("custom_repack_cost_account", () => ({filters: {
                company: frm.doc.company, root_type: "Expense", is_group: 0, disabled: 0,
                account_currency: frappe.get_doc(":Company", frm.doc.company)?.default_currency,
            }}));
        },
        refresh,
        purpose: refresh,
        async custom_multiple_boms(frm) {
            if (enabled(frm)) {
                // Clearing the single-BOM controls must not invoke core's
                // fg_completed_qty handler, which immediately fetches one BOM.
                Object.assign(frm.doc, {from_bom: 0, bom_no: "", fg_completed_qty: 0,
                    process_loss_qty: 0, process_loss_percentage: 0});
                frm.refresh_fields(["from_bom", "bom_no", "fg_completed_qty",
                    "process_loss_qty", "process_loss_percentage"]);
            }
            refresh(frm);
        },
        custom_get_repack_items: load,
    });
    frappe.ui.form.on("Retail Repack BOM", {
        async bom_no(frm, cdt, cdn) {
            const row = locals[cdt][cdn];
            const selected = row.bom_no;
            const result = selected ? await frappe.db.get_value("BOM", selected, ["item", "uom"]) : null;
            if (row.bom_no !== selected) return;
            const item = result?.message?.item;
            const stock = item ? await frappe.db.get_value("Item", item, "stock_uom") : null;
            if (row.bom_no !== selected) return;
            await frappe.model.set_value(cdt, cdn, {
                finished_item: item || "", stock_uom: stock?.message?.stock_uom || "",
            });
        },
    });
})();
