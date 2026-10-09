const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const source = fs.readFileSync(
  path.join(__dirname, "../public/js/utils/scrollable_grid.js"),
  "utf8"
);
const piItemMeta = JSON.parse(
  fs.readFileSync(
    path.join(
      __dirname,
      "../../../erpnext/erpnext/accounts/doctype/purchase_invoice_item/purchase_invoice_item.json"
    ),
    "utf8"
  )
);
const piItemTemplate = fs.readFileSync(
  path.join(
    __dirname,
    "../../../erpnext/erpnext/templates/form_grid/item_grid.html"
  ),
  "utf8"
);
const nativeSource = fs
  .readFileSync(
    path.join(
      __dirname,
      "../../../frappe/frappe/public/js/frappe/form/grid.js"
    ),
    "utf8"
  )
  .replace(/^import .*;\n/gm, "")
  .replace("export default class Grid", "class Grid");

function fixture(settings = {}) {
  const handlers = {};
  const styles = {};
  const container = { setAttribute() {}, scrollLeft: 170 };
  class Query {
    constructor(element) {
      if (element) this[0] = element;
    }
    on() {
      return this;
    }
    addClass() {
      return this;
    }
    remove() {
      return this;
    }
    find(selector) {
      return new Query(
        selector === ".form-grid-container" ? container : undefined
      );
    }
    scrollLeft(value) {
      if (value === undefined) return this[0]?.scrollLeft || 0;
      if (this[0]) this[0].scrollLeft = value;
      return this;
    }
  }
  const $ = (element) => new Query(element);
  $.extend = Object.assign;
  const frappe = {
    ui: {
      form: {
        on: (doctype, events) => {
          handlers[doctype] = events;
        },
      },
    },
    utils: { debounce: (fn) => fn },
    meta: { docfield_map: {} },
    get_meta: () => piItemMeta,
    model: {
      layout_fields: ["Section Break", "Column Break"],
      user_settings: {
        "Purchase Invoice": settings,
        save: async (doctype, key, value) => {
          const current = frappe.model.user_settings[doctype] || {};
          return {
            message: { ...current, [key]: { ...current[key], ...value } },
          };
        },
      },
    },
    get_user_settings: (doctype, key) =>
      frappe.model.user_settings[doctype]?.[key] || {},
    throw: (message) => {
      throw new Error(message);
    },
  };
  const context = { frappe, $, __: (text) => text, setTimeout };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(`${nativeSource}\nglobalThis.NativeGrid = Grid;`, context);
  vm.runInContext(source, context);
  const frm = {
    doctype: "Purchase Invoice",
    wrapper: {},
    fields_dict: {},
    meta: { __form_grid_templates: { items: piItemTemplate } },
    get_perm: (level) => !level,
  };
  const fields = Array.from({ length: 16 }, (_, i) => ({
    fieldname: `field_${i}`,
    fieldtype: "Currency",
    in_list_view: 1,
    columns: 1,
    permlevel: 0,
    read_only: i === 15 ? 1 : 0,
  }));
  const grid = new context.NativeGrid({
    frm,
    df: { fieldname: "items", options: "Purchase Invoice Item" },
  });
  grid.doctype = "Purchase Invoice Item";
  grid.docfields = fields;
  grid.fields_map = Object.fromEntries(fields.map((df) => [df.fieldname, df]));
  grid.wrapper = new Query({
    style: {
      setProperty: (key, value) => {
        styles[key] = value;
      },
    },
  });
  grid.refreshes = 0;
  grid.setup_fields = function () {};
  grid.refresh = function () {
    this.refreshes++;
    this.setup_fields();
    this.setup_visible_columns();
    this.header_row = { grid: this, frm, render_selected_columns() {} };
    return "native-refresh-result";
  };
  grid.reset_grid = function () {
    this.visible_columns = [];
    this.refresh();
  };
  frm.fields_dict.items = { grid };
  return { context, handlers, frm, grid, fields, styles, container, frappe };
}

