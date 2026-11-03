const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const context = {
	retail: {},
	frappe: { pages: { "retail-item-family-l": {} }, provide() {} },
	__: (text) => text,
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname,
	"../retail_app/page/retail_item_family_l/retail_item_family_l.js"), "utf8"), context);

function list() {
	const page = Object.create(context.retail.ItemFamilyList.prototype);
	Object.assign(page, {
		request_id: 1, start: 50, page_length: 50, has_more: false,
		get_filter_values: () => ({ brand: "Test" }),
		get_colspan: () => 18,
		update_pagination() {},
		update_selection_state() {},
		render(rows) { this.rendered = rows; },
		$tbody: { html(text) { page.html = text; } },
	});
	return page;
}

(async () => {
	const page = list();
	context.frappe.call = async ({ args }) => {
		assert.equal(args.start, 50);
		assert.equal(args.page_length, 50);
		assert.equal(args.filters.brand, "Test");
		return { message: { families: [{ item_code: "A" }], has_more: true } };
	};
	await page.load();
	assert.equal(page.rendered[0].item_code, "A");
	assert.equal(page.has_more, true);
	assert.equal(page.loading, false);

	context.frappe.call = async () => { throw new Error("timeout"); };
	await page.load();
	assert.match(page.html, /Unable to load items/);
	assert.match(page.html, /retail-family-retry/);
	assert.equal(page.loading, false);

	const pending = [];
	context.frappe.call = () => new Promise((resolve) => pending.push(resolve));
	const oldRequest = page.load();
	page.request_id += 1;
	const newRequest = page.load();
	pending[1]({ message: { families: [{ item_code: "NEW" }], has_more: false } });
	await newRequest;
	pending[0]({ message: { families: [{ item_code: "OLD" }], has_more: true } });
	await oldRequest;
	assert.equal(page.rendered[0].item_code, "NEW");
	assert.equal(page.has_more, false);
	console.log("PASS: paginated request, retry after failure, stale response protection");
})().catch((error) => { console.error(error); process.exitCode = 1; });
