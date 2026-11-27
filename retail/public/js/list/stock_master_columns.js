// Compact stock master lists, using native fields and native list rendering.
(() => {
	const layouts = {
		Batch: [
			["batch_id", "Batch ID", 135, 80],
			["item_name", "Item Name", 240, 120],
			["stock_uom", "UOM", 110, 75],
			["batch_qty", "Qty", 120, 75],
			["manufacturing_date", "Mfg Date", 130, 95],
			["expiry_date", "Expiry", 130, 95],
			["supplier", "Supplier", 180, 90],
		],
		BOM: [
			["name", "BOM ID", 190, 110],
			["item_name", "Item Name", 250, 120],
			["quantity", "Quantity", 110, 65],
			["uom", "UOM", 90, 55],
			["total_cost", "Total Cost", 140, 90],
			["is_active", "Active", 85, 55],
			["is_default", "Default", 85, 55],
		],
	};
	function install() {
		const proto = frappe.views?.ListView?.prototype;
		if (!proto || proto._retail_stock_master_columns) return;
		proto._retail_stock_master_columns = true;
		const setup = proto.setup_columns;
		proto.setup_columns = function (...args) {
			setup.apply(this, args);
			const layout = layouts[this.doctype];
			if (!layout || this.view_name !== "List") return;
			this.retail_fit_columns = true;
			this.retail_list_activity_width = 70;
			const tag = this.columns.find(column => column.type === "Tag");
			const status = this.columns.find(column => column.type === "Status");
			this.columns = layout.map(([fieldname, label, width, minimum], index) => ({
				type: index ? "Field" : "Subject",
				df: { ...(frappe.meta.get_docfield(this.doctype, fieldname) || { fieldname }), label: __(label) },
				retail_compact_width: width,
				retail_min_width: minimum,
			}));
			if (tag) this.columns.splice(1, 0, tag);
			if (status && this.doctype === "BOM") {
				status.retail_compact_width = 105;
				status.retail_min_width = 65;
				this.columns.push(status);
			}
		};
		const set_fields = proto.set_fields;
		proto.set_fields = function (...args) {
			const layout = layouts[this.doctype];
			if (layout) this.settings.add_fields = [...new Set([
				...(this.settings.add_fields || []), ...layout.map(field => field[0]),
			])];
			return set_fields.apply(this, args);
		};
	}
	install();
	$(install);
})();
