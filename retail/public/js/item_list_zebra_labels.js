frappe.listview_settings["Item"] = frappe.listview_settings["Item"] || {};

frappe.listview_settings["Item"].onload = function (listview) {
	// Hidden for now. Uncomment if bulk Zebra label printing is needed again.
	// listview.page.add_inner_button(__("Print Zebra Labels"), () => {
	// 	retail.zebra.open_bulk_print_dialog({
	// 		source: "item_list",
	// 		source_label: __("Item List"),
	// 		get_selected_items: () => listview.get_checked_items(true),
	// 		get_filters: () => listview.get_filters_for_args(),
	// 	});
	// });
};
