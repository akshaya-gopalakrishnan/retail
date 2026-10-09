(function () {
    frappe.provide("retail.zebra");
    let loading;
    async function openBulkPrintDialog(opts) {
        loading ||= frappe.require("retail_labels.bundle.js");
        await loading;
        if (retail.zebra.open_bulk_print_dialog === openBulkPrintDialog) {
            loading = null;
            throw new Error("Unable to load label printing. Please try again.");
        }
        return retail.zebra.open_bulk_print_dialog(opts);
    }
    retail.zebra.open_bulk_print_dialog = openBulkPrintDialog;
})();
