const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");
const source = fs.readFileSync(
  path.join(__dirname, "../public/js/utils/column_preferences.js"),
  "utf8"
);

function fixture() {
  const handlers = {};
  const calls = [];
  const nativeSave = () => {
    throw new Error("Native save must remain untouched");
  };
  const frappe = {
    boot: { retail_column_doctypes: ["Purchase Invoice", "Sales Invoice"] },
    ui: {
      form: {
        on: (doctype, events) => {
          handlers[doctype] = events;
        },
      },
    },
    model: { user_settings: { save: nativeSave } },
    call: async (args) => {
      calls.push(args);
      const { doctype, key, value } = args.args;
      const current = frappe.model.user_settings[doctype] || {};
      return { message: { ...current, [key]: JSON.parse(value) } };
    },
  };
  const context = { frappe, setTimeout };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(source, context);
  const frm = { doctype: "Purchase Invoice", fields_dict: {} };
  const grid = {
    doctype: "Purchase Invoice Item",
    resets: 0,
    reset_grid() {
      this.resets++;
      this.make_head();
    },
    make_head() {
      this.header_row = {
        grid: this,
        frm,
        selected_columns_for_grid: [{ fieldname: "item_code", columns: 2 }],
      };
    },
  };
  grid.make_head();
  frm.fields_dict.items = { grid };
  return { context, frappe, handlers, calls, frm, grid, nativeSave };
}

test("only allowlisted form instances are changed; shared settings save remains native", () => {
  const f = fixture();
  assert.deepEqual(Object.keys(f.handlers), [
    "Purchase Invoice",
    "Sales Invoice",
  ]);
  f.handlers["Purchase Invoice"].refresh(f.frm);
  assert.equal(f.frappe.model.user_settings.save, f.nativeSave);
  assert.equal(f.handlers.DocType, undefined);
  const head = f.grid.make_head;
  f.handlers["Purchase Invoice"].refresh(f.frm);
  assert.equal(f.grid.make_head, head);
});

test("standard grid save and reset use durable API after header recreation", async () => {
  const f = fixture();
  f.handlers["Purchase Invoice"].refresh(f.frm);
  await f.grid.header_row.update_user_settings_for_grid();
  assert.equal(f.calls[0].method, "retail.column_preferences.save");
  assert.equal(f.calls[0].type, "POST");
  assert.deepEqual(JSON.parse(f.calls[0].args.value), {
    "Purchase Invoice Item": [{ fieldname: "item_code", columns: 2 }],
  });
  assert.equal(f.grid.resets, 1);
  await f.grid.header_row.reset_user_settings_for_grid();
  assert.equal(f.calls[1].args.value, "null");
  assert.equal(f.grid.resets, 2);
});

test("scrollable grids keep their own namespace and can use durable API", async () => {
  const f = fixture();
  f.grid.__retail_scroll_options = {};
  const ownSave = () => {};
  f.grid.header_row.update_user_settings_for_grid = ownSave;
  f.handlers["Purchase Invoice"].refresh(f.frm);
  assert.equal(f.grid.header_row.update_user_settings_for_grid, ownSave);
  await f.context.retail.column_preferences.save(
    "Purchase Invoice",
    "RetailScrollableGrid",
    { items: [] }
  );
  assert.equal(f.calls[0].args.key, "RetailScrollableGrid");
});

test("failed database response leaves displayed settings and grid untouched", async () => {
  const f = fixture();
  const previous = { GridView: { old: [] } };
  f.frappe.model.user_settings["Purchase Invoice"] = previous;
  f.frappe.call = async () => {
    throw new Error("write failed");
  };
  f.handlers["Purchase Invoice"].refresh(f.frm);
  await assert.rejects(
    f.grid.header_row.update_user_settings_for_grid(),
    /write failed/
  );
  assert.equal(f.frappe.model.user_settings["Purchase Invoice"], previous);
  assert.equal(f.grid.resets, 0);
});

test("client rejects other forms and unrelated preferences", async () => {
  const f = fixture();
  await assert.rejects(
    f.context.retail.column_preferences.save("DocType", "GridView", {}),
    /Unsupported/
  );
  await assert.rejects(
    f.context.retail.column_preferences.save("Purchase Invoice", "List", {}),
    /Unsupported/
  );
  assert.equal(f.calls.length, 0);
});
