frappe.ui.form.on("Zebra Label Format", {
	refresh(frm) {
		frm.add_custom_button(__("Preview"), () => run_zebra_action(frm, () => preview_zebra_label(frm))).addClass("btn-primary");
		frm.add_custom_button(__("Print Test"), () => run_zebra_action(frm, () => print_zebra_label(frm)));
		frm.add_custom_button(__("Set as Default"), () => run_zebra_action(frm, () => set_zebra_label_default(frm)));
		set_printer_fields(frm);
		add_system_printer_button(frm);
		render_placeholder_help(frm);
	},
	print_method(frm) {
		set_printer_fields(frm);
	},
	sample_item(frm) {
		if (!frm.is_new() && frm.doc.sample_item) {
			run_zebra_action(frm, () => preview_zebra_label(frm, { quiet: true }));
		}
	},
});

async function run_zebra_action(frm, action) {
	try {
		await action();
	} catch (error) {
		console.error(error);
		frappe.msgprint({
			title: __("Zebra Label Error"),
			message: error.message || error,
			indicator: "red",
		});
	}
}

async function ensure_zebra_doc_saved(frm) {
	if (frm.is_new()) {
		throw new Error(__("Please save this Zebra Label Format before previewing or printing."));
	}
	if (frm.is_dirty()) {
		await frm.save();
	}
	if (frm.is_dirty()) {
		throw new Error(__("Please fix the validation errors and save this Zebra Label Format first."));
	}
}

async function preview_zebra_label(frm, opts = {}) {
	await ensure_zebra_doc_saved(frm);
	const { message } = await frappe.call({
		method: "retail.retail_app.doctype.zebra_label_format.zebra_label_format.render_label",
		args: {
			label_format: frm.doc.name,
			item: frm.doc.sample_item,
		},
	});
	frm.fields_dict.preview_html.$wrapper.html(message.preview_html);
	set_rendered_zpl_preview(frm, message.zpl);
	scroll_to_zebra_preview(frm);
	if (!opts.quiet) {
		frappe.show_alert({ message: __("Preview updated"), indicator: "green" });
	}
}

async function print_zebra_label(frm) {
	const print_method = frm.doc.print_method || "Network Printer";
	if (print_method === "Network Printer" && !frm.doc.printer_ip) {
		frappe.msgprint({
			title: __("Printer IP Required"),
			message: __("Set Printer IP on this Zebra Label Format before using Print Test."),
			indicator: "orange",
		});
		return;
	}
	if (print_method === "System Printer" && !frm.doc.printer_name) {
		frappe.msgprint({
			title: __("Printer Name Required"),
			message: __("Set Printer Name on this Zebra Label Format before using Print Test."),
			indicator: "orange",
		});
		return;
	}
	await ensure_zebra_doc_saved(frm);
	const { message } = await frappe.call({
		method: "retail.retail_app.doctype.zebra_label_format.zebra_label_format.print_label",
		args: {
			label_format: frm.doc.name,
			item: frm.doc.sample_item,
		},
		freeze: true,
		freeze_message: __("Sending to Zebra printer"),
	});
	frappe.show_alert({ message, indicator: "green" });
}

function set_printer_fields(frm) {
	const print_method = frm.doc.print_method || "Network Printer";
	const is_network = print_method === "Network Printer";

	frm.toggle_reqd("printer_ip", is_network);
	frm.toggle_reqd("printer_port", is_network);
	frm.toggle_display("printer_ip", is_network);
	frm.toggle_display("printer_port", is_network);
	frm.toggle_reqd("printer_name", !is_network);
	frm.toggle_display("printer_name", !is_network);
}

function add_system_printer_button(frm) {
	if ((frm.doc.print_method || "Network Printer") !== "System Printer") return;
	frm.add_custom_button(__("Show System Printers"), () => run_zebra_action(frm, () => show_system_printers()));
}

async function show_system_printers() {
	const { message } = await frappe.call({
		method: "retail.retail_app.doctype.zebra_label_format.zebra_label_format.get_system_printers",
	});
	const printers = message || [];
	frappe.msgprint({
		title: __("System Printers"),
		message: printers.length ? printers.map((printer) => `<div><code>${frappe.utils.escape_html(printer)}</code></div>`).join("") : __("No system printers found on the ERPNext host."),
		indicator: printers.length ? "green" : "orange",
	});
}

async function set_zebra_label_default(frm) {
	await ensure_zebra_doc_saved(frm);
	await frappe.call({
		method: "retail.retail_app.doctype.zebra_label_format.zebra_label_format.set_default",
		args: { label_format: frm.doc.name },
	});
	frm.reload_doc();
	frappe.show_alert({ message: __("Default label format updated"), indicator: "green" });
}

function render_placeholder_help(frm) {
	if (frm.__zebra_placeholder_help_rendered) return;
	if (frm.fields_dict.zpl_template?.$wrapper?.find(".zebra-placeholder-help").length) return;
	frm.__zebra_placeholder_help_rendered = true;
	const help = `
		<div class="small text-muted zebra-placeholder-help" style="margin-bottom: 10px;">
			Use placeholders:
			<code>{productnameenglish}</code>
			<code>{productnameenglish1}</code>
			<code>{barcode}</code>
			<code>{barcodetext}</code>
			<code>{curr}</code>
			<code>{price}</code>
			<code>{copies}</code>
		</div>
	`;
	frm.fields_dict.zpl_template?.$wrapper?.prepend(help);
}

function set_rendered_zpl_preview(frm, zpl) {
	const field = frm.fields_dict.rendered_zpl;
	frm.doc.rendered_zpl = zpl;

	if (field?.editor?.setValue) {
		field.editor.setValue(zpl);
		return;
	}

	if (field?.refresh) {
		field.refresh();
	}
}

function scroll_to_zebra_preview(frm) {
	const preview = frm.fields_dict.preview_html?.$wrapper?.get(0);
	if (preview) {
		preview.scrollIntoView({ behavior: "smooth", block: "center" });
	}
}
