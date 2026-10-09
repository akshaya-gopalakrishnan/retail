frappe.provide("retail");

retail.show_invoice_search = function () {
	const esc = value => frappe.utils.escape_html(String(value ?? ""));
	const dialog = new frappe.ui.Dialog({
		title: __("Find Invoice"),
		size: "extra-large",
		fields: [
			{ fieldname: "bill_number", fieldtype: "Data", label: __("Bill Number"), description: __("Exact POS bill number or ERP invoice number. Keep leading zeros.") },
			{ fieldname: "invoice_type", fieldtype: "Select", label: __("Invoice Type"), options: "All\nPOS Invoice\nSales Invoice", default: "All" },
			{ fieldtype: "Section Break", label: __("Filter by Purchase Details") },
			{ fieldname: "from_datetime", fieldtype: "Datetime", label: __("From Date & Time") },
			{ fieldname: "customer", fieldtype: "Link", options: "Customer", label: __("Customer Name") },
			{ fieldname: "branch", fieldtype: "Link", options: "Branch", label: __("Branch Name"), onchange: () => dialog.set_value("counter", "") },
			{ fieldtype: "Column Break" },
			{ fieldname: "to_datetime", fieldtype: "Datetime", label: __("To Date & Time") },
			{ fieldname: "cashier", fieldtype: "Link", options: "Employee", label: __("Cashier Name") },
			{ fieldname: "counter", fieldtype: "Link", options: "POS Branch Counter", label: __("Counter Name"), get_query: () => ({ filters: dialog.get_value("branch") ? { branch: dialog.get_value("branch") } : {} }) },
			{ fieldtype: "Section Break" },
			{ fieldname: "results", fieldtype: "HTML" },
		],
		primary_action_label: __("Search"),
		primary_action: async () => {
			const filters = dialog.get_values();
			if (!filters) return;
			const wrapper = dialog.fields_dict.results.$wrapper;
			dialog.get_primary_btn().prop("disabled", true);
			wrapper.empty().text(__("Searching…"));
			try {
				const { message } = await frappe.call({ method: "retail.invoice_search.search_invoices", args: { filters } });
				const rows = message.invoices;
				wrapper.empty();
				if (!rows.length) {
					wrapper.text(__("No matching invoices found. Try changing the filters."));
					return;
				}
				const headers = ["Bill Number", "Invoice", "Type", "Sale Date & Time", "Customer", "Cashier", "Counter", "Branch", "Total", "Status", "Accounting Invoice", "POS Receipt"];
				const table = $(`<div style="overflow-x:auto"><table class="table table-bordered"><thead><tr>${headers.map(label => `<th>${esc(__(label))}</th>`).join("")}</tr></thead><tbody></tbody></table></div>`);
				for (const row of rows) {
					const tr = $("<tr>");
					const cell = value => $("<td>").text(value || "—").appendTo(tr);
					const link = (doctype, name) => {
						const td = $("<td>").appendTo(tr);
						if (!name) return td.text("—");
						$("<button type='button' class='btn btn-link btn-xs'>").text(name).on("click", () => {
							dialog.hide();
							frappe.set_route("Form", doctype, name);
						}).appendTo(td);
					};
					cell(row.pos_bill_no);
					link(row.invoice_type, row.name);
					cell(__(row.invoice_type));
					cell(`${row.posting_date} ${row.posting_time}`);
					cell(row.customer_name || row.customer);
					cell(row.cashier_name || row.pos_cashier_employee || row.pos_cashier);
					cell(row.counter_name || row.pos_counter);
					cell(row.pos_branch);
					$("<td>").html(format_currency(row.grand_total, row.currency)).appendTo(tr);
					cell(row.docstatus === 2 ? __("Cancelled") : row.docstatus === 0 ? __("Draft") : __(row.status));
					link("Sales Invoice", row.consolidated_invoice);
					link("POS Invoice", row.pos_invoice);
					tr.appendTo(table.find("tbody"));
				}
				wrapper.append(table);
				$("<p class='text-muted'>").text(message.has_more ? __("Showing the newest 100 matches. Narrow your filters to find older invoices.") : __("{0} invoice(s) found.", [rows.length])).appendTo(wrapper);
			} catch (error) {
				wrapper.empty().text(__("Search failed. Check your filters and permissions, then try again."));
			} finally {
				dialog.get_primary_btn().prop("disabled", false);
			}
		},
	});
	dialog.show();
	dialog.fields_dict.results.$wrapper.text(__("Enter a bill number or combine the filters above, then click Search. Times use the system time zone."));
};

(() => {
	function install_list_patch() {
		if (!frappe.views?.ListView) return;
		const prototype = frappe.views.ListView.prototype;
		if (prototype.retail_invoice_finder) return;
		prototype.retail_invoice_finder = true;
		const setup_view = prototype.setup_view;
		prototype.setup_view = function () {
			const result = setup_view.apply(this, arguments);
			if (["POS Invoice", "Sales Invoice"].includes(this.doctype)) {
				this.page.add_inner_button(__("Find Invoice"), retail.show_invoice_search);
			}
			return result;
		};
	}
	function install_form_handlers() {
		const prototype = frappe.ui?.form?.Form?.prototype;
		if (!prototype || !frappe.ui.form.on || prototype.retail_invoice_finder) return;
		prototype.retail_invoice_finder = true;
		for (const doctype of ["POS Invoice", "Sales Invoice"]) {
			frappe.ui.form.on(doctype, { refresh(frm) { frm.add_custom_button(__("Find Invoice"), retail.show_invoice_search); } });
		}
	}
	function install() {
		install_list_patch();
		install_form_handlers();
	}
	// Desk loads list/form bundles before Retail. Support early execution without fetching them.
	install();
	if ((!frappe.views?.ListView || !frappe.ui?.form?.Form) && !retail.invoice_finder_init_pending) {
		retail.invoice_finder_init_pending = true;
		$(function () {
			retail.invoice_finder_init_pending = false;
			install();
		});
	}
})();