function names(grid) {
  return Array.from(grid.visible_columns, ([df]) => df.fieldname);
}

test("registered transaction grids remove the native width budget without a prototype patch", () => {
  const f = fixture();
  const native = f.context.NativeGrid.prototype.setup_visible_columns;
  f.grid.setup_visible_columns();
  assert.equal(f.grid.visible_columns.length, 10);
  assert.deepEqual(Object.keys(f.handlers), [
    "Purchase Order", "Purchase Invoice", "Purchase Receipt", "Material Request",
    "Stock Reconciliation", "Stock Entry", "Delivery Note", "Sales Order",
    "Sales Invoice", "POS Invoice",
  ]);
  f.handlers["Purchase Invoice"].refresh(f.frm);
  assert.equal(f.grid.visible_columns.length, 16);
  assert.equal(f.context.NativeGrid.prototype.setup_visible_columns, native);
  assert.equal(f.grid.refresh(), "native-refresh-result");
  assert.equal(f.container.scrollLeft, 170);
  assert.equal(parseInt(f.styles["--retail-grid-width"], 10),
    138 + Object.values(f.grid.__retail_content_widths).reduce((a, b) => a + b, 0));
});

test("hidden, permission-restricted and layout fields stay excluded; read-only metadata stays intact", () => {
  const f = fixture();
  f.fields[1].hidden = 1;
  f.fields[2].permlevel = 1;
  f.fields[3].fieldtype = "Section Break";
  f.handlers["Purchase Invoice"].refresh(f.frm);
  assert.equal(f.grid.visible_columns.length, 13);
  assert.ok(!names(f.grid).includes("field_1"));
  assert.ok(!names(f.grid).includes("field_2"));
  assert.ok(!names(f.grid).includes("field_3"));
  assert.equal(f.grid.visible_columns.at(-1)[0].read_only, 1);
});

test("saved selection uses current field restrictions and preserves field order and widths", () => {
  const f = fixture({
    RetailScrollableGrid: {
      items: [
        { fieldname: "field_15", columns: 3 },
        { fieldname: "field_2", columns: 2 },
        { fieldname: "field_4", columns: 1 },
        { fieldname: "removed", columns: 1 },
      ],
    },
  });
  f.fields[2].hidden = 1;
  f.handlers["Purchase Invoice"].refresh(f.frm);
  assert.deepEqual(names(f.grid), ["field_15", "field_4"]);
  assert.equal(f.grid.visible_columns[0][1], 3);
  assert.equal(
    f.fields[15].columns,
    1,
    "saved widths must not mutate global metadata"
  );
  assert.equal(f.grid.visible_columns[0][0].read_only, 1);
});

test("selector accepts totals over ten, rejects bad individual widths and empty selection", () => {
  const f = fixture();
  f.handlers["Purchase Invoice"].refresh(f.frm);
  const header = f.grid.header_row;
  header.selected_columns_for_grid = f.fields.map((df) => ({
    fieldname: df.fieldname,
    columns: 2,
  }));
  assert.doesNotThrow(() => header.validate_columns_width());
  for (const bad of [0, -1, 13, 1.5, "invalid"]) {
    header.selected_columns_for_grid = [{ columns: bad }];
    assert.throws(() => header.validate_columns_width(), /whole number/);
  }
  header.selected_columns_for_grid = [];
  assert.throws(() => header.validate_columns_width(), /at least one/);
});

