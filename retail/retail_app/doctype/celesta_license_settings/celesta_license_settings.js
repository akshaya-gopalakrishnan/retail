frappe.ui.form.on("Celesta License Settings", {
    activate(frm) { return verify_license(frm, "activate"); },
    sync_verify(frm) { return verify_license(frm, "verify"); }
});

async function verify_license(frm, action) {
    if (frm.is_dirty() || !frm.doc.installation_id) await frm.save();
    await frappe.call({
        method: `retail.licensing.client.${action}`,
        freeze: true,
        freeze_message: __("Verifying license…")
    });
    await frm.reload_doc();
    frappe.show_alert({message: __("License response verified"), indicator: "green"});
}
