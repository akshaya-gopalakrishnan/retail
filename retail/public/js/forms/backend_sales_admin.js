(() => {
    const applies = frm => !["is_pos", "is_consolidated", "custom_is_van_sale"].some(f => Number(frm.doc[f]));
    // Mirror the server's direct-operation privilege to avoid an approval RPC on
    // every Save/Submit. The server still checks the current assigned roles.
    const directOperations = () => frappe.session.user === "Administrator" ||
        ["Admin", "Customer Administrator"].some(role => frappe.user.has_role(role));
    const fields = new Set(["rate", "price_list_rate", "discount_percentage", "discount_amount",
        "additional_discount_percentage", "margin_type", "margin_rate_or_amount", "custom_foc_qty",
        "custom_rate_including_vat", "custom_amount_including_vat", "ignore_pricing_rule", "is_return", "return_against"]);
    const value = v => typeof v === "number" ? Math.round(v * 1e6) / 1e6 : (v ?? "");
    function rememberApprovedValues(frm) {
        const values = new Map();
        for (const field of fields) values.set(`:${field}`, value(frm.doc[field]));
        for (const row of frm.doc.items || []) {
            for (const field of fields) values.set(`${row.name}:${field}`, value(row[field]));
        }
        frm.__retailApprovedValues = values;
        frm.__retailUnapprovedEdit = false;
    }
    function approve(frm) {
        if (frm.__retailApprovalPending) return frm.__retailApprovalPending;
        frm.__retailApprovalPending = new Promise((resolve, reject) => {
            let accepted = false;
            const dialog = new frappe.ui.Dialog({
                title: __("Approve Price, Discount or Return"),
                fields: [
                    {fieldname: "user", fieldtype: "Link", options: "User", label: __("User ID"), reqd: 1,
                        only_select: 1, get_query: () => ({query: "retail.backend_sales_admin.approver_query"})},
                    {fieldname: "password", fieldtype: "Password", label: __("Password"), reqd: 1},
                ],
                primary_action_label: __("Approve"),
                async primary_action(values) {
                    dialog.disable_primary_action();
                    try {
                        const result = await frappe.call({method: "retail.backend_sales_admin.authorize",
                            freeze: true, freeze_message: __("Verifying approval…"),
                            type: "POST", args: {doc: frm.doc, user: values.user, password: values.password}});
                        frm.__retailSalesApprovals = [...(frm.__retailSalesApprovals || []), result.message].slice(-100);
                        frm.doc._retail_sales_approval = frm.__retailSalesApprovals;
                        rememberApprovedValues(frm);
                        frm.__retailApprovalGeneration = (frm.__retailApprovalGeneration || 0) + 1;
                        accepted = true;
                        dialog.set_value("password", "");
                        dialog.hide();
                        resolve();
                    } catch (error) {
                        dialog.set_value("password", "");
                    } finally {
                        dialog.enable_primary_action();
                    }
                },
                onhide() {
                    dialog.set_value("password", "");
                    if (!accepted) reject(new Error(__("Approval cancelled. The invoice cannot be saved with unapproved changes.")));
                },
            });
            dialog.show();
        }).finally(() => { frm.__retailApprovalPending = null; });
        return frm.__retailApprovalPending;
    }
    async function ensure(frm, saving = false) {
        clearTimeout(frm.__retailApprovalTimer);
        if (directOperations()) return;
        if (!applies(frm) || Number(frm.doc.docstatus) !== 0) return;
        if (frm.__retailApprovalPending) await frm.__retailApprovalPending;
        clearTimeout(frm.__retailApprovalTimer);
        frm.doc._retail_sales_approval = frm.__retailSalesApprovals || [];
        // Completed operation approvals are sufficient at Save. The native Save
        // request still validates every token and approved price on the server.
        if (saving && frm.doc._retail_sales_approval.length && !frm.__retailUnapprovedEdit) return;
        const generation = frm.__retailApprovalGeneration || 0;
        const result = await frappe.call({method: "retail.backend_sales_admin.requires_approval", type: "POST",
            freeze: saving, freeze_message: __("Checking invoice approval…"), args: {doc: frm.doc}});
        // An older lookup must not reopen approval after a newer one completed.
        if (generation !== (frm.__retailApprovalGeneration || 0)) return;
        if (result.message) await approve(frm);
    }
    frappe.ui.form.on("Sales Invoice", {
        refresh(frm) {
            if (!applies(frm)) return;
            if (directOperations()) {
                clearTimeout(frm.__retailApprovalTimer);
                $(frm.wrapper).off("change.retailApproval");
                return;
            }
            // Listen only to user edits; native pricing and tax calculations keep their handlers.
            $(frm.wrapper).off("change.retailApproval").on("change.retailApproval", "input, select", function (event) {
                const field = this.dataset.fieldname || this.closest?.("[data-fieldname]")?.dataset.fieldname;
                if (!event.originalEvent || !fields.has(field) || Number(frm.doc.docstatus) !== 0) return;
                const rowName = this.closest?.(".grid-row")?.dataset.name || "";
                const row = rowName ? frm.doc.items?.find(row => row.name === rowName) : frm.doc;
                const key = `${rowName}:${field}`;
                // A native input change can bubble before its async model handler
                // finishes. Compare the entered value, not the previous row value.
                const entered = this.type === "checkbox" ? Number(this.checked) :
                    this.value === undefined ? value(row?.[field]) :
                    ["return_against", "margin_type"].includes(field) ? this.value :
                    value(Number(String(this.value).replace(/,/g, "")));
                if (row && frm.__retailApprovedValues?.has(key) &&
                    frm.__retailApprovedValues.get(key) === entered) return;
                frm.__retailUnapprovedEdit = true;
                // Keep earlier row approvals; the server compares approved prices with current values.
                clearTimeout(frm.__retailApprovalTimer);
                frm.__retailApprovalTimer = setTimeout(async () => {
                    await frappe.after_ajax();
                    ensure(frm).catch(error => frappe.show_alert({message: error.message, indicator: "orange"}));
                }, 150);
            });
            if (frm.is_new() && Number(frm.doc.is_return)) {
                setTimeout(() => ensure(frm).catch(error => frappe.show_alert({message: error.message, indicator: "orange"})), 0);
            }
        },
        async before_save(frm) {
            window.retail?.transaction_items?.releaseSaveWait?.(frm);
            await ensure(frm, true);
        },
        async before_submit(frm) {
            window.retail?.transaction_items?.releaseSaveWait?.(frm);
            await ensure(frm, true);
        },
        after_save(frm) {
            if (frm.__retailSalesApprovals?.length && !frm.__retailUnapprovedEdit) rememberApprovedValues(frm);
        },
    });
})();