test("saving and resetting are isolated from standard grid preferences and other tables", async () => {
  const legacy = {
    "Purchase Invoice Item": [{ fieldname: "field_0", columns: 1 }],
  };
  const f = fixture({
    GridView: legacy,
    RetailScrollableGrid: { taxes: [{ fieldname: "tax_amount", columns: 2 }] },
  });
  f.handlers["Purchase Invoice"].refresh(f.frm);
  assert.deepEqual(names(f.grid), ["field_0"]);
  f.grid.header_row.selected_columns_for_grid = f.fields.map((df) => ({
    fieldname: df.fieldname,
    columns: 1,
  }));
  await f.grid.header_row.update_user_settings_for_grid();
  assert.equal(f.grid.visible_columns.length, 16);
  assert.deepEqual(
    f.frappe.model.user_settings["Purchase Invoice"].GridView,
    legacy
  );
  assert.equal(
    f.frappe.model.user_settings["Purchase Invoice"].RetailScrollableGrid.taxes
      .length,
    1
  );
  await f.grid.header_row.reset_user_settings_for_grid();
  assert.equal(
    f.grid.visible_columns.length,
    16,
    "reset uses all default list-view fields"
  );
  assert.deepEqual(
    f.frappe.model.user_settings["Purchase Invoice"].GridView,
    legacy
  );
});

test("repeated form refresh is idempotent and other doctypes can be registered explicitly", () => {
  const f = fixture();
  f.handlers["Purchase Invoice"].refresh(f.frm);
  const refresh = f.grid.refresh;
  f.handlers["Purchase Invoice"].refresh(f.frm);
  assert.equal(f.grid.refresh, refresh);
  f.context.retail.scrollable_grid.register("Sales Invoice", "items");
  assert.ok(f.handlers["Sales Invoice"]);
});

test("dynamic visibility changes rebuild columns and debounced refresh still configures the header", () => {
  const f = fixture();
  f.fields[2].hidden = 1;
  f.handlers["Purchase Invoice"].refresh(f.frm);
  assert.ok(!names(f.grid).includes("field_2"));
  f.fields[2].hidden = 0;
  f.grid.grid_rows = [{}];
  f.grid.debounced_refresh();
  assert.ok(names(f.grid).includes("field_2"));
  assert.equal(f.grid.grid_rows.length, 0);
  f.grid.header_row.selected_columns_for_grid = f.fields.map((df) => ({
    fieldname: df.fieldname,
    columns: 2,
  }));
  assert.doesNotThrow(() => f.grid.header_row.validate_columns_width());
  f.fields[2].hidden = 1;
  f.grid.refresh();
  assert.ok(!names(f.grid).includes("field_2"));
});

test("noneditable template-rendered grids are still left to the native renderer", () => {
  const f = fixture();
  f.grid.meta = { ...piItemMeta, editable_grid: 0 };
  const refresh = f.grid.refresh;
  f.handlers["Purchase Invoice"].refresh(f.frm);
  assert.equal(f.grid.refresh, refresh);
  assert.equal(f.grid.__retail_scroll_options, undefined);
});

for (const doctype of ["Purchase Order", "Purchase Receipt", "Material Request",
  "Stock Reconciliation", "Stock Entry", "Delivery Note", "Sales Order", "Sales Invoice", "POS Invoice"]) {
  test(`${doctype} registration enables the items grid`, () => {
    const f = fixture();
    f.frm.doctype = doctype;
    f.handlers[doctype].refresh(f.frm);
    assert.equal(f.grid.visible_columns.length, 16);
    assert.ok(f.grid.__retail_scroll_options);
  });
}

 test("content-fit widths follow headings and values with a cap for long text", () => {
  const f = fixture();
  f.fields[0].label = "Qty";
  f.fields[0].columns = 12;
  f.fields[1].label = "Description";
  f.handlers["Purchase Invoice"].refresh(f.frm);
  f.grid.grid_rows = [{doc: {field_0: 2, field_1: "A".repeat(200)}}];
  f.grid.refresh();
  assert.equal(f.grid.__retail_content_widths.field_0, 64);
  assert.equal(f.grid.__retail_content_widths.field_1, 320);
  f.grid.grid_rows = [{doc: {field_0: 123456789, field_1: "Short"}}];
  f.grid.refresh();
  assert.equal(f.grid.__retail_content_widths.field_0, 95);
  assert.equal(f.grid.__retail_content_widths.field_1, 117);
 });
