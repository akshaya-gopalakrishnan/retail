(() => {
  var __defProp = Object.defineProperty;
  var __defProps = Object.defineProperties;
  var __getOwnPropDescs = Object.getOwnPropertyDescriptors;
  var __getOwnPropSymbols = Object.getOwnPropertySymbols;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __propIsEnum = Object.prototype.propertyIsEnumerable;
  var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
  var __spreadValues = (a, b) => {
    for (var prop in b || (b = {}))
      if (__hasOwnProp.call(b, prop))
        __defNormalProp(a, prop, b[prop]);
    if (__getOwnPropSymbols)
      for (var prop of __getOwnPropSymbols(b)) {
        if (__propIsEnum.call(b, prop))
          __defNormalProp(a, prop, b[prop]);
      }
    return a;
  };
  var __spreadProps = (a, b) => __defProps(a, __getOwnPropDescs(b));
  var __objRest = (source, exclude) => {
    var target = {};
    for (var prop in source)
      if (__hasOwnProp.call(source, prop) && exclude.indexOf(prop) < 0)
        target[prop] = source[prop];
    if (source != null && __getOwnPropSymbols)
      for (var prop of __getOwnPropSymbols(source)) {
        if (exclude.indexOf(prop) < 0 && __propIsEnum.call(source, prop))
          target[prop] = source[prop];
      }
    return target;
  };

  // ../retail/retail/public/js/cdn_loader.js
  (function() {
    var _a;
    const fallbacks = (_a = frappe.boot) == null ? void 0 : _a.retail_cdn_local_assets;
    if (!fallbacks || window.__retailCdnLoader)
      return;
    window.__retailCdnLoader = true;
    const original = frappe.require;
    async function download(remote, local) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 5e3);
      try {
        const response = await fetch(remote, { credentials: "omit", signal: controller.signal });
        if (!response.ok)
          throw new Error(`Asset response ${response.status}`);
        return { content: await response.text(), url: remote };
      } catch (error) {
        const response = await fetch(local, { credentials: "same-origin" });
        if (!response.ok)
          throw new Error(`Local asset response ${response.status}`);
        return { content: await response.text(), url: new URL(local, window.location.origin).href };
      } finally {
        clearTimeout(timer);
      }
    }
    frappe.require = function(items, callback) {
      const paths = (typeof items === "string" ? [items] : items).map((path) => frappe.assets.bundled_asset(path));
      if (!paths.some((path) => fallbacks[path]))
        return original.call(this, items, callback);
      frappe.dom.freeze();
      return Promise.all(paths.map((path) => download(path, fallbacks[path] || path))).then((contents) => {
        paths.forEach((path, index) => {
          let content = contents[index].content;
          if (frappe.assets.extn(path) === "css") {
            content = content.replace(
              /url\(\s*(["']?)([^"')]+)\1\s*\)/g,
              (match, quote, url) => /^(data:|#)/i.test(url.trim()) ? match : `url("${new URL(url.trim(), contents[index].url).href}")`
            );
          }
          frappe.assets.eval_assets(path, content);
        });
        callback == null ? void 0 : callback();
      }).finally(() => frappe.dom.unfreeze());
    };
  })();

  // ../retail/retail/public/js/workspace_boot_sidebar.js
  (() => {
    function install() {
      var _a, _b;
      const prototype = (_b = (_a = frappe.views) == null ? void 0 : _a.Workspace) == null ? void 0 : _b.prototype;
      if (!(prototype == null ? void 0 : prototype.get_pages) || prototype.get_pages.retail_boot_sidebar)
        return;
      const get_pages = prototype.get_pages;
      let available = true;
      function from_boot() {
        const boot = frappe.boot;
        if (available && (boot == null ? void 0 : boot.retail_workspace_sidebar_access) && Array.isArray(boot.allowed_workspaces)) {
          available = false;
          return Promise.resolve(__spreadProps(__spreadValues({}, boot.retail_workspace_sidebar_access), {
            pages: JSON.parse(JSON.stringify(boot.allowed_workspaces))
          }));
        }
        available = false;
        return get_pages.apply(this, arguments);
      }
      from_boot.retail_boot_sidebar = true;
      prototype.get_pages = from_boot;
    }
    install();
    $(document).on("startup", install);
  })();

  // ../retail/retail/public/js/business_home_charts.js
  (() => {
    const chart_names = /* @__PURE__ */ new Set([
      "Top Selling Products",
      "Sales by Counter",
      "Sales Trend 7 Days"
    ]);
    const pending = /* @__PURE__ */ new Map();
    function with_metadata(doctype) {
      if (pending.has(doctype))
        return pending.get(doctype);
      if (locals.DocType[doctype])
        return Promise.resolve();
      const request = Promise.resolve().then(() => frappe.model.with_doctype(doctype)).then((response) => {
        if ((response == null ? void 0 : response.exc) || !locals.DocType[doctype]) {
          throw new Error(`Unable to load metadata for ${doctype}`);
        }
      });
      const shared = request.finally(() => {
        if (pending.get(doctype) === shared)
          pending.delete(doctype);
      });
      pending.set(doctype, shared);
      return shared;
    }
    frappe.provide("retail.business_home_charts");
    retail.business_home_charts.with_metadata = with_metadata;
    function install() {
      var _a;
      const factory = (_a = frappe.widget) == null ? void 0 : _a.widget_factory;
      if (!(factory == null ? void 0 : factory.chart) || factory.chart.retail_business_home)
        return;
      const ChartWidget = factory.chart;
      class BusinessHomeChart extends ChartWidget {
        constructor(opts) {
          super(opts);
          const route = frappe.get_route();
          this.retail_business_home = route[0] === "Workspaces" && route[1] === "Business Home" && chart_names.has(opts.chart_name);
        }
        is_retail_custom_chart() {
          var _a2;
          return this.retail_business_home && ((_a2 = this.chart_doc) == null ? void 0 : _a2.chart_type) === "Custom" && this.chart_doc.source === this.chart_name && this.chart_doc.document_type === "Sales Invoice";
        }
        get_chart_args() {
          if (!this.is_retail_custom_chart() || this.chart_doc.value_based_on) {
            return super.get_chart_args();
          }
          const chart_doc = this.chart_doc;
          this.chart_doc = __spreadProps(__spreadValues({}, chart_doc), { document_type: null });
          try {
            return super.get_chart_args();
          } finally {
            this.chart_doc = chart_doc;
          }
        }
        async render() {
          if (!this.is_retail_custom_chart())
            return super.render();
          if (this.chart_doc.value_based_on) {
            await with_metadata(this.chart_doc.document_type);
            return super.render();
          }
          if (!this.data || !this.data.labels || !Object.keys(this.data).length) {
            this.chart_wrapper.hide();
            this.loading.hide();
            this.$summary && this.$summary.hide();
            this.empty.show();
            return;
          }
          this.loading.hide();
          this.empty.hide();
          this.chart_wrapper.show();
          const chart_args = this.get_chart_args();
          if (!this.dashboard_chart) {
            this.dashboard_chart = frappe.utils.make_chart(this.chart_wrapper[0], chart_args);
          } else {
            this.dashboard_chart.update(this.data);
          }
          this.width == "Full" && this.summary && this.set_summary();
          this.chart_doc.type == "Heatmap" && this.render_heatmap_legend();
        }
      }
      BusinessHomeChart.retail_business_home = true;
      factory.chart = BusinessHomeChart;
    }
    install();
    $(document).on("startup", install);
  })();

  // ../retail/retail/public/js/business_home_preload.js
  (() => {
    function install() {
      var _a, _b;
      const prototype = (_b = (_a = frappe.views) == null ? void 0 : _a.Workspace) == null ? void 0 : _b.prototype;
      if (!prototype || prototype.get_data.retail_widget_preload)
        return;
      const get_data = prototype.get_data;
      function with_definitions(page) {
        return get_data.apply(this, arguments).then((result) => {
          var _a2, _b2, _c, _d, _e, _f, _g;
          if (page.name === "Business Home") {
            for (const definition of ((_a2 = this.page_data) == null ? void 0 : _a2.retail_widget_definitions) || []) {
              try {
                frappe.model.sync(definition);
              } catch (error) {
                for (const doc of definition.docs || []) {
                  frappe.model.clear_doc(doc.doctype, doc.name);
                }
              }
            }
            for (const [source, config] of Object.entries(((_b2 = this.page_data) == null ? void 0 : _b2.retail_chart_source_configs) || {})) {
              if ((_d = (_c = frappe.dashboards) == null ? void 0 : _c.chart_sources) == null ? void 0 : _d[source])
                continue;
              try {
                frappe.dom.eval(config);
              } catch (error) {
                if ((_e = frappe.dashboards) == null ? void 0 : _e.chart_sources)
                  delete frappe.dashboards.chart_sources[source];
              }
            }
            (_f = this.page_data) == null ? true : delete _f.retail_widget_definitions;
            (_g = this.page_data) == null ? true : delete _g.retail_chart_source_configs;
          }
          return result;
        });
      }
      with_definitions.retail_widget_preload = true;
      prototype.get_data = with_definitions;
    }
    install();
    $(document).on("startup", install);
  })();

  // ../retail/retail/public/js/business_home_profit_cards.js
  (() => {
    var _a;
    const prefix = "retail.retail_app.retail_dashboard.";
    const cards = {
      "Today's Sales": ["get_today_sales", "sales", false],
      "Today's Profit": ["get_profit_number_card", "profit", false],
      "Invoice Count Today": ["get_invoice_count_today", "count", true],
      "Return Amount Today": ["get_return_amount_today", "returns", true]
    };
    let pending = /* @__PURE__ */ new Map();
    let queue = [];
    let scheduled = false;
    function request_context(context) {
      return new Promise((resolve, reject) => {
        queue.push({ context, resolve, reject });
        if (scheduled)
          return;
        scheduled = true;
        setTimeout(async () => {
          const batch = queue;
          queue = [];
          scheduled = false;
          try {
            const results = await frappe.xcall(prefix + "get_business_home_profit_cards", {
              contexts: batch.map((entry) => entry.context)
            });
            batch.forEach((entry, index) => entry.resolve(results[index]));
          } catch (error) {
            batch.forEach((entry) => entry.reject(error));
          }
        }, 0);
      });
    }
    (_a = frappe.router) == null ? void 0 : _a.on("change", () => {
      pending = /* @__PURE__ */ new Map();
    });
    function install() {
      var _a2;
      const factory = (_a2 = frappe.widget) == null ? void 0 : _a2.widget_factory;
      if (!(factory == null ? void 0 : factory.number_card) || factory.number_card.retail_shared_profit)
        return;
      const Base = factory.number_card;
      class BusinessHomeNumberCard extends Base {
        get_number_for_custom_card(res) {
          var _a3;
          const result = super.get_number_for_custom_card(res);
          if (((_a3 = this.card_doc) == null ? void 0 : _a3.name) === "Today's Sales" && this.card_doc.method === prefix + "get_today_sales") {
            const value = typeof res === "object" ? res == null ? void 0 : res.value : res;
            if (typeof value === "number" && Number.isFinite(value)) {
              this.formatted_number = value.toFixed(2);
            }
          }
          return result;
        }
        async get_data() {
          var _a3;
          const route = frappe.get_route();
          const card = cards[(_a3 = this.card_doc) == null ? void 0 : _a3.name];
          if (route[0] !== "Workspaces" || route[1] !== "Business Home" || !card || this.card_doc.type !== "Custom" || this.settings.method !== prefix + card[0])
            return super.get_data();
          const args = this.settings.args || {};
          const context = {
            company: args.company || null,
            today_only: card[2],
            from_date: !card[2] && args.from_date || null,
            to_date: !card[2] && args.to_date || null,
            branch: !card[2] && args.branch || null,
            counter: !card[2] && args.counter || null
          };
          const key = JSON.stringify(__spreadProps(__spreadValues({}, context), { today_only: void 0 }));
          if (this.retail_profit_loaded)
            pending = /* @__PURE__ */ new Map();
          this.retail_profit_loaded = true;
          const requests = pending;
          if (!requests.has(key)) {
            const request = request_context(context);
            const shared = request.catch((error) => {
              requests.delete(key);
              throw error;
            });
            requests.set(key, shared);
          }
          const result = await requests.get(key);
          this.data = result[card[1]];
          return this.settings.get_number(this.data);
        }
      }
      BusinessHomeNumberCard.retail_shared_profit = true;
      factory.number_card = BusinessHomeNumberCard;
    }
    install();
    $(document).on("startup", install);
  })();

  // ../retail/retail/public/js/invoice_search.js
  frappe.provide("retail");
  retail.show_invoice_search = function() {
    const esc = (value) => frappe.utils.escape_html(String(value != null ? value : ""));
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
        { fieldname: "results", fieldtype: "HTML" }
      ],
      primary_action_label: __("Search"),
      primary_action: async () => {
        const filters = dialog.get_values();
        if (!filters)
          return;
        const wrapper = dialog.fields_dict.results.$wrapper;
        dialog.get_primary_btn().prop("disabled", true);
        wrapper.empty().text(__("Searching\u2026"));
        try {
          const { message } = await frappe.call({ method: "retail.invoice_search.search_invoices", args: { filters } });
          const rows = message.invoices;
          wrapper.empty();
          if (!rows.length) {
            wrapper.text(__("No matching invoices found. Try changing the filters."));
            return;
          }
          const headers = ["Bill Number", "Invoice", "Type", "Sale Date & Time", "Customer", "Cashier", "Counter", "Branch", "Total", "Status", "Accounting Invoice", "POS Receipt"];
          const table = $(`<div style="overflow-x:auto"><table class="table table-bordered"><thead><tr>${headers.map((label) => `<th>${esc(__(label))}</th>`).join("")}</tr></thead><tbody></tbody></table></div>`);
          for (const row of rows) {
            const tr = $("<tr>");
            const cell = (value) => $("<td>").text(value || "\u2014").appendTo(tr);
            const link = (doctype, name) => {
              const td = $("<td>").appendTo(tr);
              if (!name)
                return td.text("\u2014");
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
      }
    });
    dialog.show();
    dialog.fields_dict.results.$wrapper.text(__("Enter a bill number or combine the filters above, then click Search. Times use the system time zone."));
  };
  (() => {
    var _a, _b, _c;
    function install_list_patch() {
      var _a2;
      if (!((_a2 = frappe.views) == null ? void 0 : _a2.ListView))
        return;
      const prototype = frappe.views.ListView.prototype;
      if (prototype.retail_invoice_finder)
        return;
      prototype.retail_invoice_finder = true;
      const setup_view = prototype.setup_view;
      prototype.setup_view = function() {
        const result = setup_view.apply(this, arguments);
        if (["POS Invoice", "Sales Invoice"].includes(this.doctype)) {
          this.page.add_inner_button(__("Find Invoice"), retail.show_invoice_search);
        }
        return result;
      };
    }
    function install_form_handlers() {
      var _a2, _b2, _c2;
      const prototype = (_c2 = (_b2 = (_a2 = frappe.ui) == null ? void 0 : _a2.form) == null ? void 0 : _b2.Form) == null ? void 0 : _c2.prototype;
      if (!prototype || !frappe.ui.form.on || prototype.retail_invoice_finder)
        return;
      prototype.retail_invoice_finder = true;
      for (const doctype of ["POS Invoice", "Sales Invoice"]) {
        frappe.ui.form.on(doctype, { refresh(frm) {
          frm.add_custom_button(__("Find Invoice"), retail.show_invoice_search);
        } });
      }
    }
    function install() {
      install_list_patch();
      install_form_handlers();
    }
    install();
    if ((!((_a = frappe.views) == null ? void 0 : _a.ListView) || !((_c = (_b = frappe.ui) == null ? void 0 : _b.form) == null ? void 0 : _c.Form)) && !retail.invoice_finder_init_pending) {
      retail.invoice_finder_init_pending = true;
      $(function() {
        retail.invoice_finder_init_pending = false;
        install();
      });
    }
  })();

  // ../retail/retail/public/js/utils/column_preferences.js
  (() => {
    window.retail = window.retail || {};
    if (retail.column_preferences)
      return;
    const supported = /* @__PURE__ */ new Set();
    function save(doctype, key, value) {
      if (!supported.has(doctype) || !["GridView", "RetailScrollableGrid"].includes(key)) {
        return Promise.reject(new Error("Unsupported Retail column preferences"));
      }
      return frappe.call({
        method: "retail.column_preferences.save",
        type: "POST",
        args: { doctype, key, value: JSON.stringify(value != null ? value : null) }
      }).then((r) => {
        frappe.model.user_settings[doctype] = r.message;
        return r;
      });
    }
    function configureHeader(grid) {
      const row = grid.header_row;
      if (!row || row.__retail_durable_columns || grid.__retail_scroll_options)
        return;
      row.__retail_durable_columns = true;
      row.update_user_settings_for_grid = function() {
        if (!this.selected_columns_for_grid || !this.frm)
          return;
        return save(this.frm.doctype, "GridView", {
          [this.grid.doctype]: this.selected_columns_for_grid
        }).then(() => this.grid.reset_grid());
      };
      row.reset_user_settings_for_grid = function() {
        return save(this.frm.doctype, "GridView", null).then(() => this.grid.reset_grid());
      };
    }
    function enable(frm) {
      for (const control of Object.values(frm.fields_dict)) {
        const grid = control.grid;
        if (!grid || grid.__retail_durable_columns)
          continue;
        grid.__retail_durable_columns = true;
        const makeHead = grid.make_head;
        grid.make_head = function(...args) {
          const result = makeHead.apply(this, args);
          configureHeader(this);
          return result;
        };
        configureHeader(grid);
      }
    }
    retail.column_preferences = { save, supports: (doctype) => supported.has(doctype) };
    function boot() {
      var _a, _b, _c;
      if (!((_c = (_b = (_a = window.frappe) == null ? void 0 : _a.ui) == null ? void 0 : _b.form) == null ? void 0 : _c.on) || !frappe.boot) {
        setTimeout(boot, 100);
        return;
      }
      for (const doctype of frappe.boot.retail_column_doctypes || []) {
        supported.add(doctype);
        frappe.ui.form.on(doctype, { refresh: enable });
      }
    }
    boot();
  })();

  // ../retail/retail/public/js/utils/scrollable_grid.js
  (() => {
    window.retail = window.retail || {};
    if (retail.scrollable_grid)
      return;
    const SETTINGS = "RetailScrollableGrid";
    const registrations = /* @__PURE__ */ new Set();
    function setupColumns() {
      var _a, _b, _c;
      if ((_a = this.visible_columns) == null ? void 0 : _a.length)
        return;
      const own = frappe.get_user_settings(this.frm.doctype, SETTINGS) || {};
      const legacy = frappe.get_user_settings(this.frm.doctype, "GridView") || {};
      const saved = Object.prototype.hasOwnProperty.call(own, this.df.fieldname) ? own[this.df.fieldname] : legacy[this.doctype];
      this.user_defined_columns = (Array.isArray(saved) ? saved : []).flatMap((entry) => {
        const df = this.fields_map[entry.fieldname];
        return df ? [__spreadProps(__spreadValues({}, df), { columns: entry.columns, width_px: entry.width_px, in_list_view: 1 })] : [];
      });
      let fields = this.user_defined_columns.length ? this.user_defined_columns : this.editable_fields || this.docfields;
      const target = this.retail_promotion_target;
      if (target && this.fields_map[target]) {
        fields = [this.fields_map[target], ...fields.filter((field) => (typeof field === "string" ? field : field.fieldname) !== target)];
        if (this.user_defined_columns.length)
          this.user_defined_columns = fields;
      }
      this.visible_columns = [];
      const seen = /* @__PURE__ */ new Set();
      for (const field of fields) {
        const df = typeof field === "string" ? this.fields_map[field] : field;
        if (!df || seen.has(df.fieldname) || df.hidden || !(this.editable_fields || df.in_list_view) || !this.frm.get_perm(df.permlevel, "read") || frappe.model.layout_fields.includes(df.fieldtype))
          continue;
        seen.add(df.fieldname);
        this.update_default_colsize(df);
        df.colsize = Math.max(1, Math.min(12, Number(df.columns) || df.colsize || 1));
        if (df.fieldtype === "Link" && !df.formatter && df.parent) {
          const formatter = (_c = (_b = frappe.meta.docfield_map[df.parent]) == null ? void 0 : _b[df.fieldname]) == null ? void 0 : _c.formatter;
          if (formatter)
            df.formatter = formatter;
        }
        if (df.fieldname === "item_code" && df.fieldtype === "Link" && df.options === "Item") {
          df.formatter = (value, field2, options, doc) => frappe.form.formatters.Link(value, field2, __spreadProps(__spreadValues({}, options), { label: value }), doc);
        }
        this.visible_columns.push([df, df.colsize]);
      }
    }
    function saveColumns(row, columns) {
      var _a;
      const save = ((_a = retail.column_preferences) == null ? void 0 : _a.supports(row.frm.doctype)) ? retail.column_preferences.save : frappe.model.user_settings.save.bind(frappe.model.user_settings);
      return save(row.frm.doctype, SETTINGS, {
        [row.grid.df.fieldname]: columns
      }).then((r) => {
        frappe.model.user_settings[row.frm.doctype] = r.message || r;
        row.grid.reset_grid();
      });
    }
    function configureHeader(grid) {
      const row = grid.header_row;
      if (!row || row.__retail_scroll_header)
        return;
      row.__retail_scroll_header = true;
      row.validate_columns_width = function() {
        var _a;
        if (!((_a = this.selected_columns_for_grid) == null ? void 0 : _a.length)) {
          frappe.throw(__("Select at least one column."));
        }
        for (const entry of this.selected_columns_for_grid) {
          const width = Number(entry.columns);
          if (!Number.isInteger(width) || width < 1 || width > 12) {
            frappe.throw(__("Each column width must be a whole number from 1 to 12."));
          }
        }
      };
      row.update_user_settings_for_grid = function() {
        return saveColumns(this, this.selected_columns_for_grid);
      };
      row.reset_user_settings_for_grid = function() {
        return saveColumns(this, []);
      };
      const render = row.render_selected_columns;
      row.render_selected_columns = function(...args) {
        const result = render.apply(this, args);
        for (const entry of this.selected_columns_for_grid || []) {
          $(this.fields_html_wrapper).find(".column-width").filter(function() {
            return this.dataset.fieldname === entry.fieldname;
          }).val(entry.columns).attr("value", entry.columns);
        }
        $(this.fields_html_wrapper).find(".column-width").on("change.retailPixels", (event) => {
          const entry = this.selected_columns_for_grid.find((column) => column.fieldname === event.target.dataset.fieldname);
          if (entry)
            delete entry.width_px;
        });
        return result;
      };
      const sortColumns = row.sort_columns;
      if (sortColumns)
        row.sort_columns = function(...args) {
          const pixels = new Map((this.selected_columns_for_grid || []).map((entry) => [entry.fieldname, entry.width_px]));
          const result = sortColumns.apply(this, args);
          for (const entry of this.selected_columns_for_grid) {
            if (Number.isFinite(pixels.get(entry.fieldname)))
              entry.width_px = pixels.get(entry.fieldname);
          }
          return result;
        };
      const setupDialog = row.setup_columns_for_dialog;
      if (setupDialog)
        row.setup_columns_for_dialog = function(...args) {
          var _a;
          const result = setupDialog.apply(this, args);
          for (const entry of this.selected_columns_for_grid) {
            const df = (_a = grid.visible_columns.find(([df2]) => df2.fieldname === entry.fieldname)) == null ? void 0 : _a[0];
            if (Number.isFinite(df == null ? void 0 : df.width_px))
              entry.width_px = df.width_px;
          }
          return result;
        };
    }
    function contentWidths(grid) {
      var _a, _b;
      const widths = {};
      const canvas = typeof document !== "undefined" ? document.createElement("canvas") : null;
      const context = canvas == null ? void 0 : canvas.getContext("2d");
      const font = typeof getComputedStyle === "function" ? getComputedStyle(grid.wrapper[0]).font : "14px sans-serif";
      if (context)
        context.font = font || "14px sans-serif";
      const measure = (text) => {
        const lines = String(text != null ? text : "").split(/\r?\n/);
        return Math.max(0, ...lines.map((line) => context ? context.measureText(line).width : line.length * 7));
      };
      for (const [df] of grid.visible_columns) {
        if (Number.isFinite(df.width_px)) {
          widths[df.fieldname] = df.width_px;
          continue;
        }
        if ((_a = grid.user_defined_columns) == null ? void 0 : _a.some((column) => column.fieldname === df.fieldname)) {
          widths[df.fieldname] = Math.max(1, Math.min(12, Number(df.columns) || df.colsize || 1)) * 80;
          continue;
        }
        let width = measure(__(df.label || df.fieldname)) + 40;
        for (const row of grid.grid_rows || []) {
          const value = (_b = row.doc) == null ? void 0 : _b[df.fieldname];
          let text = value != null ? value : "";
          if (frappe.format && value != null) {
            const html = frappe.format(value, df, { inline: true }, row.doc);
            const element = document.createElement("div");
            element.innerHTML = html;
            text = element.textContent || "";
          }
          width = Math.max(width, measure(text) + 32);
        }
        widths[df.fieldname] = Math.ceil(Math.min(320, Math.max(64, width)));
      }
      return widths;
    }
    function styleRow(grid, row) {
      var _a, _b, _c, _d;
      if (!(row == null ? void 0 : row.row))
        return;
      if (row.doc && !row.__retail_item_name_search && ((_a = grid.fields_map.item_code) == null ? void 0 : _a.options) === "Item") {
        row.__retail_item_name_search = true;
        const makeControl = row.make_control;
        row.make_control = function(column) {
          var _a2;
          if (column.df.fieldname !== "item_name")
            return makeControl.call(this, column);
          if (column.field)
            return;
          const df = __spreadProps(__spreadValues({}, grid.fields_map.item_code), { label: column.df.label, formatter: void 0 });
          const field = frappe.ui.form.make_control({
            df,
            parent: column.field_area,
            only_input: true,
            with_link_btn: true,
            doc: this.doc,
            doctype: this.doc.doctype,
            docname: this.doc.name,
            frm: grid.frm,
            grid,
            grid_row: this
          });
          field.get_query = (...args) => {
            const query = grid.get_field("item_code").get_query;
            return typeof query === "function" ? query(...args) : query;
          };
          field.is_title_link = () => true;
          field.refresh();
          (_a2 = field.$input) == null ? void 0 : _a2.addClass("input-sm").attr("placeholder", __("Search Item Name"));
          this.set_arrow_keys(field);
          column.field = field;
          this.on_grid_fields_dict.item_name = field;
          this.on_grid_fields.push(field);
        };
      }
      const itemColumn = grid.visible_columns.find(([df]) => df.fieldname === "item_code" && df.fieldtype === "Link" && df.options === "Item");
      if (row.doc && itemColumn) {
        const field = (_b = row.docfields) == null ? void 0 : _b.find((df) => df.fieldname === "item_code");
        if (field)
          field.formatter = itemColumn[0].formatter;
        (_d = (_c = row.columns) == null ? void 0 : _c.item_code) == null ? void 0 : _d.static_area.html(
          itemColumn[0].formatter(row.doc.item_code, itemColumn[0], {}, row.doc)
        );
      }
      const options = grid.__retail_scroll_options;
      row.row.children(".col").each(function() {
        var _a2, _b2;
        const fieldname = this.dataset.fieldname;
        const column = grid.visible_columns.find(([df]) => df.fieldname === fieldname);
        const width = column ? ((_a2 = grid.__retail_content_widths) == null ? void 0 : _a2[fieldname]) || 80 : this.classList.contains("row-index") ? 56 : 40;
        this.style.setProperty("--retail-column-width", `${width}px`);
        this.style.setProperty("--retail-column-grow", column && fieldname !== grid.__retail_resizing ? String(width) : "0");
        this.classList.toggle("retail-grid-data-column", Boolean(column));
        this.classList.toggle("retail-grid-pinned", fieldname === options.pin_field && ((_b2 = grid.visible_columns[0]) == null ? void 0 : _b2[0].fieldname) === fieldname);
      });
      row.row.children("[data-fieldname]").off("touchmove");
    }
    function currentColumns(grid) {
      return grid.visible_columns.map(([df]) => __spreadValues({
        fieldname: df.fieldname,
        columns: Math.max(1, Math.min(12, Number(df.columns) || df.colsize || 1))
      }, Number.isFinite(df.width_px) ? { width_px: df.width_px } : {}));
    }
    function configureDirectColumns(grid) {
      var _a;
      const header = grid.header_row;
      if (!((_a = header == null ? void 0 : header.row) == null ? void 0 : _a[0]) || header.__retail_direct_columns)
        return;
      header.__retail_direct_columns = true;
      let dragged;
      for (const cell of header.row[0].querySelectorAll(".retail-grid-data-column")) {
        cell.draggable = true;
        cell.title = __("Drag to move column; drag the edge to resize.");
        cell.addEventListener("dragstart", (event) => {
          dragged = cell.dataset.fieldname;
          event.dataTransfer.setData("text/plain", dragged);
          event.dataTransfer.effectAllowed = "move";
        });
        cell.addEventListener("dragover", (event) => {
          if (dragged) {
            event.preventDefault();
            event.dataTransfer.dropEffect = "move";
          }
        });
        cell.addEventListener("drop", (event) => {
          if (!dragged)
            return;
          event.preventDefault();
          const columns = currentColumns(grid);
          const source = columns.findIndex((column) => column.fieldname === dragged);
          const target = columns.findIndex((column) => column.fieldname === cell.dataset.fieldname);
          if (source >= 0 && target >= 0 && source !== target) {
            columns.splice(target, 0, columns.splice(source, 1)[0]);
            saveColumns(header, columns);
          }
          dragged = null;
        });
        cell.addEventListener("dragend", () => {
          dragged = null;
        });
        const handle = document.createElement("span");
        handle.className = "retail-grid-resize-handle";
        handle.title = __("Drag to resize column");
        handle.addEventListener("pointerdown", (event) => {
          event.preventDefault();
          event.stopPropagation();
          cell.draggable = false;
          const start = event.clientX;
          const width = cell.getBoundingClientRect().width;
          const columns = currentColumns(grid);
          const column = columns.find((column2) => column2.fieldname === cell.dataset.fieldname);
          for (const entry of columns) {
            const heading = Array.from(header.row[0].children).find((element) => element.dataset.fieldname === entry.fieldname);
            entry.width_px = Math.round((heading == null ? void 0 : heading.getBoundingClientRect().width) || grid.__retail_content_widths[entry.fieldname]);
            grid.__retail_content_widths[entry.fieldname] = entry.width_px;
          }
          grid.__retail_resizing = column.fieldname;
          const direction = frappe.utils.is_rtl() ? -1 : 1;
          const move = (event2) => {
            const pixels = Math.round(Math.max(64, Math.min(960, width + direction * (event2.clientX - start))));
            column.width_px = pixels;
            grid.__retail_content_widths[column.fieldname] = pixels;
            grid.wrapper[0].style.setProperty("--retail-grid-width", `${138 + Object.values(grid.__retail_content_widths).reduce((sum, value) => sum + value, 0)}px`);
            [header, grid.header_search, ...grid.grid_rows || []].forEach((row) => styleRow(grid, row));
          };
          const finish = () => {
            document.removeEventListener("pointermove", move);
            document.removeEventListener("pointerup", finish);
            document.removeEventListener("pointercancel", cancel);
            cell.draggable = true;
            for (const entry of columns) {
              const heading = Array.from(header.row[0].children).find((element) => element.dataset.fieldname === entry.fieldname);
              entry.width_px = Math.round((heading == null ? void 0 : heading.getBoundingClientRect().width) || entry.width_px);
            }
            delete grid.__retail_resizing;
            saveColumns(header, columns);
          };
          const cancel = () => {
            document.removeEventListener("pointermove", move);
            document.removeEventListener("pointerup", finish);
            document.removeEventListener("pointercancel", cancel);
            cell.draggable = true;
            delete grid.__retail_resizing;
            layout(grid);
          };
          document.addEventListener("pointermove", move);
          document.addEventListener("pointerup", finish);
          document.addEventListener("pointercancel", cancel);
        });
        cell.appendChild(handle);
      }
    }
    function layout(grid) {
      if (!grid.wrapper || grid.__retail_resizing)
        return;
      grid.wrapper.addClass("retail-scrollable-grid");
      const container = grid.wrapper.find(".form-grid-container")[0];
      if (!container)
        return;
      container.setAttribute("aria-label", __("Scrollable table"));
      container.setAttribute("tabindex", "0");
      grid.__retail_content_widths = contentWidths(grid);
      const totalWidth = 138 + grid.visible_columns.reduce(
        (sum, [df]) => sum + grid.__retail_content_widths[df.fieldname],
        0
      );
      grid.wrapper[0].style.setProperty("--retail-grid-width", `${totalWidth}px`);
      configureHeader(grid);
      [grid.header_row, grid.header_search, ...grid.grid_rows || []].forEach(
        (row) => styleRow(grid, row)
      );
      configureDirectColumns(grid);
    }
    function bindInteractions(grid) {
      let popup;
      const closePopup = () => {
        if (!popup)
          return;
        popup.parent.appendChild(popup.list);
        popup.host.remove();
        popup = null;
        window.removeEventListener("scroll", reposition, true);
        window.removeEventListener("resize", reposition);
      };
      const reposition = () => {
        if (!popup)
          return;
        if (!popup.input.isConnected || popup.list.hidden) {
          closePopup();
          return;
        }
        const rect = popup.input.getBoundingClientRect();
        const viewport = grid.wrapper.find(".form-grid-container")[0].getBoundingClientRect();
        if (rect.right < viewport.left || rect.left > viewport.right || rect.bottom < 0 || rect.top > innerHeight) {
          popup.input.dispatchEvent(new Event("blur"));
          closePopup();
          return;
        }
        const width = Math.min(Math.max(rect.width, 280), innerWidth - 16);
        const below = innerHeight - rect.bottom - 12;
        const above = below < 180 && rect.top > below;
        Object.assign(popup.host.style, {
          width: `${width}px`,
          left: `${Math.max(8, Math.min(rect.left, innerWidth - width - 8))}px`,
          top: above ? "auto" : `${rect.bottom}px`,
          bottom: above ? `${innerHeight - rect.top}px` : "auto"
        });
        popup.list.style.maxHeight = `${Math.max(
          60,
          Math.min(300, above ? rect.top - 12 : below)
        )}px`;
      };
      grid.wrapper.on("awesomplete-open.retailScroll", "input", function() {
        if (!this.closest(".data-row"))
          return;
        closePopup();
        const parent = this.closest(".awesomplete");
        const list = parent == null ? void 0 : parent.querySelector("ul");
        if (!list)
          return;
        const host = document.createElement("div");
        host.className = "awesomplete retail-grid-autocomplete";
        document.body.appendChild(host);
        host.appendChild(list);
        popup = { input: this, parent, list, host };
        reposition();
        window.addEventListener("scroll", reposition, true);
        window.addEventListener("resize", reposition);
      }).on("awesomplete-close.retailScroll", "input", closePopup);
      grid.wrapper.on(
        "focusin.retailScroll",
        ".data-row input, .data-row select, .data-row textarea",
        function() {
          const cell = this.closest(".col");
          if (!cell || cell.classList.contains("retail-grid-pinned"))
            return;
          const container = grid.wrapper.find(".form-grid-container")[0];
          const bounds = container.getBoundingClientRect();
          const rect = cell.getBoundingClientRect();
          const pinned = this.closest(".data-row").querySelector(".retail-grid-pinned");
          const inset = innerWidth > 767 ? 96 + ((pinned == null ? void 0 : pinned.offsetWidth) || 0) : 0;
          const rtl = frappe.utils.is_rtl();
          const left = bounds.left + (rtl ? 0 : inset);
          const right = bounds.right - (rtl ? inset : 0);
          if (rect.left < left)
            container.scrollLeft -= left - rect.left;
          else if (rect.right > right)
            container.scrollLeft += rect.right - right;
        }
      );
    }
    function enable(frm, fieldname, options = {}) {
      var _a, _b;
      const grid = (_a = frm.fields_dict[fieldname]) == null ? void 0 : _a.grid;
      if (!grid || grid.__retail_scroll_options || grid.template && !((_b = grid.meta) == null ? void 0 : _b.editable_grid))
        return;
      grid.__retail_scroll_options = __spreadValues({ pin_field: "item_code" }, options);
      grid.setup_visible_columns = setupColumns;
      const setupFields = grid.setup_fields;
      grid.setup_fields = function(...args) {
        var _a2;
        const previous = JSON.stringify(
          (this.visible_columns || []).map(([df, width]) => [df.fieldname, width])
        );
        const result = setupFields.apply(this, args);
        this.visible_columns = [];
        this.setup_visible_columns();
        const current = JSON.stringify(
          this.visible_columns.map(([df, width]) => [df.fieldname, width])
        );
        if (previous !== current && ((_a2 = this.grid_rows) == null ? void 0 : _a2.length)) {
          this.grid_rows = [];
          this.wrapper.find(".grid-body .grid-row").remove();
        }
        return result;
      };
      const refresh = grid.refresh;
      grid.refresh = function(...args) {
        var _a2, _b2;
        const scroll = ((_a2 = this.wrapper) == null ? void 0 : _a2.find(".form-grid-container").scrollLeft()) || 0;
        const result = refresh.apply(this, args);
        layout(this);
        (_b2 = this.wrapper) == null ? void 0 : _b2.find(".form-grid-container").scrollLeft(scroll);
        return result;
      };
      const fitColumns = frappe.utils.debounce(() => layout(grid), 100);
      const refreshField = grid.refresh_field;
      if (refreshField) {
        grid.refresh_field = function(...args) {
          const result = refreshField.apply(this, args);
          fitColumns();
          return result;
        };
      }
      grid.debounced_refresh = frappe.utils.debounce(grid.refresh.bind(grid), 100);
      $(frm.wrapper).on(`grid-row-render.retailScroll_${fieldname}`, (_event, row) => {
        if (row.grid === grid) {
          styleRow(grid, row);
          fitColumns();
        }
      });
      grid.reset_grid();
      bindInteractions(grid);
    }
    function register(doctype, fieldname, options = {}) {
      const key = `${doctype}:${fieldname}`;
      if (registrations.has(key))
        return;
      registrations.add(key);
      frappe.ui.form.on(doctype, {
        refresh(frm) {
          enable(frm, fieldname, options);
        }
      });
    }
    retail.scrollable_grid = { enable, register };
    function boot() {
      var _a, _b, _c;
      if (!((_c = (_b = (_a = window.frappe) == null ? void 0 : _a.ui) == null ? void 0 : _b.form) == null ? void 0 : _c.on)) {
        setTimeout(boot, 100);
        return;
      }
      register("Purchase Order", "items");
      register("Purchase Invoice", "items");
      register("Purchase Receipt", "items");
      register("Material Request", "items");
      register("Stock Reconciliation", "items");
      register("Stock Entry", "items");
      register("Delivery Note", "items");
      register("Sales Order", "items");
      register("Sales Invoice", "items");
      register("POS Invoice", "items");
      register("Promo Price", "products", { pin_field: "item" });
      register("Item", "custom_retail_packing_detail", {
        pin_field: "barcode"
      });
    }
    boot();
  })();

  // ../retail/retail/public/js/retail_keyboard.js
  (() => {
    frappe.provide("retail.keyboard");
    const api = retail.keyboard;
    if (api.installed)
      return;
    api.installed = true;
    api.doctypes || (api.doctypes = {});
    api.children || (api.children = {});
    const scanNames = ["scan_barcode", "barcode", "item_barcode"];
    const native = "textarea,select,button,a,[contenteditable]:not([contenteditable=false]),[role=button]";
    let generation = 0;
    let pending = 0;
    const visible = (el) => !!el && $(el).is(":visible");
    const enabled = (el) => visible(el) && !el.disabled && !el.readOnly && !el.closest('[aria-disabled="true"],.disabled');
    const frozen = () => $("#freeze:not(.grid-form):visible,.freeze:not(.grid-form):visible").length;
    const blocked = (includeFreeze = true) => window.cur_dialog || includeFreeze && frozen() || $(".modal:visible,.dropdown-menu:visible,[role=listbox]:visible,.awesomplete > ul:visible,.datepicker.active:visible").length;
    const current = () => {
      const frm = window.cur_frm;
      return frappe.get_route()[0] === "Form" && visible(frm == null ? void 0 : frm.wrapper) ? frm : null;
    };
    const scanField = (frm) => {
      var _a;
      const override = (_a = api.doctypes[frm.doctype]) == null ? void 0 : _a.scan_field;
      return (override === false ? [] : override ? [override] : scanNames).map((name) => frm.fields_dict[name]).find((field) => {
        var _a2;
        return field && !field.df.hidden && !field.df.read_only && !field.grid && enabled((_a2 = field.$input) == null ? void 0 : _a2[0]);
      });
    };
    function reveal(input) {
      if (!(input == null ? void 0 : input.getBoundingClientRect) || !input.scrollIntoView)
        return;
      input.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "instant" });
      const margin = 12;
      const viewportHeight = window.innerHeight;
      let top = margin;
      const rect = input.getBoundingClientRect();
      for (const bar of Array.from(document.querySelectorAll(".sticky-top, .navbar, .page-head, .form-tabs-list")).sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top)) {
        const style = getComputedStyle(bar);
        const bounds2 = bar.getBoundingClientRect();
        if (!["fixed", "sticky"].includes(style.position) || style.visibility === "hidden" || !bounds2.height || bounds2.bottom <= 0 || bounds2.top > top || bounds2.right <= rect.left || bounds2.left >= rect.right)
          continue;
        top = Math.max(top + bounds2.height, bounds2.bottom + margin);
      }
      const dy = rect.top < top ? rect.top - top : rect.bottom > viewportHeight - margin ? rect.bottom - viewportHeight + margin : 0;
      if (dy)
        window.scrollBy({ top: dy, left: 0, behavior: "instant" });
      const container = input.closest(".retail-scrollable-grid .form-grid-container");
      const row = input.closest(".data-row");
      if (!container || !row || input.closest(".retail-grid-pinned"))
        return;
      const bounds = container.getBoundingClientRect();
      let left = Math.max(0, bounds.left) + margin;
      let right = Math.min(window.innerWidth, bounds.right) - margin;
      for (const pinned of row.querySelectorAll(".row-check, .row-index, .retail-grid-pinned")) {
        if (getComputedStyle(pinned).position !== "sticky")
          continue;
        const pin = pinned.getBoundingClientRect();
        if (getComputedStyle(container).direction === "rtl")
          right = Math.min(right, pin.left - margin);
        else
          left = Math.max(left, pin.right + margin);
      }
      const cell = input.getBoundingClientRect();
      const dx = cell.left < left ? cell.left - left : cell.right > right ? cell.right - right : 0;
      if (dx)
        container.scrollBy({ left: dx, top: 0, behavior: "instant" });
    }
    const focus = (field) => {
      var _a, _b;
      const input = (_a = field == null ? void 0 : field.$input) == null ? void 0 : _a[0];
      if (enabled(input)) {
        input.focus({ preventScroll: true });
        (_b = input.select) == null ? void 0 : _b.call(input);
        reveal(input);
      }
    };
    const consume = (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
    };
    let selected = null;
    const expanded = (row) => {
      var _a;
      return visible((_a = row.grid_form) == null ? void 0 : _a.wrapper);
    };
    const controls = (row) => {
      const config = api.children[row.doc.doctype] || {};
      const fields = expanded(row) ? (row.grid_form.fields || Object.values(row.grid_form.fields_dict)).map((field) => ({ df: field.df, field, cell: field.$wrapper || field.wrapper })) : (row.columns_list || []).map((column) => ({ df: column.df, field: column.field, cell: column }));
      return fields.filter(
        ({ df, field, cell }) => {
          var _a, _b, _c, _d, _e, _f;
          return !df.hidden && !df.hidden_due_to_dependency && !df.read_only && !df.disabled && !df.is_virtual && !((_a = config.skip) == null ? void 0 : _a.includes(df.fieldname)) && !((_b = frappe.model.no_value_type) == null ? void 0 : _b.includes(df.fieldtype)) && !["Read Only", "Table", "Table MultiSelect"].includes(df.fieldtype) && visible($(cell)[0]) && !((_d = (_c = field == null ? void 0 : field.$input) == null ? void 0 : _c[0]) == null ? void 0 : _d.disabled) && !((_f = (_e = field == null ? void 0 : field.$input) == null ? void 0 : _e[0]) == null ? void 0 : _f.readOnly) && (!(field == null ? void 0 : field.get_status) || field.get_status() === "Write");
        }
      );
    };
    $('<style id="retail-keyboard-style">.retail-keyboard-selected{outline:2px solid var(--primary,#2490ef)!important;outline-offset:-2px;background-color:var(--control-bg,#f4f5f6)}</style>').appendTo(document.head);
    const clearSelection = () => {
      $(".retail-keyboard-selected").each(function() {
        const previous = $(this).data("retail-keyboard-tabindex");
        if (previous == null)
          $(this).removeAttr("tabindex");
        else
          $(this).attr("tabindex", previous);
      }).removeClass("retail-keyboard-selected");
      selected = null;
    };
    const select = (row, name) => {
      var _a;
      if (!expanded(row))
        row.toggle_editable_row(false);
      const entry = controls(row).find(({ df }) => df.fieldname === name);
      if (!entry) {
        clearSelection();
        return;
      }
      clearSelection();
      selected = { grid: row.grid, name: row.doc.name, fieldname: name };
      $(entry.cell).data("retail-keyboard-tabindex", (_a = $(entry.cell).attr("tabindex")) != null ? _a : null).addClass("retail-keyboard-selected").attr("tabindex", "-1")[0].focus({ preventScroll: true });
      reveal($(entry.cell)[0]);
    };
    const edit = (row, name) => {
      var _a;
      clearSelection();
      if (!expanded(row)) {
        if (row.grid.allow_on_grid_editing())
          row.activate();
        else {
          row.toggle_view(true);
          const token = generation;
          setTimeout(() => {
            var _a2;
            if (token === generation && expanded(row) && current() === row.grid.frm) {
              focus((_a2 = controls(row).find(({ df }) => df.fieldname === name)) == null ? void 0 : _a2.field);
            }
          }, 550);
        }
      }
      focus((_a = controls(row).find(({ df }) => df.fieldname === name)) == null ? void 0 : _a.field);
    };
    $(document).on("grid-row-render.retailKeyboard", (event, row) => {
      if ((selected == null ? void 0 : selected.grid) !== row.grid || selected.name !== row.doc.name)
        return;
      const name = selected.fieldname;
      queueMicrotask(() => {
        if ((selected == null ? void 0 : selected.name) === row.doc.name && selected.fieldname === name && (document.activeElement === document.body || document.activeElement.classList.contains("retail-keyboard-selected"))) {
          select(row.grid.grid_rows_by_docname[row.doc.name] || row, name);
        }
      });
    });
    async function settled(frm, field, token, scan = false) {
      var _a;
      pending++;
      try {
        await Promise.resolve();
        if (scan && ((_a = api.doctypes[frm.doctype]) == null ? void 0 : _a.when_scan_complete)) {
          await api.doctypes[frm.doctype].when_scan_complete(frm);
        }
        if (!scan) {
          for (let elapsed = 0; elapsed < 3e4; elapsed += 16) {
            if (token !== generation || current() !== frm || blocked(false))
              return false;
            if (!frozen() && !(field == null ? void 0 : field.inside_change_event))
              return true;
            await new Promise((resolve) => setTimeout(resolve, 16));
          }
          return false;
        }
        let quiet = 0;
        for (let elapsed = 0; elapsed < 3e4; elapsed += 100) {
          await new Promise((resolve) => setTimeout(resolve, 100));
          if (token !== generation || current() !== frm || blocked(false))
            return false;
          quiet = frozen() || frappe.request.ajax_count || (field == null ? void 0 : field.inside_change_event) || frappe.flags.trigger_from_barcode_scanner ? 0 : quiet + 100;
          if (quiet >= 700)
            return true;
        }
        return false;
      } finally {
        pending--;
      }
    }
    const headerFields = (frm) => (frm.fields || Object.values(frm.fields_dict)).filter((field) => {
      var _a;
      return !field.grid && !field.df.hidden && !field.df.hidden_due_to_dependency && !field.df.read_only && !field.df.disabled && !field.df.is_virtual && enabled((_a = field.$input) == null ? void 0 : _a[0]) && (!field.get_status || field.get_status() === "Write");
    });
    async function commit(frm, field, target, token, requireValue = true) {
      var _a;
      const value = (field == null ? void 0 : field.get_input_value) ? field.get_input_value() : target.value;
      if (requireValue && (field == null ? void 0 : field.df.reqd) && (value == null || String(value).trim() === "")) {
        (_a = frappe.show_alert) == null ? void 0 : _a.call(frappe, { message: __("Please fill {0}", [__(field.df.label || field.df.fieldname)]), indicator: "orange" });
        focus(field);
        return false;
      }
      try {
        if ((field == null ? void 0 : field.inside_change_event) && !await settled(frm, field, token))
          return false;
        if (field == null ? void 0 : field.parse_validate_and_set_in_model) {
          await field.parse_validate_and_set_in_model(value);
        }
        if (token !== generation || current() !== frm)
          return false;
        if ((field == null ? void 0 : field.df.invalid) || requireValue && (field == null ? void 0 : field.df.reqd) && (field == null ? void 0 : field.get_model_value) && [field.get_model_value()].some((v) => v == null || v === "")) {
          focus(field);
          return false;
        }
        if (token !== generation || current() !== frm)
          return false;
        target.blur();
        return await settled(frm, field, token);
      } catch (error) {
        if (token === generation && current() === frm)
          focus(field);
        console.error(error);
        return false;
      }
    }
    function firstCell(row) {
      var _a;
      const entries = controls(row);
      const preferred = (_a = api.children[row.doc.doctype]) == null ? void 0 : _a.first_field;
      return entries.find(({ df }) => df.fieldname === preferred) || entries[0];
    }
    async function focusItems(frm, token) {
      var _a, _b, _c, _d;
      const grid = (_b = frm.fields_dict[((_a = api.doctypes[frm.doctype]) == null ? void 0 : _a.items_field) || "items"]) == null ? void 0 : _b.grid;
      if (!(grid == null ? void 0 : grid.is_editable()) || ((_c = api.children[grid.df.options]) == null ? void 0 : _c.enabled) === false)
        return;
      let row = (_d = grid.grid_rows) == null ? void 0 : _d.find((row2) => row2.doc && firstCell(row2));
      if (!row && !grid.get_data().length && !grid.cannot_add_rows && !grid.df.cannot_add_rows) {
        const doc = grid.add_new_row(null, null, false);
        if (!doc || !await settled(frm, null, token))
          return;
        row = grid.grid_rows_by_docname[doc.name];
      }
      const first = row && firstCell(row);
      if (first)
        edit(row, first.df.fieldname);
    }
    async function nextCell(frm, row, name, token) {
      const grid = row.grid;
      const live = grid.grid_rows_by_docname[row.doc.name];
      if (!live || !grid.is_editable())
        return;
      const entries = controls(live);
      const index = entries.findIndex(({ df }) => df.fieldname === name);
      if (index < 0)
        return;
      if (entries[index + 1])
        return edit(live, entries[index + 1].df.fieldname);
      if (!live.doc.item_code && grid.docfields.some((df) => df.fieldname === "item_code")) {
        const first2 = firstCell(live);
        if (first2)
          edit(live, first2.df.fieldname);
        return;
      }
      if (grid.cannot_add_rows || grid.df.cannot_add_rows)
        return;
      if (expanded(live))
        live.toggle_view(false);
      const doc = grid.add_new_row(live.doc.idx + 1, null, false);
      if (!doc || !await settled(frm, null, token))
        return;
      if (!grid.grid_rows_by_docname[doc.name] && grid.grid_pagination) {
        const size = grid.grid_pagination.page_length;
        if (size)
          grid.grid_pagination.go_to_page(Math.ceil(doc.idx / size));
      }
      const added = grid.grid_rows_by_docname[doc.name];
      const first = added && firstCell(added);
      if (first)
        edit(added, first.df.fieldname);
    }
    function arrowEntries(frm) {
      const headers = new Set(headerFields(frm));
      return (frm.fields || Object.values(frm.fields_dict)).flatMap((field) => {
        var _a, _b, _c;
        const grid = field.grid;
        if (!grid)
          return headers.has(field) ? [{ field }] : [];
        if (field.df.hidden || field.df.hidden_due_to_dependency || !grid.is_editable() || ((_a = api.children[grid.df.options]) == null ? void 0 : _a.enabled) === false)
          return [];
        const entries = (grid.grid_rows || []).flatMap((row) => row.doc ? controls(row).map(({ df }) => ({ row, name: df.fieldname })) : []);
        if (!entries.length && !grid.get_data().length && field.df.fieldname === (((_b = api.doctypes[frm.doctype]) == null ? void 0 : _b.items_field) || "items") && !grid.cannot_add_rows && !grid.df.cannot_add_rows && visible(((_c = field.$wrapper) == null ? void 0 : _c[0]) || field.wrapper))
          return [{ grid }];
        return entries;
      });
    }
    function entryRect(entry) {
      var _a, _b, _c, _d;
      const element = ((_b = (_a = entry.field) == null ? void 0 : _a.$input) == null ? void 0 : _b[0]) || (entry.grid ? $(entry.grid.wrapper)[0] : $((_c = controls(entry.row).find(({ df }) => df.fieldname === entry.name)) == null ? void 0 : _c.cell)[0]);
      return (_d = element == null ? void 0 : element.getBoundingClientRect) == null ? void 0 : _d.call(element);
    }
    function arrowDestination(frm, row, name, field, key) {
      const entries = arrowEntries(frm);
      const origin = entries.find((entry) => row ? entry.row === row && entry.name === name : entry.field === field);
      if (!origin)
        return;
      const from = entryRect(origin);
      if (!from)
        return;
      const horizontal = ["ArrowLeft", "ArrowRight"].includes(key);
      const forward = ["ArrowDown", "ArrowRight"].includes(key);
      const center = (rect, axis) => axis === "x" ? (rect.left + rect.right) / 2 : (rect.top + rect.bottom) / 2;
      let best, bestScore = Infinity;
      for (const entry of entries) {
        if (entry === origin)
          continue;
        const rect = entryRect(entry);
        if (!rect || rect.right <= rect.left || rect.bottom <= rect.top)
          continue;
        const overlap = horizontal ? Math.min(from.bottom, rect.bottom) - Math.max(from.top, rect.top) : Math.min(from.right, rect.right) - Math.max(from.left, rect.left);
        if (overlap <= 0)
          continue;
        const delta = center(rect, horizontal ? "x" : "y") - center(from, horizontal ? "x" : "y");
        if (forward ? delta <= 1 : delta >= -1)
          continue;
        const deviation = Math.abs(center(rect, horizontal ? "y" : "x") - center(from, horizontal ? "y" : "x"));
        const score = Math.abs(delta) + deviation * 0.25;
        if (score < bestScore) {
          best = entry;
          bestScore = score;
        }
      }
      return best;
    }
    async function focusArrowEntry(next, frm, token) {
      if (next.grid)
        return focusItems(frm, token);
      if (next.row) {
        const live = next.row.grid.grid_rows_by_docname[next.row.doc.name];
        if (live)
          edit(live, next.name);
      } else
        focus(next.field);
    }
    document.addEventListener("focusin", (event) => {
      var _a;
      const frm = current();
      if (!frm || ((_a = api.doctypes[frm.doctype]) == null ? void 0 : _a.enabled) === false || window.cur_dialog || !frm.wrapper.contains(event.target))
        return;
      queueMicrotask(() => {
        if (document.activeElement === event.target && current() === frm)
          reveal(event.target);
      });
    }, true);
    document.addEventListener("pointerdown", () => {
      generation++;
      clearSelection();
    }, true);
    frappe.router.on("change", () => {
      generation++;
      clearSelection();
    });
    document.addEventListener("keydown", (event) => {
      var _a, _b, _c, _d, _e, _f;
      const repeatedEnter = event.repeat && event.key === "Enter";
      const token = repeatedEnter ? generation : ++generation;
      const frm = current();
      if (!frm || ((_a = api.doctypes[frm.doctype]) == null ? void 0 : _a.enabled) === false || event.isComposing || event.keyCode === 229)
        return;
      if (event.ctrlKey || event.metaKey || event.altKey || event.key === "Tab")
        return;
      if (event.shiftKey && event.key !== "Enter")
        return;
      if (!["Enter", "ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight", "Escape"].includes(event.key))
        return;
      const target = event.target;
      const arrow = event.key.startsWith("Arrow");
      const returnToScan = event.shiftKey && event.key === "Enter";
      const blockedHere = returnToScan ? window.cur_dialog || frozen() || $(".modal:visible").length : blocked();
      if (blockedHere)
        return;
      if (!returnToScan && (!frm.wrapper.contains(target) || target.closest(arrow ? "button,a,[role=button],[contenteditable]:not([contenteditable=false])" : native)))
        return;
      if (returnToScan && target !== document.body && !frm.wrapper.contains(target))
        return;
      if (repeatedEnter) {
        consume(event);
        return;
      }
      const scan = scanField(frm);
      if (event.key === "Enter" && !event.shiftKey && target === (scan == null ? void 0 : scan.$input[0])) {
        settled(frm, scan, token, true).then((ok) => ok && focus(scanField(frm))).catch(console.error);
        return;
      }
      const row = $(target).closest(".grid-row").data("grid_row");
      const fields = (row == null ? void 0 : row.doc) ? controls(row) : [];
      const entry = fields.find(({ field: field2, cell }) => {
        var _a2, _b2;
        return ((_a2 = field2 == null ? void 0 : field2.$input) == null ? void 0 : _a2[0]) === target || $(cell)[0] === target || ((_b2 = $(cell)[0]) == null ? void 0 : _b2.contains(target));
      });
      const field = (entry == null ? void 0 : entry.field) || headerFields(frm).find((field2) => field2.$input[0] === target);
      if (!returnToScan && row && (((_b = api.children[row.doc.doctype]) == null ? void 0 : _b.enabled) === false || !row.grid.is_editable()))
        return;
      if (returnToScan) {
        if (!scan)
          return;
        consume(event);
        (_c = field == null ? void 0 : field.awesomplete) == null ? void 0 : _c.close();
        (_d = field == null ? void 0 : field.datepicker) == null ? void 0 : _d.hide();
        (async () => {
          if (field && !await commit(frm, field, target, token, false))
            return;
          if (row && expanded(row))
            row.toggle_view(false);
          clearSelection();
          focus(scanField(frm));
        })().catch(console.error);
        return;
      }
      if (event.key === "Enter" && target.type === "checkbox" && field && enabled(target)) {
        consume(event);
        target.click();
        return;
      }
      if (arrow && (entry || field)) {
        const next = arrowDestination(frm, (row == null ? void 0 : row.doc) ? row : null, entry == null ? void 0 : entry.df.fieldname, field, event.key);
        consume(event);
        if (!next)
          return;
        (async () => {
          var _a2;
          if (((_a2 = field == null ? void 0 : field.$input) == null ? void 0 : _a2[0]) === target && !await commit(frm, field, target, token, false))
            return;
          await focusArrowEntry(next, frm, token);
        })().catch(console.error);
        return;
      }
      if ((row == null ? void 0 : row.doc) && entry) {
        const name = entry.df.fieldname;
        const isInput = ((_f = (_e = entry.field) == null ? void 0 : _e.$input) == null ? void 0 : _f[0]) === target;
        if (event.key === "Escape") {
          consume(event);
          target.blur();
          select(row, name);
          return;
        }
        consume(event);
        if (!isInput)
          return edit(row, name);
        (async () => {
          if (await commit(frm, field, target, token))
            await nextCell(frm, row, name, token);
        })().catch(console.error);
        return;
      }
      if (event.key !== "Enter" || !field)
        return;
      consume(event);
      (async () => {
        if (!await commit(frm, field, target, token))
          return;
        const headers = headerFields(frm);
        const index = headers.findIndex((candidate) => candidate.df.fieldname === field.df.fieldname);
        const next = headers.slice(index + 1).find((candidate) => candidate.df.reqd && candidate !== scanField(frm));
        if (next)
          return focus(next);
        if (scanField(frm))
          return focus(scanField(frm));
        await focusItems(frm, token);
      })().catch(console.error);
    }, true);
  })();

  // ../retail/retail/public/js/document_code_list.js
  (() => {
    var _a, _b, _c;
    frappe.provide("retail");
    function code_field(listview) {
      if (listview.meta.fields.some((df) => df.fieldname === "custom_document_code")) {
        return "custom_document_code";
      }
      return listview.doctype === "Item" ? "item_code" : "name";
    }
    function code_label() {
      return __("ID");
    }
    function add_code_filter(listview) {
      var _a2, _b2;
      const fieldname = code_field(listview);
      const label = code_label(listview);
      const fields = listview.page.fields_dict;
      if (fieldname === "custom_document_code" && fields.name) {
        const identity_label = listview.doctype === "User" ? __("Login") : __("Name");
        fields.name.df.label = identity_label;
        (_a2 = fields.name.$input) == null ? void 0 : _a2.attr("placeholder", identity_label);
      }
      const existing = fields[fieldname];
      const value = (existing == null ? void 0 : existing.get_value()) || "";
      const wrapper = listview.filter_area.standard_filters_wrapper;
      if ((existing == null ? void 0 : existing.df.fieldtype) === "Autocomplete") {
        existing.df.label = label;
        (_b2 = existing.$input) == null ? void 0 : _b2.attr("placeholder", label);
        existing.$wrapper.find(".control-label").text(label);
        existing.$wrapper.prependTo(wrapper);
        return;
      }
      existing == null ? void 0 : existing.$wrapper.remove();
      delete fields[fieldname];
      const control = listview.page.add_field({
        fieldname,
        fieldtype: "Autocomplete",
        label,
        condition: "like",
        ignore_validation: true,
        onchange: () => listview.filter_area.debounced_refresh_list_view()
      }, wrapper);
      control.set_input(value);
      control.$wrapper.prependTo(wrapper);
      let request = 0;
      const suggest = frappe.utils.debounce(async () => {
        const sequence = ++request;
        const term = control.$input.val() || "";
        const rows = await frappe.db.get_list(listview.doctype, {
          fields: [fieldname],
          filters: [[fieldname, "like", `%${term}%`]],
          order_by: `${fieldname} asc`,
          limit: 30
        });
        if (sequence !== request || term !== control.$input.val())
          return;
        control.set_data(rows.filter((row) => row[fieldname]).map((row) => ({
          value: row[fieldname],
          label: frappe.utils.escape_html(row[fieldname])
        })));
        if (control.$input.is(":focus"))
          control.awesomplete.evaluate();
      }, 200);
      control.$input.on("input focus", suggest);
      listview.page.show_form();
    }
    function install_list_patch() {
      var _a2;
      if (!((_a2 = frappe.views) == null ? void 0 : _a2.ListView))
        return;
      const prototype = frappe.views.ListView.prototype;
      if (prototype.retail_document_codes)
        return;
      prototype.retail_document_codes = true;
      const set_fields = prototype.set_fields;
      prototype.set_fields = async function() {
        const fieldname = code_field(this);
        this.settings.add_fields = [.../* @__PURE__ */ new Set([...this.settings.add_fields || [], fieldname])];
        return set_fields.call(this);
      };
      const refresh = prototype.refresh;
      prototype.refresh = async function(...args) {
        if (code_field(this) === "custom_document_code") {
          await frappe.call("retail.document_codes.ensure_codes", { doctype: this.doctype });
        }
        return refresh.apply(this, args);
      };
      const setup_columns = prototype.setup_columns;
      prototype.setup_columns = function() {
        setup_columns.call(this);
        const fieldname = code_field(this);
        this.columns = this.columns.filter((column) => {
          var _a3, _b2, _c2;
          if (((_a3 = column.df) == null ? void 0 : _a3.fieldname) === fieldname)
            return false;
          if (((_b2 = column.df) == null ? void 0 : _b2.fieldname) === "name" && fieldname === "item_code")
            return false;
          if (((_c2 = column.df) == null ? void 0 : _c2.fieldname) === "name" && fieldname === "custom_document_code") {
            if (this.doctype !== "User" && this.meta.title_field && this.meta.title_field !== "name")
              return false;
            column.df = __spreadProps(__spreadValues({}, column.df), { label: this.doctype === "User" ? __("Login") : __("Name") });
          }
          return true;
        });
        const subject = this.columns.find((column) => column.type === "Subject");
        if (subject)
          subject.type = "Field";
        this.columns.unshift({
          type: "Subject",
          df: { fieldname, label: code_label(this), fieldtype: "Data" }
        });
      };
      const setup_view = prototype.setup_view;
      prototype.setup_view = function() {
        setup_view.call(this);
        add_code_filter(this);
      };
    }
    function install_form_patch() {
      var _a2, _b2;
      if (!((_b2 = (_a2 = frappe.ui) == null ? void 0 : _a2.form) == null ? void 0 : _b2.Toolbar))
        return;
      const prototype = frappe.ui.form.Toolbar.prototype;
      if (prototype.retail_document_codes)
        return;
      prototype.retail_document_codes = true;
      const set_title = prototype.set_title;
      prototype.set_title = function() {
        var _a3;
        set_title.call(this);
        const code = (_a3 = this.frm.doc) == null ? void 0 : _a3.custom_document_code;
        if (code && !this.frm.is_new()) {
          if (!this.page.$sub_title_area.length) {
            this.page.$sub_title_area = this.page.$title_area.find(".sub-heading");
          }
          this.page.set_title_sub(frappe.utils.escape_html(code));
          this.page.$sub_title_area.css("cursor", "copy").off("click").on("click.retail_code", (event) => {
            event.stopImmediatePropagation();
            frappe.utils.copy_to_clipboard(code);
          });
        }
      };
    }
    function install() {
      install_list_patch();
      install_form_patch();
    }
    install();
    if ((!((_a = frappe.views) == null ? void 0 : _a.ListView) || !((_c = (_b = frappe.ui) == null ? void 0 : _b.form) == null ? void 0 : _c.Toolbar)) && !retail.document_codes_init_pending) {
      retail.document_codes_init_pending = true;
      $(function() {
        retail.document_codes_init_pending = false;
        install();
      });
    }
  })();

  // ../retail/retail/public/js/automatic_series_visibility.js
  (() => {
    function install() {
      var _a, _b, _c, _d;
      if (!((_a = window.erpnext) == null ? void 0 : _a.toggle_naming_series) || !((_c = (_b = window.frappe) == null ? void 0 : _b.boot) == null ? void 0 : _c.retail_native_code_doctypes) || !((_d = frappe.ui) == null ? void 0 : _d.form)) {
        setTimeout(install, 150);
        return;
      }
      if (erpnext.toggle_naming_series.__retail_automatic_series)
        return;
      const managed = new Set(frappe.boot.retail_native_code_doctypes);
      const original = erpnext.toggle_naming_series;
      erpnext.toggle_naming_series = function(...args) {
        const frm = window.cur_frm;
        if (frm && managed.has(frm.doctype) && frm.fields_dict.naming_series) {
          frm.toggle_display("naming_series", false);
          return;
        }
        return original.apply(this, args);
      };
      erpnext.toggle_naming_series.__retail_automatic_series = true;
      for (const doctype of managed) {
        frappe.ui.form.on(doctype, {
          refresh(frm) {
            if (frm.fields_dict.naming_series)
              frm.toggle_display("naming_series", false);
          }
        });
      }
    }
    install();
  })();

  // ../retail/retail/public/js/list_column_widths.js
  (() => {
    const clamp = (width) => Math.max(70, Math.min(1200, Math.round(width)));
    const key = (view) => `retail:list-widths:v1:${frappe.session.user}:${view.doctype}`;
    const column_key = (column) => {
      var _a;
      return `${column.type}:${column.balance_field || ((_a = column.df) == null ? void 0 : _a.fieldname) || column.type}`;
    };
    const order_key = (view) => `${key(view)}:order`;
    function column_order(view) {
      if (!view._retail_list_order) {
        try {
          const saved = JSON.parse(localStorage.getItem(order_key(view)) || "[]");
          view._retail_list_order = Array.isArray(saved) ? [...new Set(saved.filter((value) => typeof value === "string"))] : [];
        } catch (e) {
          view._retail_list_order = [];
        }
      }
      const available = view.columns.map(column_key);
      if (!view._retail_list_order.length) {
        const is_status = (column) => {
          var _a;
          return column.type === "Status" || ((_a = column.df) == null ? void 0 : _a.fieldname) === "status";
        };
        return [
          ...view.columns.filter((column) => !is_status(column)),
          ...view.columns.filter(is_status)
        ].map(column_key);
      }
      return [...view._retail_list_order.filter((name) => available.includes(name)), ...available.filter((name) => !view._retail_list_order.includes(name))];
    }
    function save_order(view) {
      try {
        localStorage.setItem(order_key(view), JSON.stringify(view._retail_list_order));
      } catch (e) {
        frappe.show_alert({ message: __("Column order could not be saved in this browser."), indicator: "orange" });
      }
    }
    function move_column(view, source, target) {
      const order = column_order(view);
      if (source === target || !order.includes(source) || !order.includes(target))
        return;
      const source_index = order.indexOf(source), target_index = order.indexOf(target);
      [order[source_index], order[target_index]] = [order[target_index], order[source_index]];
      view._retail_list_order = order;
      save_order(view);
      apply(view);
    }
    function preferences(view) {
      if (view._retail_list_widths)
        return view._retail_list_widths;
      try {
        const saved = JSON.parse(localStorage.getItem(key(view)) || "{}");
        view._retail_list_widths = Object.fromEntries(Object.entries(saved || {}).filter(([, value]) => Number.isFinite(value)).map(([name, value]) => [name, clamp(value)]));
      } catch (e) {
        view._retail_list_widths = {};
      }
      return view._retail_list_widths;
    }
    function save(view) {
      try {
        localStorage.setItem(key(view), JSON.stringify(preferences(view)));
      } catch (e) {
        frappe.show_alert({ message: __("Column widths could not be saved in this browser."), indicator: "orange" });
      }
    }
    function default_width(column) {
      const df = column.df || {};
      if (column.type === "Status")
        return 110;
      if (column.type === "Subject" && ["name", "item_code", "custom_document_code"].includes(df.fieldname))
        return 140;
      if (frappe.model.is_numeric_field(df))
        return 145;
      return 190;
    }
    function apply(view) {
      if (view.view_name !== "List" || !view.$result || !view.columns)
        return;
      const root = view.$result[0];
      const head = root.querySelector(".list-row-head > .level-left:not(.checkbox-actions)");
      if (!head)
        return;
      view.$result.addClass("retail-list-widths");
      const saved = preferences(view);
      const order = column_order(view);
      const headers = Array.from(head.children).filter((el) => el.classList.contains("list-row-col"));
      const widths = view.columns.map((column) => saved[column_key(column)] || default_width(column));
      const visible = headers.map((el, index) => ({ el, index })).filter(({ el }) => getComputedStyle(el).display !== "none");
      const header_style = getComputedStyle(head.parentElement);
      const root_style = getComputedStyle(root);
      const pixels = (value) => parseFloat(value) || 0;
      const gutter = pixels(header_style.marginLeft) + pixels(header_style.marginRight);
      const available_width = Math.max(0, root.clientWidth - pixels(root_style.paddingLeft) - pixels(root_style.paddingRight) - gutter);
      root.style.setProperty("--retail-list-gutter", `${gutter}px`);
      const spare = Math.max(0, available_width - 170 - visible.reduce((sum, { index }) => sum + widths[index] + 15, 0));
      const flexible = visible.filter(({ index }) => {
        var _a;
        return !saved[column_key(view.columns[index])] && !frappe.model.is_numeric_field(view.columns[index].df || {}) && view.columns[index].type !== "Status" && !["name", "item_code", "custom_document_code"].includes((_a = view.columns[index].df) == null ? void 0 : _a.fieldname);
      });
      for (const { index } of flexible)
        widths[index] += spare / flexible.length;
      root.style.setProperty("--retail-list-width", `${Math.floor(170 + visible.reduce((sum, { index }) => sum + widths[index] + 15, 0))}px`);
      for (const row of root.querySelectorAll(".list-row > .level-left, .list-row-head > .level-left:not(.checkbox-actions)")) {
        const cells = Array.from(row.children).filter((el) => el.classList.contains("list-row-col"));
        cells.forEach((cell, index) => {
          if (widths[index])
            cell.style.setProperty("--retail-list-column-width", `${widths[index]}px`);
          if (view.columns[index])
            cell.style.setProperty("--retail-list-column-order", order.indexOf(column_key(view.columns[index])));
        });
      }
      headers.forEach((cell, index) => {
        var _a, _b;
        if (!view.columns[index] || cell.querySelector(".retail-list-resize"))
          return;
        const name = column_key(view.columns[index]);
        const grip = document.createElement("span");
        grip.className = "retail-list-reorder";
        grip.textContent = "\u22EE\u22EE";
        grip.draggable = true;
        grip.tabIndex = 0;
        grip.setAttribute("role", "button");
        grip.setAttribute("aria-label", __("Move {0}", [((_a = view.columns[index].df) == null ? void 0 : _a.label) || view.columns[index].type]));
        grip.title = __("Drag to move this column. Use arrow keys to move one position.");
        grip.addEventListener("click", (event) => {
          event.preventDefault();
          event.stopPropagation();
        });
        grip.addEventListener("dragstart", (event) => {
          if (window.innerWidth < 768) {
            event.preventDefault();
            return;
          }
          event.stopPropagation();
          view._retail_drag_column = name;
          event.dataTransfer.effectAllowed = "move";
          event.dataTransfer.setData("text/plain", name);
        });
        const clear_drag = () => {
          view._retail_drag_column = null;
          for (const header of headers)
            header.classList.remove("retail-list-drop-target");
        };
        grip.addEventListener("dragend", clear_drag);
        cell.addEventListener("dragover", (event) => {
          if (!view._retail_drag_column || view._retail_drag_column === name)
            return;
          event.preventDefault();
          event.stopPropagation();
          event.dataTransfer.dropEffect = "move";
          cell.classList.add("retail-list-drop-target");
        });
        cell.addEventListener("dragleave", () => cell.classList.remove("retail-list-drop-target"));
        cell.addEventListener("drop", (event) => {
          if (!view._retail_drag_column)
            return;
          event.preventDefault();
          event.stopPropagation();
          move_column(view, view._retail_drag_column, name);
          clear_drag();
        });
        grip.addEventListener("keydown", (event) => {
          if (!["ArrowLeft", "ArrowRight"].includes(event.key))
            return;
          event.preventDefault();
          event.stopPropagation();
          const visible_order = column_order(view).filter((key2) => {
            const index2 = view.columns.findIndex((column) => column_key(column) === key2);
            return headers[index2] && getComputedStyle(headers[index2]).display !== "none";
          });
          const direction = getComputedStyle(root).direction === "rtl" ? -1 : 1;
          const step = (event.key === "ArrowRight" ? 1 : -1) * direction;
          const target = visible_order[visible_order.indexOf(name) + step];
          if (!target)
            return;
          move_column(view, name, target);
        });
        cell.append(grip);
        const handle = document.createElement("span");
        handle.className = "retail-list-resize";
        handle.tabIndex = 0;
        handle.setAttribute("role", "separator");
        handle.setAttribute("aria-orientation", "vertical");
        handle.setAttribute("aria-label", __("Resize {0}", [((_b = view.columns[index].df) == null ? void 0 : _b.label) || view.columns[index].type]));
        handle.title = __("Drag to resize. Use arrow keys to adjust. Double-click to reset this column.");
        const change = (width) => {
          preferences(view)[column_key(view.columns[index])] = clamp(width);
          apply(view);
        };
        handle.addEventListener("click", (event) => {
          event.preventDefault();
          event.stopPropagation();
        });
        handle.addEventListener("dblclick", (event) => {
          event.stopPropagation();
          delete preferences(view)[column_key(view.columns[index])];
          save(view);
          apply(view);
        });
        handle.addEventListener("keydown", (event) => {
          if (!["ArrowLeft", "ArrowRight"].includes(event.key))
            return;
          event.preventDefault();
          event.stopPropagation();
          const direction = getComputedStyle(root).direction === "rtl" ? -1 : 1;
          change(cell.getBoundingClientRect().width + (event.key === "ArrowRight" ? 10 : -10) * direction);
          save(view);
        });
        handle.addEventListener("pointerdown", (event) => {
          if (event.button !== 0)
            return;
          event.preventDefault();
          event.stopPropagation();
          const start = event.clientX, width = cell.getBoundingClientRect().width;
          const direction = getComputedStyle(root).direction === "rtl" ? -1 : 1;
          handle.setPointerCapture(event.pointerId);
          const move = (e) => change(width + (e.clientX - start) * direction);
          const finish = () => {
            handle.removeEventListener("pointermove", move);
            handle.removeEventListener("pointerup", finish);
            handle.removeEventListener("pointercancel", finish);
            save(view);
          };
          handle.addEventListener("pointermove", move);
          handle.addEventListener("pointerup", finish);
          handle.addEventListener("pointercancel", finish);
        });
        cell.append(handle);
      });
      if (!view._retail_width_controls) {
        view._retail_width_controls = true;
        view.page.add_menu_item(__("Reset Column Widths"), () => {
          view._retail_list_widths = {};
          save(view);
          apply(view);
        });
        view.page.add_menu_item(__("Reset Column Order"), () => {
          view._retail_list_order = [];
          save_order(view);
          apply(view);
        });
        if (window.ResizeObserver) {
          view._retail_width_observer = new ResizeObserver(() => apply(view));
          view._retail_width_observer.observe(root);
        }
      }
    }
    function install() {
      var _a, _b;
      const prototype = (_b = (_a = frappe.views) == null ? void 0 : _a.ListView) == null ? void 0 : _b.prototype;
      if (!prototype || prototype._retail_widths_installed)
        return;
      prototype._retail_widths_installed = true;
      const show_list_settings = prototype.show_list_settings;
      prototype.show_list_settings = async function(...args) {
        if (this._retail_loading_list_settings)
          return;
        this._retail_loading_list_settings = true;
        try {
          const response = await frappe.call({
            method: "frappe.desk.form.load.getdoctype",
            type: "GET",
            args: { doctype: "List View Settings" }
          });
          if (response.exc)
            return;
          frappe.model.set_in_localstorage("List View Settings", response.docs);
          return show_list_settings.apply(this, args);
        } finally {
          this._retail_loading_list_settings = false;
        }
      };
      for (const method of ["render_header", "render_list"]) {
        const original = prototype[method];
        prototype[method] = function(...args) {
          const result = original.apply(this, args);
          apply(this);
          return result;
        };
      }
    }
    install();
    $(install);
  })();

  // ../retail/retail/public/js/retail_navigation.js
  (function() {
    var _a, _b, _c;
    if (window.retailNavigationLoaded)
      return;
    window.retailNavigationLoaded = true;
    if (window.location.pathname === "/app/business-home-desk") {
      window.location.replace("/app/business-home");
      return;
    }
    const DEBUG = false;
    const debugLog = (...args) => DEBUG && console.log(...args);
    debugLog("retail_navigation: script loaded", { host: window.location.host, readyState: document.readyState });
    const OPEN_WORK_STORAGE_KEY = "retail_open_work_tabs_v3";
    const OPEN_SIDEBAR_STORAGE_KEY = "retail_open_sidebar_groups_v1";
    const OPEN_WORK_TTL_MS = 12 * 60 * 60 * 1e3;
    const ICON_MAP = {
      "loyalty program list": { icon: "fa fa-list", cls: "color-sales" },
      "loyalty program": { icon: "fa fa-star", cls: "color-sales" },
      "loyalty program report": { icon: "fa fa-bar-chart", cls: "color-sales" },
      "loyalty point entry": { icon: "fa fa-book", cls: "color-sales" },
      "loyalty point entry report": { icon: "fa fa-line-chart", cls: "color-sales" },
      "promotions": { icon: "fa fa-gift", cls: "color-sales" },
      "promo price": { icon: "fa fa-tag", cls: "color-purchase" },
      "buy x get y promotion": { icon: "fa fa-gift", cls: "color-purchase" },
      "gift voucher promotion": { icon: "fa fa-gift", cls: "color-purchase" },
      "gift voucher ledger": { icon: "fa fa-book", cls: "color-purchase" },
      "voucher cards": { icon: "fa fa-credit-card", cls: "color-purchase" },
      "voucher card batch": { icon: "fa fa-credit-card", cls: "color-purchase" },
      "pricing rule": { icon: "fa fa-percent", cls: "color-purchase" },
      "promotional scheme": { icon: "fa fa-tags", cls: "color-purchase" },
      "home": { icon: "fa fa-home", cls: "color-settings" },
      "business home": { icon: "fa fa-home", cls: "color-settings" },
      "items": { icon: "fa fa-cubes", cls: "color-items" },
      "sales": { icon: "fa fa-shopping-cart", cls: "color-sales" },
      "pos": { icon: "fa fa-desktop", cls: "color-sales" },
      "hr": { icon: "fa fa-users", cls: "color-hr" },
      "recruitment": { icon: "fa fa-user-plus", cls: "color-hr-recruitment" },
      "employee lifecycle": { icon: "fa fa-random", cls: "color-hr-lifecycle" },
      "performance": { icon: "fa fa-star", cls: "color-hr-performance" },
      "shift & attendance": { icon: "fa fa-calendar-check-o", cls: "color-hr-attendance" },
      "expense claims": { icon: "fa fa-money", cls: "color-hr-expenses" },
      "leaves": { icon: "fa fa-calendar", cls: "color-hr-leaves" },
      "purchases": { icon: "fa fa-cart-arrow-down", cls: "color-purchase" },
      "stocks": { icon: "fa fa-archive", cls: "color-stock" },
      "manufacturing": { icon: "fa fa-industry", cls: "color-manufacturing" },
      "van sales": { icon: "fa fa-truck", cls: "color-sales" },
      "fleet": { icon: "fa fa-truck", cls: "color-sales" },
      "van fleet": { icon: "fa fa-truck", cls: "color-sales" },
      "van sales fleet link": { icon: "fa fa-truck", cls: "color-sales" },
      "driver": { icon: "fa fa-id-card-o", cls: "color-sales" },
      "van driver": { icon: "fa fa-id-card-o", cls: "color-sales" },
      "van sales driver link": { icon: "fa fa-id-card-o", cls: "color-sales" },
      "van session": { icon: "fa fa-clock-o", cls: "color-sales" },
      "van sessions": { icon: "fa fa-clock-o", cls: "color-sales" },
      "van sales sessions link": { icon: "fa fa-clock-o", cls: "color-sales" },
      "stock request": { icon: "fa fa-list-alt", cls: "color-stock" },
      "van stock request": { icon: "fa fa-list-alt", cls: "color-stock" },
      "van sales stock request link": { icon: "fa fa-list-alt", cls: "color-stock" },
      "van stock entries": { icon: "fa fa-exchange", cls: "color-stock" },
      "van sales stock entries link": { icon: "fa fa-exchange", cls: "color-stock" },
      "van stock view": { icon: "fa fa-cubes", cls: "color-stock" },
      "van sales stock view link": { icon: "fa fa-cubes", cls: "color-stock" },
      "van sales invoice": { icon: "fa fa-file-text", cls: "color-sales" },
      "van sales invoice link": { icon: "fa fa-file-text", cls: "color-sales" },
      "van payments": { icon: "fa fa-money", cls: "color-accounts" },
      "van sales payments link": { icon: "fa fa-money", cls: "color-accounts" },
      "van customers": { icon: "fa fa-users", cls: "color-sales" },
      "van sales customers link": { icon: "fa fa-users", cls: "color-sales" },
      "van items": { icon: "fa fa-cubes", cls: "color-items" },
      "van sales items link": { icon: "fa fa-cubes", cls: "color-items" },
      "van warehouses": { icon: "fa fa-archive", cls: "color-stock" },
      "van sales warehouses link": { icon: "fa fa-archive", cls: "color-stock" },
      "van sales reports": { icon: "fa fa-bar-chart", cls: "color-sales" },
      "van sales reports link": { icon: "fa fa-bar-chart", cls: "color-sales" },
      "van daily sales summary": { icon: "fa fa-bar-chart", cls: "color-sales" },
      "van daily stock summary": { icon: "fa fa-bar-chart", cls: "color-stock" },
      "van detailed sales summary": { icon: "fa fa-list-alt", cls: "color-sales" },
      "van profit report": { icon: "fa fa-line-chart", cls: "color-accounts" },
      "van wastage report": { icon: "fa fa-exclamation-triangle", cls: "color-stock" },
      "van outstanding collection summary": { icon: "fa fa-money", cls: "color-accounts" },
      "daily stock summary": { icon: "fa fa-bar-chart", cls: "color-stock" },
      "detailed sales summary": { icon: "fa fa-list-alt", cls: "color-sales" },
      "profit report": { icon: "fa fa-line-chart", cls: "color-accounts" },
      "wastage report": { icon: "fa fa-exclamation-triangle", cls: "color-stock" },
      "outstanding / collection summary": { icon: "fa fa-money", cls: "color-accounts" },
      "bom": { icon: "fa fa-sitemap", cls: "color-manufacturing" },
      "production plan": { icon: "fa fa-calendar-check-o", cls: "color-manufacturing" },
      "work orders": { icon: "fa fa-tasks", cls: "color-manufacturing" },
      "job cards": { icon: "fa fa-id-card-o", cls: "color-manufacturing" },
      "stock entries": { icon: "fa fa-exchange", cls: "color-manufacturing" },
      "quality inspection": { icon: "fa fa-check-square-o", cls: "color-manufacturing" },
      "manufacturing reports": { icon: "fa fa-line-chart", cls: "color-manufacturing" },
      "manufacturing setup": { icon: "fa fa-cogs", cls: "color-manufacturing" },
      "setup": { icon: "fa fa-cogs", cls: "color-manufacturing" },
      "manufacturing child reports": { icon: "fa fa-line-chart", cls: "color-manufacturing" },
      "manufacturing child setup": { icon: "fa fa-cogs", cls: "color-manufacturing" },
      "operations": { icon: "fa fa-cogs", cls: "color-manufacturing" },
      "workstations": { icon: "fa fa-building-o", cls: "color-manufacturing" },
      "routing": { icon: "fa fa-code-fork", cls: "color-manufacturing" },
      "bom creator": { icon: "fa fa-plus-square-o", cls: "color-manufacturing" },
      "manufacturing settings": { icon: "fa fa-sliders", cls: "color-manufacturing" },
      "bom stock report": { icon: "fa fa-bar-chart", cls: "color-manufacturing" },
      "work order stock report": { icon: "fa fa-bar-chart", cls: "color-manufacturing" },
      "open work orders": { icon: "fa fa-folder-open-o", cls: "color-manufacturing" },
      "work orders in progress": { icon: "fa fa-spinner", cls: "color-manufacturing" },
      "completed work orders": { icon: "fa fa-check-circle-o", cls: "color-manufacturing" },
      "work order summary": { icon: "fa fa-list-alt", cls: "color-manufacturing" },
      "job card summary": { icon: "fa fa-list-alt", cls: "color-manufacturing" },
      "production analytics": { icon: "fa fa-area-chart", cls: "color-manufacturing" },
      "accounts": { icon: "fa fa-university", cls: "color-accounts" },
      "reports": { icon: "fa fa-bar-chart", cls: "color-accounts" },
      "settings": { icon: "fa fa-cog", cls: "color-settings" },
      "material request": { icon: "fa fa-clipboard", cls: "color-purchase" },
      "material requests": { icon: "fa fa-clipboard", cls: "color-purchase" },
      "request for quotation": { icon: "fa fa-question-circle", cls: "color-purchase" },
      "request for quotations": { icon: "fa fa-question-circle", cls: "color-purchase" },
      "supplier quotation": { icon: "fa fa-comments-o", cls: "color-purchase" },
      "supplier quotations": { icon: "fa fa-comments-o", cls: "color-purchase" },
      "purchase orders": { icon: "fa fa-file-text", cls: "color-purchase" },
      "purchase receipts": { icon: "fa fa-file-text", cls: "color-purchase" },
      "purchase invoice": { icon: "fa fa-money", cls: "color-purchase" },
      "purchase invoices": { icon: "fa fa-money", cls: "color-purchase" },
      "purchase bills": { icon: "fa fa-money", cls: "color-purchase" },
      "purchase returns": { icon: "fa fa-undo", cls: "color-purchase" },
      "suppliers": { icon: "fa fa-building", cls: "color-purchase" },
      "items list": { icon: "fa fa-cubes", cls: "color-items" },
      "item family list": { icon: "fa fa-sitemap", cls: "color-items" },
      "item groups": { icon: "fa fa-th-large", cls: "color-items" },
      "price lists": { icon: "fa fa-tags", cls: "color-items" },
      "brands": { icon: "fa fa-bookmark", cls: "color-items" },
      "customers": { icon: "fa fa-users", cls: "color-sales" },
      "quotation": { icon: "fa fa-file-text-o", cls: "color-sales" },
      "quotations": { icon: "fa fa-file-text-o", cls: "color-sales" },
      "sales orders": { icon: "fa fa-shopping-cart", cls: "color-sales" },
      "sales invoices": { icon: "fa fa-file-text", cls: "color-sales" },
      "sales returns": { icon: "fa fa-undo", cls: "color-sales" },
      "delivery notes": { icon: "fa fa-truck", cls: "color-sales" },
      "warehouses": { icon: "fa fa-archive", cls: "color-stock" },
      "stock adjustments": { icon: "fa fa-wrench", cls: "color-stock" },
      "stock take": { icon: "fa fa-clipboard", cls: "color-stock" },
      "serials & batches": { icon: "fa fa-barcode", cls: "color-stock" },
      "stock status": { icon: "fa fa-bar-chart", cls: "color-stock" },
      "bank accounts": { icon: "fa fa-university", cls: "color-accounts" },
      "payments": { icon: "fa fa-money", cls: "color-accounts" },
      "taxes": { icon: "fa fa-percent", cls: "color-accounts" },
      "journal entries": { icon: "fa fa-book", cls: "color-accounts" },
      "accounts receivable": { icon: "fa fa-arrow-circle-down", cls: "color-accounts" },
      "accounts payable": { icon: "fa fa-arrow-circle-up", cls: "color-accounts" },
      "business profile": { icon: "fa fa-building", cls: "color-settings" },
      "staff & users": { icon: "fa fa-user", cls: "color-settings" },
      "user list": { icon: "fa fa-users", cls: "color-settings" },
      "employee list": { icon: "fa fa-id-badge", cls: "color-hr" },
      "branding": { icon: "fa fa-paint-brush", cls: "color-settings" },
      "system rules": { icon: "fa fa-gavel", cls: "color-settings" },
      "counters": { icon: "fa fa-arrow-up", cls: "color-settings" },
      "pos counters": { icon: "fa fa-desktop", cls: "color-pos-counters" },
      "pos invoices": { icon: "fa fa-file-text", cls: "color-pos-invoices" },
      "pos profiles": { icon: "fa fa-id-card", cls: "color-pos-profiles" },
      "pos profile": { icon: "fa fa-id-card", cls: "color-settings" },
      "pos cashier shifts": { icon: "fa fa-user", cls: "color-pos-cashier-shifts" },
      "pos cashier shift": { icon: "fa fa-user", cls: "color-pos-cashier-shifts" },
      "pos counter sessions": { icon: "fa fa-desktop", cls: "color-pos-counter-sessions" },
      "pos counter session": { icon: "fa fa-desktop", cls: "color-pos-counter-sessions" },
      "pos opening entries": { icon: "fa fa-sign-in", cls: "color-pos-opening" },
      "pos opening entry": { icon: "fa fa-sign-in", cls: "color-accounts" },
      "pos closing entries": { icon: "fa fa-sign-out", cls: "color-pos-closing" },
      "pos closing entry": { icon: "fa fa-sign-out", cls: "color-accounts" },
      "pos branch day closings": { icon: "fa fa-calendar-check-o", cls: "color-pos-day-closing" },
      "pos branch day closing": { icon: "fa fa-calendar-check-o", cls: "color-pos-day-closing" },
      "pos sync logs": { icon: "fa fa-exchange", cls: "color-pos-sync" },
      "pos sync log": { icon: "fa fa-exchange", cls: "color-settings" },
      "pos reports": { icon: "fa fa-bar-chart", cls: "color-pos-reports" },
      "mode of payment": { icon: "fa fa-credit-card", cls: "color-accounts" },
      "pos invoice profit": { icon: "fa fa-file-text", cls: "color-pos-reports" },
      "pos invoice report": { icon: "fa fa-file-text", cls: "color-pos-reports" },
      "pos sales summary": { icon: "fa fa-bar-chart", cls: "color-accounts" },
      "pos transaction log": { icon: "fa fa-list", cls: "color-accounts" },
      "pos item-wise sales": { icon: "fa fa-cubes", cls: "color-sales" },
      "pos category/item group sales": { icon: "fa fa-sitemap", cls: "color-sales" },
      "pos category item group sales": { icon: "fa fa-sitemap", cls: "color-sales" },
      "pos hourly sales": { icon: "fa fa-clock-o", cls: "color-sales" },
      "pos return report": { icon: "fa fa-undo", cls: "color-sales" },
      "cashier wise sales": { icon: "fa fa-user", cls: "color-pos-cashier-shifts" },
      "counter wise sales": { icon: "fa fa-desktop", cls: "color-pos-counters" },
      "shift closing variance": { icon: "fa fa-balance-scale", cls: "color-pos-closing" },
      "payment mode summary": { icon: "fa fa-credit-card", cls: "color-accounts" },
      "pos payment mode summary": { icon: "fa fa-credit-card", cls: "color-accounts" },
      "pos discount report": { icon: "fa fa-tags", cls: "color-sales" },
      "pos price override report": { icon: "fa fa-pencil-square-o", cls: "color-sales" },
      "pos daily closing summary": { icon: "fa fa-calendar-check-o", cls: "color-pos-day-closing" },
      "pos cash movement report": { icon: "fa fa-money", cls: "color-accounts" },
      "sales reports": { icon: "fa fa-line-chart", cls: "color-sales" },
      "purchase reports": { icon: "fa fa-area-chart", cls: "color-purchase" },
      "stock reports": { icon: "fa fa-bar-chart", cls: "color-stock" },
      "accounts reports": { icon: "fa fa-pie-chart", cls: "color-accounts" },
      "pos sales reports": { icon: "fa fa-bar-chart", cls: "color-pos-reports" },
      "manufacturing module reports": { icon: "fa fa-industry", cls: "color-manufacturing" },
      "item group sales analysis": { icon: "fa fa-sitemap", cls: "color-sales" },
      "daily sales summary": { icon: "fa fa-line-chart", cls: "color-sales" },
      "counter performance": { icon: "fa fa-desktop", cls: "color-pos-counters" },
      "daily transaction log": { icon: "fa fa-list", cls: "color-sales" },
      "sales payment mode summary": { icon: "fa fa-credit-card", cls: "color-sales" },
      "daily profit report": { icon: "fa fa-money", cls: "color-sales" },
      "gross profit": { icon: "fa fa-area-chart", cls: "color-sales" },
      "sales tax report": { icon: "fa fa-percent", cls: "color-accounts" },
      "sales day wise tax report": { icon: "fa fa-calendar", cls: "color-accounts" },
      "purchase register": { icon: "fa fa-book", cls: "color-purchase" },
      "purchase tax report": { icon: "fa fa-percent", cls: "color-purchase" },
      "purchase day wise tax report": { icon: "fa fa-calendar", cls: "color-purchase" },
      "supplier wise returns": { icon: "fa fa-undo", cls: "color-purchase" },
      "stock balance": { icon: "fa fa-archive", cls: "color-stock" },
      "stock ledger": { icon: "fa fa-list-alt", cls: "color-stock" },
      "packing stock balance": { icon: "fa fa-cubes", cls: "color-stock" },
      "packing stock ledger": { icon: "fa fa-list", cls: "color-stock" },
      "stock movement summary": { icon: "fa fa-exchange", cls: "color-stock" },
      "stock adjustment history": { icon: "fa fa-history", cls: "color-stock" },
      "low stock reorder report": { icon: "fa fa-warning", cls: "color-stock" },
      "fast moving items": { icon: "fa fa-forward", cls: "color-items" },
      "slow moving items": { icon: "fa fa-hourglass-half", cls: "color-items" },
      "negative stock report": { icon: "fa fa-minus-circle", cls: "color-stock" },
      "near expiry report": { icon: "fa fa-clock-o", cls: "color-stock" },
      "expiry loss": { icon: "fa fa-trash-o", cls: "color-stock" },
      "general ledger": { icon: "fa fa-book", cls: "color-accounts" },
      "trial balance": { icon: "fa fa-balance-scale", cls: "color-accounts" },
      "balance sheet": { icon: "fa fa-table", cls: "color-accounts" },
      "profit and loss statement": { icon: "fa fa-line-chart", cls: "color-accounts" },
      "tax report": { icon: "fa fa-percent", cls: "color-accounts" },
      "tax reports": { icon: "fa fa-percent", cls: "color-accounts" },
      "tax payable report summary": { icon: "fa fa-calculator", cls: "color-accounts" }
    };
    const DESKTOP_MEDIA = "(min-width: 992px)";
    const DIRECT_MAPPING = ((_a = frappe.boot) == null ? void 0 : _a.retail_sidebar_routes) || {};
    const DOCTYPE_TO_WORKSPACE = {
      "Voucher Card Batch": "Promotions",
      "Voucher Card Transaction": "Promotions",
      "Loyalty Program": "Promotions",
      "Loyalty Point Entry": "Promotions",
      "Item": "Items",
      "Item Group": "Items",
      "Price List": "Items",
      "Item Price": "Items",
      "Brand": "Items",
      "Customer": "Sales",
      "Quotation": "Sales",
      "Sales Order": "Sales",
      "Sales Invoice": "Sales",
      "POS Invoice": "POS",
      "POS Profile": "POS",
      "POS Cashier Shift": "POS",
      "POS Counter Session": "POS",
      "POS Opening Entry": "POS",
      "POS Closing Entry": "POS",
      "POS Branch Day Closing": "POS",
      "POS Sync Log": "POS",
      "Delivery Note": "Sales",
      "Supplier": "Purchases",
      "Material Request": "Purchases",
      "Request for Quotation": "Purchases",
      "Supplier Quotation": "Purchases",
      "Purchase Order": "Purchases",
      "Purchase Receipt": "Purchases",
      "Purchase Invoice": "Purchases",
      "BOM": "Manufacturing",
      "Production Plan": "Manufacturing",
      "Work Order": "Manufacturing",
      "Job Card": "Manufacturing",
      "Quality Inspection": "Manufacturing",
      "Operation": "Manufacturing",
      "Workstation": "Manufacturing",
      "Routing": "Manufacturing",
      "BOM Creator": "Manufacturing",
      "Manufacturing Settings": "Manufacturing",
      "Warehouse": "Stocks",
      "Stock Entry": "Stocks",
      "Stock Reconciliation": "Stocks",
      "Serial and Batch Bundle": "Stocks",
      "Bin": "Stocks",
      "Bank Account": "Accounts",
      "Payment Entry": "Accounts",
      "Sales Taxes and Charges Template": "Accounts",
      "Journal Entry": "Accounts",
      "Company": "Settings",
      "User": "Settings",
      "Employee": "Settings",
      "POS Operator Privilege": "Settings",
      "Letter Head": "Settings",
      "Document Naming Rule": "Settings",
      "POS Branch Counter": "POS",
      "Van Fleet": "Van Sales",
      "Driver": "Van Sales",
      "Van Session": "Van Sales"
    };
    const DOCTYPE_TO_CHILD = {
      "Voucher Card Batch": "Promotions Voucher Card Batch Link",
      "Voucher Card Transaction": "Promotions Voucher Card Batch Link",
      "Loyalty Program": "Promotions Loyalty Program Link",
      "Loyalty Point Entry": "Promotions Loyalty Point Entry Link",
      "Item": "Items List",
      "Item Group": "Item Groups",
      "Price List": "Price Lists",
      "Item Price": "Price Lists",
      "Brand": "Brands",
      "Customer": "Customers",
      "Quotation": "Quotations",
      "Sales Order": "Sales Orders",
      "Sales Invoice": "Sales Invoices",
      "POS Invoice": "POS Invoices",
      "POS Profile": "POS Profile",
      "POS Cashier Shift": "POS Cashier Shifts",
      "POS Counter Session": "POS Counter Sessions",
      "POS Opening Entry": "POS Opening Entry",
      "POS Closing Entry": "POS Closing Entry",
      "POS Branch Day Closing": "POS Branch Day Closing",
      "POS Sync Log": "POS Sync Log",
      "Delivery Note": "Delivery Notes",
      "Supplier": "Suppliers",
      "Material Request": "Material Requests",
      "Request for Quotation": "Request for Quotations",
      "Supplier Quotation": "Supplier Quotations",
      "Purchase Order": "Purchase Orders",
      "Purchase Receipt": "Purchase Receipts",
      "Purchase Invoice": "Purchase Invoices",
      "BOM": "BOM",
      "Production Plan": "Production Plan",
      "Work Order": "Work Orders",
      "Job Card": "Job Cards",
      "Quality Inspection": "Quality Inspection",
      "Operation": "Manufacturing Setup",
      "Workstation": "Manufacturing Setup",
      "Routing": "Manufacturing Setup",
      "BOM Creator": "Manufacturing Setup",
      "Manufacturing Settings": "Manufacturing Setup",
      "Warehouse": "Warehouses",
      "Stock Entry": "Stock Adjustments",
      "Stock Reconciliation": "Stock Take",
      "Serial and Batch Bundle": "Serials & Batches",
      "Bin": "Stock Status",
      "Bank Account": "Bank Accounts",
      "Payment Entry": "Payments",
      "Sales Taxes and Charges Template": "Taxes",
      "Journal Entry": "Journal Entries",
      "Company": "Business Profile",
      "User": "User List",
      "Employee": "Employee List",
      "POS Operator Privilege": "Employee List",
      "Letter Head": "Branding",
      "Document Naming Rule": "System Rules",
      "POS Branch Counter": "POS Counters",
      "Van Fleet": "Van Fleet",
      "Driver": "Van Driver",
      "Van Session": "Van Sessions"
    };
    const CHILD_TO_PARENT = Object.freeze({
      "Promotions Loyalty Program Link": "Promotions",
      "Promotions Loyalty Program List Link": "Promotions Loyalty Program Link",
      "Promotions Loyalty Program Report Link": "Promotions Loyalty Program Link",
      "Promotions Loyalty Point Entry Link": "Promotions Loyalty Program Link",
      "Promotions Loyalty Point Entry Report Link": "Promotions Loyalty Program Link",
      "Promotions Promo Price Link": "Promotions",
      "Promotions Buy X Get Y Promotion Link": "Promotions",
      "Promotions Gift Voucher Promotion Link": "Promotions",
      "Promotions Gift Voucher Ledger Link": "Promotions",
      "Promotions Voucher Card Batch Link": "Promotions",
      "Voucher Card Batch": "Promotions",
      "Promo Price": "Promotions",
      "Buy X Get Y Promotion": "Promotions",
      "Gift Voucher Promotion": "Promotions",
      "Gift Voucher Ledger": "Promotions",
      "Items List": "Items",
      "Item Groups": "Items",
      "Price Lists": "Items",
      "Brands": "Items",
      "Customers": "Sales",
      "Quotation": "Sales",
      "Quotations": "Sales",
      "Sales Orders": "Sales",
      "Sales Invoices": "Sales",
      "Sales Returns": "Sales",
      "Trading Invoices": "Sales",
      "All Sales Invoices": "Sales",
      "POS Invoices": "POS",
      "POS Profile": "POS",
      "POS Profiles": "POS",
      "POS Cashier Shifts": "POS",
      "POS Counter Sessions": "POS",
      "POS Opening Entry": "POS",
      "POS Opening Entries": "POS",
      "POS Closing Entry": "POS",
      "POS Closing Entries": "POS",
      "POS Branch Day Closing": "POS",
      "POS Branch Day Closings": "POS",
      "POS Counters": "POS",
      "POS Sync Log": "POS",
      "POS Sync Logs": "POS",
      "Mode of Payment": "POS",
      "POS Payments": "POS",
      "POS Reports": "POS",
      "POS Invoice Profit": "POS Reports",
      "POS Sales Summary": "POS Reports",
      "POS Transaction Log": "POS Reports",
      "POS Item-wise Sales": "POS Reports",
      "POS Category/Item Group Sales": "POS Reports",
      "POS Category Item Group Sales": "POS Reports",
      "POS Hourly Sales": "POS Reports",
      "POS Return Report": "POS Reports",
      "Cashier Wise Sales": "POS Reports",
      "Counter Wise Sales": "POS Reports",
      "Shift Closing Variance": "POS Reports",
      "Payment Mode Summary": "POS Reports",
      "POS Discount Report": "POS Reports",
      "POS Price Override Report": "POS Reports",
      "POS Daily Closing Summary": "POS Reports",
      "POS Cash Movement Report": "POS Reports",
      "Counter Performance": "POS",
      "Delivery Notes": "Sales",
      "Suppliers": "Purchases",
      "Material Request": "Purchases",
      "Material Requests": "Purchases",
      "Request for Quotation": "Purchases",
      "Request for Quotations": "Purchases",
      "Supplier Quotation": "Purchases",
      "Supplier Quotations": "Purchases",
      "Purchase Orders": "Purchases",
      "Purchase Receipts": "Purchases",
      "Purchase Invoice": "Purchases",
      "Purchase Invoices": "Purchases",
      "Purchase Bills": "Purchases",
      "Purchase Returns": "Purchases",
      "BOM": "Manufacturing",
      "Production Plan": "Manufacturing",
      "Work Orders": "Manufacturing",
      "Job Cards": "Manufacturing",
      "Stock Entries": "Manufacturing",
      "Quality Inspection": "Manufacturing",
      "Manufacturing Reports": "Manufacturing",
      "Manufacturing Setup": "Manufacturing",
      "BOM Stock Report": "Manufacturing",
      "Work Order Stock Report": "Manufacturing",
      "Open Work Orders": "Manufacturing",
      "Work Orders in Progress": "Manufacturing",
      "Completed Work Orders": "Manufacturing",
      "Work Order Summary": "Manufacturing",
      "Job Card Summary": "Manufacturing",
      "Production Analytics": "Manufacturing",
      "Operations": "Manufacturing",
      "Workstations": "Manufacturing",
      "Routing": "Manufacturing",
      "BOM Creator": "Manufacturing",
      "Manufacturing Settings": "Manufacturing",
      "Warehouses": "Stocks",
      "Stock Adjustments": "Stocks",
      "Stock Take": "Stocks",
      "Serials & Batches": "Stocks",
      "Stock Status": "Stocks",
      "Bank Accounts": "Accounts",
      "Payments": "Accounts",
      "Taxes": "Accounts",
      "Journal Entries": "Accounts",
      "Accounts Receivable": "Accounts",
      "Accounts Payable": "Accounts",
      "Business Profile": "Settings",
      "Staff & Users": "Settings",
      "User List": "Settings",
      "Employee List": "Settings",
      "Branding": "Settings",
      "System Rules": "Settings",
      "Van Fleet": "Van Sales",
      "Fleet": "Van Sales",
      "Van Driver": "Van Sales",
      "Driver": "Van Sales",
      "Van Sessions": "Van Sales",
      "Stock Request": "Van Sales",
      "Van Stock Request": "Van Sales",
      "Van Stock Entries": "Van Sales",
      "Van Stock View": "Van Sales",
      "Van Sales Invoice": "Van Sales",
      "Van Payments": "Van Sales",
      "Van Customers": "Van Sales",
      "Van Items": "Van Sales",
      "Van Warehouses": "Van Sales",
      "Van Sales Fleet Link": "Van Sales",
      "Van Sales Driver Link": "Van Sales",
      "Van Sales Sessions Link": "Van Sales",
      "Van Sales Stock Entries Link": "Van Sales",
      "Van Sales Stock View Link": "Van Sales",
      "Van Sales Invoice Link": "Van Sales",
      "Van Sales Payments Link": "Van Sales",
      "Van Sales Customers Link": "Van Sales",
      "Van Sales Items Link": "Van Sales",
      "Van Sales Warehouses Link": "Van Sales",
      "Van Sales Reports": "Van Sales",
      "Van Sales Reports Link": "Van Sales",
      "Van Daily Sales Summary": "Van Sales Reports",
      "Van Daily Stock Summary": "Van Sales Reports",
      "Van Detailed Sales Summary": "Van Sales Reports",
      "Van Profit Report": "Van Sales Reports",
      "Van Wastage Report": "Van Sales Reports",
      "Van Outstanding Collection Summary": "Van Sales Reports",
      "Daily Stock Summary": "Van Sales",
      "Detailed Sales Summary": "Van Sales",
      "Profit Report": "Van Sales",
      "Wastage Report": "Van Sales",
      "Outstanding / Collection Summary": "Van Sales"
    });
    const ROUTE_ALIAS_TO_CHILD = Object.freeze({
      "Fleet": "Van Sales Fleet Link",
      "Van Fleet": "Van Sales Fleet Link",
      "Driver": "Van Sales Driver Link",
      "Van Driver": "Van Sales Driver Link",
      "Van Session": "Van Sales Sessions Link",
      "Van Sessions": "Van Sales Sessions Link",
      "Van Items": "Van Sales Items Link",
      "Van Warehouses": "Van Sales Warehouses Link",
      "Van Sales Reports": "Van Sales Reports Link",
      "BOM Stock Report": "Manufacturing Reports",
      "Work Order Stock Report": "Manufacturing Reports",
      "Open Work Orders": "Manufacturing Reports",
      "Work Orders in Progress": "Manufacturing Reports",
      "Completed Work Orders": "Manufacturing Reports",
      "Work Order Summary": "Manufacturing Reports",
      "Job Card Summary": "Manufacturing Reports",
      "Production Analytics": "Manufacturing Reports",
      "Operations": "Manufacturing Setup",
      "Workstations": "Manufacturing Setup",
      "Routing": "Manufacturing Setup",
      "BOM Creator": "Manufacturing Setup",
      "Manufacturing Settings": "Manufacturing Setup"
    });
    const WORKSPACE_ROUTE_NAMES = Object.freeze({
      "Home": "Business Home",
      "Manufacturing Reports": "Manufacturing Reports",
      "Manufacturing Setup": "Manufacturing Setup"
    });
    const WORKSPACE_DISPLAY_LABELS = Object.freeze(((_b = frappe.boot) == null ? void 0 : _b.retail_sidebar_labels) || {});
    const ROLE_SIDEBAR_WORKSPACES = Object.freeze({
      "Van Sales User": ["Van Sales"],
      "Van Sales Manager": ["Van Sales"],
      "Sales User": ["Sales"],
      "Sales Manager": ["Sales"],
      "Sales Master Manager": ["Sales"],
      "Item Manager": ["Items"],
      "Retail Price Manager": ["Items"],
      "Stock User": ["Stocks"],
      "Stock Manager": ["Stocks"],
      "Purchase User": ["Purchases"],
      "Purchase Manager": ["Purchases"],
      "Purchase Master Manager": ["Purchases"],
      "Accounts User": ["Accounts"],
      "Accounts Manager": ["Accounts"],
      "POS User": ["POS"],
      "POS Manager": ["POS"],
      "POS Integration User": ["POS"],
      "Manufacturing User": ["Manufacturing"],
      "Manufacturing Manager": ["Manufacturing"],
      "Report Manager": ["Reports"],
      "Analytics": ["Reports"],
      "Fleet Manager": ["Van Sales"]
    });
    const TOP_LEVEL_WORKSPACES = /* @__PURE__ */ new Set([
      "Promotions",
      "Business Home",
      "Items",
      "Sales",
      "POS",
      "Purchases",
      "Stocks",
      "Manufacturing",
      "Van Sales",
      "Accounts",
      "Reports",
      "Settings"
    ]);
    const ALWAYS_VISIBLE_WORKSPACES = /* @__PURE__ */ new Set(["Business Home"]);
    const HIDDEN_SIDEBAR_LABELS = /* @__PURE__ */ new Set([
      "Sales Stock View",
      "Stock View"
    ]);
    const WORKSPACE_TO_MODULE = Object.freeze({
      "Business Home": "",
      "Items": "Stock",
      "Items List": "Stock",
      "Item Family List": "Stock",
      "Item Groups": "Stock",
      "Price Lists": "Stock",
      "Brands": "Stock",
      "Stocks": "Stock",
      "Warehouses": "Stock",
      "Stock Adjustments": "Stock",
      "Stock Take": "Stock",
      "Serials & Batches": "Stock",
      "Stock Status": "Stock",
      "Delivery Notes": "Stock",
      "Purchase Receipts": "Stock",
      "Material Requests": "Stock",
      "Sales": "Selling",
      "Customers": "Selling",
      "Quotations": "Selling",
      "Sales Orders": "Selling",
      "Sales Invoices": "Selling",
      "Sales Returns": "Selling",
      "POS": "Accounts",
      "POS Invoices": "Accounts",
      "POS Profile": "Accounts",
      "POS Profiles": "Accounts",
      "POS Counters": "Accounts",
      "POS Opening Entry": "Accounts",
      "POS Opening Entries": "Accounts",
      "POS Closing Entry": "Accounts",
      "POS Closing Entries": "Accounts",
      "POS Cashier Shifts": "Accounts",
      "POS Counter Sessions": "Accounts",
      "POS Branch Day Closing": "Accounts",
      "POS Branch Day Closings": "Accounts",
      "POS Sync Log": "Accounts",
      "POS Sync Logs": "Accounts",
      "Mode of Payment": "Accounts",
      "POS Reports": "Accounts",
      "POS Sales Summary": "Accounts",
      "POS Transaction Log": "Accounts",
      "POS Item-wise Sales": "Accounts",
      "POS Category/Item Group Sales": "Accounts",
      "POS Category Item Group Sales": "Accounts",
      "POS Hourly Sales": "Accounts",
      "POS Return Report": "Accounts",
      "Cashier Wise Sales": "Accounts",
      "Counter Wise Sales": "Accounts",
      "Shift Closing Variance": "Accounts",
      "Payment Mode Summary": "Accounts",
      "POS Discount Report": "Accounts",
      "POS Price Override Report": "Accounts",
      "POS Daily Closing Summary": "Accounts",
      "POS Cash Movement Report": "Accounts",
      "Purchases": "Buying",
      "Suppliers": "Buying",
      "Request for Quotations": "Buying",
      "Supplier Quotations": "Buying",
      "Purchase Orders": "Buying",
      "Purchase Invoices": "Accounts",
      "Purchase Returns": "Accounts",
      "Manufacturing": "Manufacturing",
      "BOM": "Manufacturing",
      "Production Plan": "Manufacturing",
      "Work Orders": "Manufacturing",
      "Job Cards": "Manufacturing",
      "Stock Entries": "Manufacturing",
      "Quality Inspection": "Manufacturing",
      "Manufacturing Reports": "Manufacturing",
      "Manufacturing Setup": "Manufacturing",
      "Accounts": "Accounts",
      "Bank Accounts": "Accounts",
      "Payments": "Accounts",
      "Taxes": "Accounts",
      "Journal Entries": "Accounts",
      "Accounts Receivable": "Accounts",
      "Accounts Payable": "Accounts",
      "Reports": "Accounts",
      "Settings": "Setup",
      "Business Profile": "Setup",
      "Branding": "Setup",
      "System Rules": "Setup",
      "User List": "Setup",
      "Employee List": "HR",
      "Van Sales": "",
      "Van Fleet": "",
      "Van Driver": "",
      "Van Sessions": "",
      "Stock Request": "",
      "Van Stock Request": "",
      "Van Stock Entries": "",
      "Van Stock View": "",
      "Van Sales Invoice": "",
      "Van Payments": "",
      "Van Customers": "",
      "Van Items": "",
      "Van Warehouses": "",
      "Van Sales Fleet Link": "",
      "Van Sales Driver Link": "",
      "Van Sales Sessions Link": "",
      "Van Sales Stock Entries Link": "",
      "Van Sales Stock View Link": "",
      "Van Sales Invoice Link": "",
      "Van Sales Payments Link": "",
      "Van Sales Customers Link": "",
      "Van Sales Items Link": "",
      "Van Sales Warehouses Link": "",
      "Van Sales Reports": "",
      "Van Sales Reports Link": ""
    });
    const REPORT_TO_WORKSPACE = Object.freeze({
      "Daily Sales Summary": "Sales",
      "Counter Performance": "Sales",
      "Daily Transaction Log": "Sales",
      "Daily Profit Report": "Sales",
      "Gross Profit": "Sales",
      "Low Stock Reorder Report": "Stocks",
      "Stock Movement Summary": "Stocks",
      "Stock Adjustment History": "Stocks",
      "Stock Balance": "Stocks",
      "Stock Ledger": "Stocks",
      "Packing Stock Balance": "Stocks",
      "Packing Stock Ledger": "Stocks",
      "Fast Moving Items": "Items",
      "Slow Moving Items": "Items",
      "Accounts Receivable": "Accounts",
      "Accounts Payable": "Accounts",
      "General Ledger": "Accounts",
      "Trial Balance": "Accounts",
      "Balance Sheet": "Accounts",
      "Profit and Loss Statement": "Accounts",
      "POS Sales Summary": "POS Reports",
      "POS Transaction Log": "POS Reports",
      "POS Item-wise Sales": "POS Reports",
      "POS Category Item Group Sales": "POS Reports",
      "POS Category/Item Group Sales": "POS Reports",
      "POS Hourly Sales": "POS Reports",
      "POS Return Report": "POS Reports",
      "Cashier Wise Sales": "POS Reports",
      "Counter Wise Sales": "POS Reports",
      "Shift Closing Variance": "POS Reports",
      "POS Payment Mode Summary": "POS Reports",
      "Payment Mode Summary": "POS Reports",
      "POS Discount Report": "POS Reports",
      "POS Price Override Report": "POS Reports",
      "POS Daily Closing Summary": "POS Reports",
      "POS Cash Movement Report": "POS Reports",
      "BOM Stock Report": "Manufacturing",
      "Work Order Stock Report": "Manufacturing",
      "Open Work Orders": "Manufacturing",
      "Work Orders in Progress": "Manufacturing",
      "Completed Work Orders": "Manufacturing",
      "Work Order Summary": "Manufacturing",
      "Job Card Summary": "Manufacturing",
      "Production Analytics": "Manufacturing",
      "Van Daily Sales Summary": "Van Sales Reports",
      "Van Daily Stock Summary": "Van Sales Reports",
      "Van Detailed Sales Summary": "Van Sales Reports",
      "Van Profit Report": "Van Sales Reports",
      "Van Wastage Report": "Van Sales Reports",
      "Van Outstanding Collection Summary": "Van Sales Reports"
    });
    const VAN_PAGE_TO_CHILD = Object.freeze({
      "retail-van-sales-invoice": "Van Sales Invoice",
      "van-payments": "Van Payments",
      "van-stock-request": "Stock Request",
      "van-stock-entries": "Van Stock Entries",
      "van-stock-view": "Van Stock View",
      "van-customers": "Van Customers"
    });
    const VAN_PAGE_ROUTES = new Set(Object.keys(VAN_PAGE_TO_CHILD));
    const REQUIRED_VAN_SALES_CHILDREN = Object.freeze([
      {
        name: "Stock Request",
        title: "Stock Request",
        parent_page: "Van Sales",
        icon: "list",
        public: 1,
        is_hidden: 0
      },
      {
        name: "Van Sales Stock View Link",
        title: "Van Stock View",
        parent_page: "Van Sales",
        icon: "stock",
        public: 1,
        is_hidden: 0,
        insert_after: ["Van Stock Entries", "Stock Request", "Van Sessions"]
      }
    ]);
    let sidebarItemsPromise = null;
    let sidebarItemsCache = null;
    let observerRefreshTimer = null;
    let routeRefreshTimer = null;
    let sidebarRenderRetryCount = 0;
    let sidebarRenderRetryTimer = null;
    let useBootSidebarItems = true;
    let sidebarItemsGeneration = 0;
    let workspaceCustomCardsPatched = false;
    let workspaceSidebarRoutesPatched = false;
    const dynamicSidebarItems = /* @__PURE__ */ new Map();
    const manuallyClosedSidebarGroups = /* @__PURE__ */ new Set();
    let lastSidebarStateRouteKey = null;
    let openWorkClearedRouteKey = null;
    function redirectStandardHomeToBusinessHome() {
      var _a2, _b2;
      if (Array.isArray((_a2 = frappe.boot) == null ? void 0 : _a2.retail_sidebar_selection) && !workspaceIsAllowed("Business Home"))
        return false;
      const route = ((_b2 = frappe.get_route) == null ? void 0 : _b2.call(frappe)) || [];
      const routeName = route[0] === "private" ? route[1] : route[0];
      if (frappe.router.slug(routeName || "") !== "home")
        return false;
      const target = getWorkspaceUrl("Business Home", true).replace(/^\/app\//, "");
      if (route.join("/") === target)
        return false;
      frappe.set_route(target);
      return true;
    }
    function bindNavbarHomeToBusinessHome() {
      var _a2;
      if (Array.isArray((_a2 = frappe.boot) == null ? void 0 : _a2.retail_sidebar_selection) && !workspaceIsAllowed("Business Home"))
        return;
      const businessHomeUrl = getWorkspaceUrl("Business Home", true);
      const businessHomeRoute = businessHomeUrl.replace(/^\/app\//, "");
      document.querySelectorAll(".navbar .navbar-home").forEach((link) => {
        if (link.tagName === "A") {
          link.setAttribute("href", businessHomeUrl);
        }
      });
      if (!window.__retail_business_home_navbar_bound) {
        window.__retail_business_home_navbar_bound = true;
        document.addEventListener("click", (event) => {
          var _a3, _b2, _c2;
          const homeLink = (_b2 = (_a3 = event.target) == null ? void 0 : _a3.closest) == null ? void 0 : _b2.call(_a3, ".navbar .navbar-home");
          if (!homeLink)
            return;
          event.preventDefault();
          event.stopPropagation();
          (_c2 = event.stopImmediatePropagation) == null ? void 0 : _c2.call(event);
          frappe.set_route(businessHomeRoute);
        }, true);
      }
      if (!window.jQuery)
        return;
      $(document).off("click.retailBusinessHome", ".navbar .navbar-home").on("click.retailBusinessHome", ".navbar .navbar-home", (event) => {
        event.preventDefault();
        event.stopPropagation();
        frappe.set_route(businessHomeRoute);
        return false;
      });
    }
    function normalizeText(text) {
      return (text || "").toString().trim().toLowerCase().replace(/\s+/g, " ");
    }
    function getBlockedModules() {
      var _a2;
      return new Set(((_a2 = frappe.boot) == null ? void 0 : _a2.retail_blocked_modules) || []);
    }
    function moduleIsAllowed(moduleName) {
      var _a2, _b2;
      if (((_b2 = (_a2 = frappe.boot) == null ? void 0 : _a2.retail_module_access) == null ? void 0 : _b2[moduleName]) === false)
        return false;
      return !moduleName || !getBlockedModules().has(moduleName);
    }
    function getWorkspaceModule(workspaceName) {
      var _a2, _b2;
      if (!workspaceName)
        return "";
      return WORKSPACE_TO_MODULE[workspaceName] || ((_b2 = (_a2 = frappe.boot) == null ? void 0 : _a2.retail_workspace_modules) == null ? void 0 : _b2[workspaceName]) || "";
    }
    function getCurrentUserRoles() {
      var _a2, _b2;
      return frappe.user_roles || ((_b2 = (_a2 = frappe.boot) == null ? void 0 : _a2.user) == null ? void 0 : _b2.roles) || [];
    }
    function getRoleAllowedSidebarWorkspaces() {
      var _a2, _b2;
      if (((_a2 = frappe.session) == null ? void 0 : _a2.user) === "Administrator")
        return null;
      const roles = getCurrentUserRoles();
      if (roles.includes("System Manager"))
        return null;
      const bootAllowed = (_b2 = frappe.boot) == null ? void 0 : _b2.retail_allowed_sidebar_workspaces;
      if (Array.isArray(bootAllowed))
        return new Set(bootAllowed);
      const allowed = /* @__PURE__ */ new Set();
      roles.forEach((role) => {
        (ROLE_SIDEBAR_WORKSPACES[role] || []).forEach((workspace) => allowed.add(workspace));
      });
      ALWAYS_VISIBLE_WORKSPACES.forEach((workspace) => allowed.add(workspace));
      return allowed;
    }
    function getSidebarGroup(workspaceName) {
      var _a2, _b2;
      if (!workspaceName)
        return "";
      if ((_a2 = dynamicSidebarItems.get(workspaceName)) == null ? void 0 : _a2.sidebar_group) {
        return dynamicSidebarItems.get(workspaceName).sidebar_group;
      }
      const bootGroups = ((_b2 = frappe.boot) == null ? void 0 : _b2.retail_workspace_sidebar_groups) || {};
      if (bootGroups[workspaceName])
        return bootGroups[workspaceName];
      let current = workspaceName;
      const seen = /* @__PURE__ */ new Set();
      while (current && !seen.has(current)) {
        seen.add(current);
        if (TOP_LEVEL_WORKSPACES.has(current))
          return current;
        current = CHILD_TO_PARENT[current];
      }
      return workspaceName;
    }
    function sidebarWorkspaceIsAllowed(...names) {
      if (names.filter(Boolean).some((name) => ALWAYS_VISIBLE_WORKSPACES.has(name)))
        return true;
      const allowed = getRoleAllowedSidebarWorkspaces();
      if (allowed === null)
        return true;
      return names.filter(Boolean).some((name) => allowed.has(getSidebarGroup(name)));
    }
    function workspaceIsAllowed(workspaceName) {
      var _a2;
      const selection = (_a2 = frappe.boot) == null ? void 0 : _a2.retail_sidebar_selection;
      if (Array.isArray(selection)) {
        const entries = (frappe.boot.retail_sidebar_registry || []).flatMap((group) => [group, ...group.children]);
        const entry = entries.find((entry2) => entry2.workspace === workspaceName || entry2.workspace === WORKSPACE_DISPLAY_LABELS[workspaceName]);
        if (entry && !selection.includes(entry.id))
          return false;
      }
      if (workspaceName && !sidebarWorkspaceIsAllowed(workspaceName))
        return false;
      let current = workspaceName;
      const seen = /* @__PURE__ */ new Set();
      while (current && !seen.has(current)) {
        seen.add(current);
        if (!moduleIsAllowed(getWorkspaceModule(current)))
          return false;
        current = CHILD_TO_PARENT[current];
      }
      return true;
    }
    function checklistTargetIsAllowed(kind, target) {
      var _a2, _b2;
      if ((_a2 = frappe.boot) == null ? void 0 : _a2.retail_sidebar_unrestricted_targets)
        return true;
      const selection = (_b2 = frappe.boot) == null ? void 0 : _b2.retail_sidebar_selection;
      if (!Array.isArray(selection))
        return true;
      const entries = (frappe.boot.retail_sidebar_registry || []).flatMap((group) => [group, ...group.children]);
      const candidates = entries.filter((entry) => (entry.targets || []).some((pair) => pair[0] === kind && pair[1] === target));
      return !candidates.length || candidates.some((entry) => selection.includes(entry.id));
    }
    function doctypeIsAllowed(doctype) {
      var _a2, _b2, _c2, _d;
      if (!doctype)
        return true;
      if (!checklistTargetIsAllowed("doctype", doctype))
        return false;
      let canRead = true;
      const bootCanRead = (_b2 = (_a2 = frappe.boot) == null ? void 0 : _a2.user) == null ? void 0 : _b2.can_read;
      if (Array.isArray(bootCanRead)) {
        canRead = bootCanRead.includes(doctype);
      } else if ((_c2 = frappe.model) == null ? void 0 : _c2.can_read) {
        canRead = frappe.model.can_read(doctype);
      }
      if (!canRead)
        return false;
      if (Array.isArray((_d = frappe.boot) == null ? void 0 : _d.retail_sidebar_selection))
        return true;
      if (doctype === "Driver")
        return true;
      const workspace = DOCTYPE_TO_CHILD[doctype] || DOCTYPE_TO_WORKSPACE[doctype];
      return workspace ? workspaceIsAllowed(workspace) : true;
    }
    function pageIsAllowed(pageName) {
      var _a2;
      if (!pageName)
        return true;
      if (!checklistTargetIsAllowed("page", pageName))
        return false;
      if (["point-of-sale", "pos"].includes(pageName) && !moduleIsAllowed("POS"))
        return false;
      if ((pageName.startsWith("van-") || pageName === "retail-van-sales-invoice") && !moduleIsAllowed("Van Sales"))
        return false;
      const allowedPages = (_a2 = frappe.boot) == null ? void 0 : _a2.allowed_pages;
      return !Array.isArray(allowedPages) || !allowedPages.length || allowedPages.includes(pageName);
    }
    function reportIsAllowed(reportName, report) {
      var _a2, _b2, _c2, _d, _e;
      if (!checklistTargetIsAllowed("report", reportName))
        return false;
      if (((reportName == null ? void 0 : reportName.startsWith("POS ")) || ["Cashier Wise Sales", "Counter Wise Sales", "Shift Closing Variance", "Item Group Sales Analysis"].includes(reportName)) && !moduleIsAllowed("POS"))
        return false;
      if ((reportName == null ? void 0 : reportName.startsWith("Van ")) && !moduleIsAllowed("Van Sales"))
        return false;
      if (workspaceIsAllowed("Reports") && ((_b2 = (_a2 = frappe.boot) == null ? void 0 : _a2.retail_allowed_workspace_reports) == null ? void 0 : _b2.includes(reportName)))
        return true;
      if (!reportName)
        return true;
      const reports = (_d = (_c2 = frappe.boot) == null ? void 0 : _c2.user) == null ? void 0 : _d.all_reports;
      if (reports && !reports[reportName])
        return false;
      if (Array.isArray((_e = frappe.boot) == null ? void 0 : _e.retail_sidebar_selection))
        return true;
      const workspace = REPORT_TO_WORKSPACE[reportName];
      if (workspace)
        return workspaceIsAllowed(workspace);
      return doctypeIsAllowed(report == null ? void 0 : report.ref_doctype);
    }
    function routeIsAllowed(route) {
      var _a2, _b2, _c2;
      if (!Array.isArray(route) || !route.length)
        return true;
      const view = route[0];
      if (VAN_PAGE_TO_CHILD[view]) {
        return workspaceIsAllowed("Van Sales") && (pageIsAllowed(view) || VAN_PAGE_ROUTES.has(view));
      }
      if (view === "List" || view === "Form" || view === "Tree") {
        return doctypeIsAllowed(route[1]);
      }
      if (view === "query-report") {
        return reportIsAllowed(route[1], (_c2 = (_b2 = (_a2 = frappe.boot) == null ? void 0 : _a2.user) == null ? void 0 : _b2.all_reports) == null ? void 0 : _c2[route[1]]);
      }
      if (view === "Workspaces" || view === "workspace" || view === "private") {
        const workspaceName = view === "private" ? route[1] : route[1];
        return workspaceIsAllowed(routeNameToWorkspaceTitle(workspaceName));
      }
      if (typeof view === "string") {
        return pageIsAllowed(view);
      }
      return true;
    }
    function getSidebarTarget(item) {
      var _a2;
      const title = (item == null ? void 0 : item.title) || (item == null ? void 0 : item.name) || "";
      const displayTitle = WORKSPACE_DISPLAY_LABELS[item == null ? void 0 : item.name] || title;
      return (item == null ? void 0 : item.route) || ((_a2 = dynamicSidebarItems.get((item == null ? void 0 : item.name) || title)) == null ? void 0 : _a2.route) || DIRECT_MAPPING[title] || DIRECT_MAPPING[item == null ? void 0 : item.name] || DIRECT_MAPPING[displayTitle];
    }
    function workspaceHasAllowedChildren(workspaceName) {
      if (!workspaceName)
        return false;
      if (Array.from(dynamicSidebarItems.values()).some((item) => item.parent_page === workspaceName && sidebarItemIsAllowed(item)))
        return true;
      return Object.entries(CHILD_TO_PARENT).some(([child, parent]) => {
        if (parent !== workspaceName)
          return false;
        if (!sidebarWorkspaceIsAllowed(child))
          return false;
        if (!workspaceIsAllowed(child))
          return false;
        const childTarget = getSidebarTarget({ name: child, title: child });
        if (childTarget)
          return routeIsAllowed(childTarget);
        return workspaceHasAllowedChildren(child);
      });
    }
    function sidebarItemIsAllowed(item) {
      var _a2;
      const title = (item == null ? void 0 : item.title) || (item == null ? void 0 : item.name) || "";
      if (Array.isArray((_a2 = frappe.boot) == null ? void 0 : _a2.retail_sidebar_selection)) {
        const entries = (frappe.boot.retail_sidebar_registry || []).flatMap((group) => [group, ...group.children]);
        const entry = entries.find((entry2) => entry2.workspace === (item == null ? void 0 : item.name) || entry2.workspace === title || entry2.workspace === WORKSPACE_DISPLAY_LABELS[item == null ? void 0 : item.name]);
        if (entry && !frappe.boot.retail_sidebar_selection.includes(entry.id))
          return false;
      }
      const target = getSidebarTarget(item);
      const reportItem = dynamicSidebarItems.get((item == null ? void 0 : item.name) || title);
      if (reportItem) {
        if (reportItem.is_report_link) {
          const reportRoute = reportItem.route || target;
          const reportName = Array.isArray(reportRoute) && reportRoute[0] === "query-report" ? reportRoute[1] : reportItem.link_to || title;
          return workspaceIsAllowed("Reports") && reportIsAllowed(reportName, reportItem);
        }
        return workspaceIsAllowed("Reports") && workspaceHasAllowedChildren(reportItem.name);
      }
      if (ALWAYS_VISIBLE_WORKSPACES.has(item == null ? void 0 : item.name) || ALWAYS_VISIBLE_WORKSPACES.has(title))
        return true;
      if (!sidebarWorkspaceIsAllowed(item == null ? void 0 : item.name, title))
        return false;
      if (!workspaceIsAllowed(title) || !workspaceIsAllowed(item == null ? void 0 : item.name))
        return false;
      if ((item == null ? void 0 : item.is_workspace_link) || ((item == null ? void 0 : item.name) || title) === "Reports")
        return true;
      if (target)
        return routeIsAllowed(target);
      return workspaceHasAllowedChildren((item == null ? void 0 : item.name) || title);
    }
    function registerSidebarItems(items) {
      (items || []).forEach((item) => {
        if (item.is_report_link || item.is_report_group) {
          dynamicSidebarItems.set(item.name || item.title, item);
        }
      });
      return items;
    }
    function optionIsAllowed(option) {
      if (!option)
        return true;
      if (option.match && typeof option.match === "string") {
        if (DOCTYPE_TO_CHILD[option.match] || DOCTYPE_TO_WORKSPACE[option.match]) {
          return doctypeIsAllowed(option.match);
        }
        if (WORKSPACE_TO_MODULE[option.match]) {
          return workspaceIsAllowed(option.match);
        }
      }
      return routeIsAllowed(option.route);
    }
    function routeNameToWorkspaceTitle(routeName) {
      const decoded = decodeURIComponent(String(routeName || "")).replace(/-/g, " ");
      const normalized = normalizeText(decoded);
      const known = Object.keys(WORKSPACE_TO_MODULE).find((name) => normalizeText(name) === normalized);
      return known || decoded.replace(/\b\w/g, (char) => char.toUpperCase());
    }
    function filterSearchResults(results) {
      if (!Array.isArray(results))
        return results;
      return results.filter(optionIsAllowed);
    }
    function filterGlobalResultSets(resultSets) {
      if (!Array.isArray(resultSets))
        return resultSets;
      return resultSets.map((set) => Object.assign({}, set, { results: filterSearchResults(set.results || []) })).filter((set) => doctypeIsAllowed(set.title) && set.results.length);
    }
    function installModuleAwareSearchFilters() {
      var _a2;
      const utils = (_a2 = frappe.search) == null ? void 0 : _a2.utils;
      if (!utils || utils.__retail_module_filters_installed)
        return !!utils;
      [
        "get_recent_pages",
        "get_frequent_links",
        "get_search_in_list",
        "get_creatables",
        "get_doctypes",
        "get_reports",
        "get_pages",
        "get_workspaces",
        "get_dashboards",
        "get_executables"
      ].forEach((methodName) => {
        const original = utils[methodName];
        if (typeof original !== "function")
          return;
        utils[methodName] = function(...args) {
          return filterSearchResults(original.apply(this, args));
        };
      });
      const originalGetGlobalResults = utils.get_global_results;
      if (typeof originalGetGlobalResults === "function") {
        utils.get_global_results = function(...args) {
          return originalGetGlobalResults.apply(this, args).then(filterGlobalResultSets);
        };
      }
      utils.__retail_module_filters_installed = true;
      return true;
    }
    function waitForSearchFilters() {
      if (installModuleAwareSearchFilters())
        return;
      let attempts = 0;
      const timer = setInterval(() => {
        attempts += 1;
        if (installModuleAwareSearchFilters() || attempts >= 40)
          clearInterval(timer);
      }, 250);
    }
    function enforceAllowedRoute() {
      var _a2, _b2;
      if (routeIsAllowed(((_a2 = frappe.get_route) == null ? void 0 : _a2.call(frappe)) || []))
        return false;
      frappe.show_alert({
        message: __("You do not have permission to access this module."),
        indicator: "orange"
      });
      if (Array.isArray((_b2 = frappe.boot) == null ? void 0 : _b2.retail_sidebar_selection)) {
        const permitted = (frappe.boot.allowed_workspaces || []).find((item) => item.route || DIRECT_MAPPING[item.name]);
        const target = permitted && (permitted.route || DIRECT_MAPPING[permitted.name]);
        if (target)
          frappe.set_route(target);
      } else {
        frappe.set_route(getWorkspaceUrl("Business Home", true).replace(/^\/app\//, ""));
      }
      return true;
    }
    function findIconConfig(labelText) {
      const displayLabel = WORKSPACE_DISPLAY_LABELS[labelText] || labelText;
      const name = normalizeText(displayLabel);
      if (!name)
        return null;
      if (ICON_MAP[name])
        return ICON_MAP[name];
      if (ICON_MAP[name + "s"])
        return ICON_MAP[name + "s"];
      return null;
    }
    function createIconElement(config) {
      const iconEl = document.createElement("i");
      let iconClasses = (config.icon || "").replace(/\bfa-(?:solid|regular|brands|light|duotone)\b/g, "fa").replace(/\bfas\b|\bfar\b|\bfal\b/g, "fa");
      if (!/\bfa\b/.test(iconClasses)) {
        iconClasses = `fa ${iconClasses}`.trim();
      }
      iconEl.className = `${iconClasses} ${config.cls} retail-icon`;
      iconEl.setAttribute("aria-hidden", "true");
      return iconEl;
    }
    function isDesktop() {
      return window.matchMedia(DESKTOP_MEDIA).matches;
    }
    function isMobile() {
      return !isDesktop();
    }
    function isWorkspaceRoute(route) {
      var _a2, _b2, _c2;
      const view = (_a2 = route == null ? void 0 : route[0]) == null ? void 0 : _a2.toLowerCase();
      const routeSlug = frappe.router.slug(
        (route == null ? void 0 : route[0]) === "private" ? (route == null ? void 0 : route[1]) || "" : (route == null ? void 0 : route[0]) || ""
      );
      const currentPage = getCurrentPage();
      return view === "workspaces" || view === "workspace" || !!(routeSlug && ((_b2 = frappe.workspaces) == null ? void 0 : _b2[routeSlug])) || ((_c2 = currentPage == null ? void 0 : currentPage.dataset) == null ? void 0 : _c2.pageRoute) === "Workspaces";
    }
    function isItemFamilyPageRoute(route = frappe.get_route()) {
      return Array.isArray(route) && route[0] === "retail-item-family-l";
    }
    function suppressCustomDocumentCards() {
      var _a2, _b2;
      const workspacePrototype = (_b2 = (_a2 = frappe.views) == null ? void 0 : _a2.Workspace) == null ? void 0 : _b2.prototype;
      if (!workspacePrototype || workspaceCustomCardsPatched)
        return !!workspacePrototype;
      const addCustomCards = workspacePrototype.add_custom_cards_in_content;
      if (typeof addCustomCards !== "function")
        return false;
      workspacePrototype.add_custom_cards_in_content = function() {
        addCustomCards.call(this);
        this.content = (this.content || []).filter(
          (block) => {
            var _a3;
            return !(block.type === "card" && ((_a3 = block.data) == null ? void 0 : _a3.card_name) === "Custom Documents");
          }
        );
      };
      workspaceCustomCardsPatched = true;
      return true;
    }
    function patchWorkspaceSidebarRoutes() {
      var _a2, _b2;
      const workspacePrototype = (_b2 = (_a2 = frappe.views) == null ? void 0 : _a2.Workspace) == null ? void 0 : _b2.prototype;
      if (!workspacePrototype)
        return false;
      if (workspaceSidebarRoutesPatched)
        return true;
      const renderItem = workspacePrototype.sidebar_item_container;
      const getPages = workspacePrototype.get_pages;
      if (typeof renderItem !== "function" || typeof getPages !== "function")
        return false;
      workspacePrototype.get_pages = function(...args) {
        return Promise.resolve(getPages.apply(this, args)).then((result) => {
          registerSidebarItems((result == null ? void 0 : result.pages) || []);
          return result;
        });
      };
      workspacePrototype.sidebar_item_container = function(item) {
        registerSidebarItems([item]);
        const $container = renderItem.call(this, item);
        const container = $container.get(0);
        container.setAttribute("item-workspace-name", item.name || item.title);
        if (item.is_report_group)
          container.dataset.retailReportGroup = "1";
        if (item.is_report_link)
          container.dataset.retailReportLink = "1";
        const target = getSidebarTarget(item);
        const anchor = container.querySelector(":scope > .desk-sidebar-item > .item-anchor");
        if (item.is_report_group) {
          configureReportGroupAnchor(anchor);
        } else if (anchor && target) {
          anchor.setAttribute("href", getTargetUrl(target));
          setAnchorRouteTarget(anchor, target);
        }
        return $container;
      };
      workspaceSidebarRoutesPatched = true;
      return true;
    }
    function waitForWorkspaceModule() {
      if (suppressCustomDocumentCards() && patchWorkspaceSidebarRoutes())
        return;
      let attempts = 0;
      const timer = setInterval(() => {
        attempts += 1;
        const ready = suppressCustomDocumentCards() && patchWorkspaceSidebarRoutes();
        if (ready || attempts >= 40)
          clearInterval(timer);
      }, 250);
    }
    function isReturnFilter(value) {
      return value === true || value === 1 || value === "1" || value === "true";
    }
    function getRouteParts(route) {
      return (route || []).filter((part) => !$.isPlainObject(part));
    }
    function getTargetRouteParts(target) {
      return getRouteParts(target);
    }
    function getTargetFilters(target) {
      return (target == null ? void 0 : target.find((part) => $.isPlainObject(part))) || {};
    }
    function getRouteFilters(route) {
      const queryFilters = {};
      new URLSearchParams(window.location.search).forEach((value, field) => {
        queryFilters[field] = value;
      });
      return Object.assign(
        {},
        (route == null ? void 0 : route.find((part) => $.isPlainObject(part))) || {},
        queryFilters,
        frappe.route_options || {}
      );
    }
    function normalizeFilterValue(value) {
      if (value === true)
        return "1";
      if (value === false)
        return "0";
      if (value === void 0 || value === null)
        return "";
      return String(value);
    }
    function routePartsMatch(currentParts, targetParts) {
      if (!currentParts.length || currentParts.length < targetParts.length)
        return false;
      return targetParts.every((part, index) => currentParts[index] === part);
    }
    function targetFiltersMatch(currentFilters, targetFilters) {
      return Object.entries(targetFilters).every(([field, value]) => normalizeFilterValue(currentFilters[field]) === normalizeFilterValue(value));
    }
    const SIDEBAR_CONTEXT_KEY = "retail_sidebar_context_v1";
    function getStoredSidebarChild(matches, visibleLabels) {
      let stored = null;
      try {
        stored = JSON.parse(sessionStorage.getItem(SIDEBAR_CONTEXT_KEY) || "null");
      } catch (e) {
        stored = null;
      }
      const child = stored == null ? void 0 : stored.child;
      if (!child || !visibleLabels.has(child))
        return null;
      const matchLabels = new Set(matches.map(([label]) => label));
      const aliasMatches = matches.some(([label]) => ROUTE_ALIAS_TO_CHILD[label] === child);
      return matchLabels.has(child) || aliasMatches ? child : null;
    }
    function rememberSidebarContext(label) {
      const child = ROUTE_ALIAS_TO_CHILD[label] || (getParentLabel(label) ? label : null);
      const main = child ? getTopParentLabel(child) : TOP_LEVEL_WORKSPACES.has(label) ? label : null;
      if (!main)
        return;
      try {
        sessionStorage.setItem(SIDEBAR_CONTEXT_KEY, JSON.stringify({ main, child, ts: Date.now() }));
      } catch (e) {
      }
    }
    function getMappedChildFromRoute(route, filters) {
      var _a2;
      const currentParts = getRouteParts(route);
      const visibleLabels = getVisibleSidebarLabels();
      const matches = Object.entries(DIRECT_MAPPING).sort((a, b) => Object.keys(getTargetFilters(b[1])).length - Object.keys(getTargetFilters(a[1])).length).filter(([, target]) => routePartsMatch(currentParts, getTargetRouteParts(target)) && targetFiltersMatch(filters, getTargetFilters(target)));
      const storedChild = getStoredSidebarChild(matches, visibleLabels);
      if (storedChild)
        return storedChild;
      const visibleMatch = (_a2 = matches.find(([label]) => visibleLabels.has(label))) == null ? void 0 : _a2[0];
      if (visibleMatch)
        return visibleMatch;
      const aliasMatch = matches.map(([label]) => ROUTE_ALIAS_TO_CHILD[label]).find((child) => child && visibleLabels.has(child));
      if (aliasMatch)
        return aliasMatch;
      return matches[0] ? ROUTE_ALIAS_TO_CHILD[matches[0][0]] || matches[0][0] : null;
    }
    function getTargetUrl(target) {
      const route = target.filter((part) => !$.isPlainObject(part));
      const filters = target.find((part) => $.isPlainObject(part));
      let url = frappe.router.make_url(frappe.router.convert_from_standard_route(route));
      if (filters && Object.keys(filters).length) {
        const params = new URLSearchParams(filters);
        url = `${url}?${params.toString()}`;
      }
      return url;
    }
    function clearListFilter(doctype, fieldname) {
      var _a2;
      if (((_a2 = window.cur_list) == null ? void 0 : _a2.doctype) !== doctype)
        return false;
      const filterArea = window.cur_list.filter_area;
      if (!(filterArea == null ? void 0 : filterArea.get().some((filter) => filter[1] === fieldname)))
        return false;
      filterArea.remove(fieldname);
      return true;
    }
    function resetSalesInvoiceListFilters() {
      var _a2, _b2;
      return [
        (_b2 = (_a2 = window.cur_list) == null ? void 0 : _a2.retail_reset_invoice_source) == null ? void 0 : _b2.call(_a2),
        clearListFilter("Sales Invoice", "is_return"),
        clearListFilter("Sales Invoice", "custom_is_van_sale")
      ].some(Boolean);
    }
    function clearSalesInvoiceListState(keepFields = []) {
      var _a2, _b2, _c2;
      const blockedFields = /* @__PURE__ */ new Set(["is_return", "custom_is_van_sale"]);
      keepFields.forEach((field) => blockedFields.delete(field));
      frappe.route_options = null;
      if (((_a2 = window.cur_list) == null ? void 0 : _a2.doctype) === "Sales Invoice") {
        let changed = Boolean((_c2 = (_b2 = window.cur_list).retail_reset_invoice_source) == null ? void 0 : _c2.call(_b2));
        blockedFields.forEach((field) => {
          changed = clearListFilter("Sales Invoice", field) || changed;
        });
        if (Array.isArray(window.cur_list.filters)) {
          const nextFilters = window.cur_list.filters.filter((filter) => !blockedFields.has(filter == null ? void 0 : filter[1]));
          changed = changed || nextFilters.length !== window.cur_list.filters.length;
          window.cur_list.filters = nextFilters;
        }
        return changed;
      }
      return false;
    }
    function normalizeSalesInvoiceListRoute(route, filters) {
      if (route[0] !== "List" || route[1] !== "Sales Invoice")
        return null;
      const hasFilters = filters && Object.keys(filters).length;
      if (hasFilters) {
        clearSalesInvoiceListState();
        return getTargetUrl(targetWithFilters(route, filters));
      }
      clearSalesInvoiceListState();
      return getTargetUrl(route);
    }
    function targetWithFilters(route, filters) {
      return filters && Object.keys(filters).length ? [...route, filters] : [...route];
    }
    function isVanSalesInvoiceWrapperRoute() {
      return Array.isArray(frappe.get_route()) && frappe.get_route()[0] === "retail-van-sales-invoice";
    }
    function routeToTarget(target) {
      const route = target.filter((part) => !$.isPlainObject(part));
      const filters = target.find((part) => $.isPlainObject(part));
      const salesInvoiceUrl = normalizeSalesInvoiceListRoute(route, filters);
      if (salesInvoiceUrl) {
        if (isVanSalesInvoiceWrapperRoute()) {
          window.location.href = salesInvoiceUrl;
          return Promise.resolve();
        }
        return routeToUrl(salesInvoiceUrl).then(() => {
          var _a2;
          const changed = !filters || !Object.keys(filters).length ? clearSalesInvoiceListState() : clearSalesInvoiceListState(Object.keys(filters));
          if (changed && ((_a2 = window.cur_list) == null ? void 0 : _a2.doctype) === "Sales Invoice") {
            return window.cur_list.refresh();
          }
        });
      }
      if (filters && Object.keys(filters).length) {
        return routeToUrl(getTargetUrl(target));
      }
      if (route[0] === "van-stock-view" || route[0] === "van-stock-request") {
        return routeToUrl(`/app/${route[0]}`);
      }
      const resetInvoiceFilters = route[0] === "List" && route[1] === "Sales Invoice" ? resetSalesInvoiceListFilters() : false;
      frappe.route_options = filters || null;
      return frappe.set_route(...route).then(() => {
        var _a2;
        if (resetInvoiceFilters && ((_a2 = window.cur_list) == null ? void 0 : _a2.doctype) === "Sales Invoice") {
          return window.cur_list.refresh();
        }
      });
    }
    function bindViewWebsiteToRetailHome() {
      var _a2, _b2;
      const websiteUrl = "/retail-home";
      if ((_b2 = (_a2 = window.frappe) == null ? void 0 : _a2.ui) == null ? void 0 : _b2.toolbar) {
        frappe.ui.toolbar.view_website = function() {
          const websiteTab = window.open();
          if (!websiteTab) {
            window.location.href = websiteUrl;
            return;
          }
          websiteTab.opener = null;
          websiteTab.location = websiteUrl;
        };
      }
      if (!window.__retail_view_website_bound) {
        window.__retail_view_website_bound = true;
        document.addEventListener("click", (event) => {
          var _a3, _b3, _c2;
          const item = (_b3 = (_a3 = event.target) == null ? void 0 : _a3.closest) == null ? void 0 : _b3.call(_a3, ".dropdown-menu a, .dropdown-menu button");
          if (!item || normalizeText(item.textContent) !== "view website")
            return;
          event.preventDefault();
          event.stopPropagation();
          (_c2 = event.stopImmediatePropagation) == null ? void 0 : _c2.call(event);
          const websiteTab = window.open(websiteUrl);
          if (websiteTab) {
            websiteTab.opener = null;
          } else {
            window.location.href = websiteUrl;
          }
        }, true);
      }
      document.querySelectorAll(".dropdown-menu a, .dropdown-menu button").forEach((item) => {
        if (normalizeText(item.textContent) !== "view website")
          return;
        if (item.dataset.retailViewWebsiteBound === "1")
          return;
        item.dataset.retailViewWebsiteBound = "1";
        if (item.tagName === "A") {
          item.setAttribute("href", websiteUrl);
        }
        item.addEventListener("click", (event) => {
          event.preventDefault();
          event.stopPropagation();
          const websiteTab = window.open(websiteUrl);
          if (websiteTab) {
            websiteTab.opener = null;
          } else {
            window.location.href = websiteUrl;
          }
        }, { capture: true });
      });
    }
    function getAnchorRouteTarget(anchor) {
      var _a2;
      const routeTarget = (_a2 = anchor == null ? void 0 : anchor.dataset) == null ? void 0 : _a2.retailRouteTarget;
      if (!routeTarget)
        return null;
      try {
        return JSON.parse(routeTarget);
      } catch (e) {
        return null;
      }
    }
    function setAnchorRouteTarget(anchor, target) {
      if (!anchor || !target)
        return;
      anchor.dataset.retailRouteTarget = JSON.stringify(target);
    }
    function getAnchorAppUrl(anchor) {
      const href = anchor == null ? void 0 : anchor.getAttribute("href");
      if (!href || href === "#")
        return "";
      const url = new URL(href, window.location.origin);
      if (url.origin !== window.location.origin || !frappe.router.is_app_route(url.pathname)) {
        return "";
      }
      return `${url.pathname}${url.search}${url.hash}`;
    }
    function getTargetFromUrl(anchor) {
      const appUrl = getAnchorAppUrl(anchor);
      if (!appUrl)
        return null;
      const path = appUrl.split(/[?#]/)[0].replace(/\/+$/, "");
      const purchaseInvoiceWorkspaceUrls = /* @__PURE__ */ new Set([
        "/app/purchase-invoice",
        "/app/purchase-invoices",
        "/app/purchase-bills"
      ]);
      if (purchaseInvoiceWorkspaceUrls.has(path)) {
        return DIRECT_MAPPING["Purchase Invoices"];
      }
      return null;
    }
    function waitForRoute() {
      return new Promise((resolve) => {
        setTimeout(() => {
          if (frappe.after_ajax) {
            frappe.after_ajax(resolve);
          } else {
            resolve();
          }
        }, 100);
      });
    }
    function routeToUrl(url, replace = false) {
      frappe.route_options = null;
      frappe.route_hash = null;
      const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;
      if (currentUrl !== url) {
        if (replace) {
          window.history.replaceState(null, null, url);
        } else {
          window.history.pushState(null, null, url);
        }
        frappe.router.route();
      }
      return waitForRoute();
    }
    function getWorkspaceUrl(workspaceName, isPublic = true) {
      const legacyName = workspaceName == null ? void 0 : workspaceName.replace(/ Desk$/, "");
      if (TOP_LEVEL_WORKSPACES.has(legacyName))
        workspaceName = legacyName;
      const slug = frappe.router.slug(workspaceName);
      return `/app/${isPublic ? slug : `private/${slug}`}`;
    }
    function isVisibleElement(element) {
      if (!element)
        return false;
      const style = window.getComputedStyle(element);
      return style.display !== "none" && style.visibility !== "hidden" && element.offsetParent !== null;
    }
    function unwrapElement(value) {
      if (!value)
        return null;
      if (value instanceof Element)
        return value;
      if (value.jquery)
        return value.get(0);
      if (value.wrapper instanceof Element)
        return value.wrapper;
      if (value.page instanceof Element)
        return value.page;
      return null;
    }
    function getVisiblePageContainers() {
      return Array.from(document.querySelectorAll(".page-container")).filter(isVisibleElement);
    }
    function getCurrentPage() {
      var _a2;
      const frappePage = unwrapElement((_a2 = frappe.container) == null ? void 0 : _a2.page);
      if (isVisibleElement(frappePage))
        return frappePage;
      const visiblePages = getVisiblePageContainers();
      return visiblePages[visiblePages.length - 1] || document.querySelector('.page-container[style*="display: block"]');
    }
    function getCurrentSideSection() {
      var _a2;
      const pageSideSection = (_a2 = getCurrentPage()) == null ? void 0 : _a2.querySelector(".layout-side-section");
      if (pageSideSection)
        return pageSideSection;
      const visibleSideSections = Array.from(document.querySelectorAll(".layout-side-section")).filter(isVisibleElement);
      return visibleSideSections[visibleSideSections.length - 1] || pageSideSection;
    }
    function getRetailSidebarContainers() {
      return document.querySelectorAll(".retail-persistent-sidebar .sidebar-item-container");
    }
    function getSelectableSidebarContainers() {
      return document.querySelectorAll(
        ".retail-persistent-sidebar .sidebar-item-container, .desk-sidebar .sidebar-item-container"
      );
    }
    function getItemLabel(container) {
      var _a2, _b2;
      return (_b2 = (_a2 = container == null ? void 0 : container.querySelector(":scope > .desk-sidebar-item > .item-anchor .sidebar-item-label")) == null ? void 0 : _a2.innerText) == null ? void 0 : _b2.trim();
    }
    function getSidebarRoutingLabel(container) {
      const label = getItemLabel(container);
      const workspaceName = container == null ? void 0 : container.getAttribute("item-workspace-name");
      if (workspaceName && (dynamicSidebarItems.has(workspaceName) || CHILD_TO_PARENT[workspaceName] || DIRECT_MAPPING[workspaceName] || WORKSPACE_TO_MODULE[workspaceName])) {
        return workspaceName;
      }
      return label;
    }
    function getParentLabel(label) {
      var _a2;
      return ((_a2 = dynamicSidebarItems.get(label)) == null ? void 0 : _a2.parent_page) || CHILD_TO_PARENT[label] || "";
    }
    function getTopParentLabel(label) {
      let current = label;
      const seen = /* @__PURE__ */ new Set();
      while (getParentLabel(current) && !seen.has(current)) {
        seen.add(current);
        current = getParentLabel(current);
      }
      return current;
    }
    function isDescendantOf(label, ancestor) {
      let current = label;
      const seen = /* @__PURE__ */ new Set();
      while (getParentLabel(current) && !seen.has(current)) {
        seen.add(current);
        current = getParentLabel(current);
        if (current === ancestor)
          return true;
      }
      return false;
    }
    function getSidebarIconLabel(container) {
      const workspaceName = container == null ? void 0 : container.getAttribute("item-workspace-name");
      if (workspaceName === "Manufacturing Reports")
        return "Manufacturing Child Reports";
      if (workspaceName === "Manufacturing Setup")
        return "Manufacturing Child Setup";
      return getItemLabel(container);
    }
    function getVisibleSidebarLabels() {
      const labels = /* @__PURE__ */ new Set();
      Array.from(getSelectableSidebarContainers()).forEach((container) => {
        const label = getItemLabel(container);
        const routingLabel = getSidebarRoutingLabel(container);
        if (label)
          labels.add(label);
        if (routingLabel)
          labels.add(routingLabel);
      });
      return labels;
    }
    function escapeHtml(value) {
      var _a2;
      if ((_a2 = frappe.utils) == null ? void 0 : _a2.escape_html)
        return frappe.utils.escape_html(value);
      return String(value || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
    }
    function getRouteState() {
      var _a2, _b2, _c2, _d, _e, _f;
      const route = frappe.get_route();
      const view = (_a2 = route == null ? void 0 : route[0]) == null ? void 0 : _a2.toLowerCase();
      const filters = getRouteFilters(route);
      const workspaceRoute = view === "workspaces" || view === "workspace" ? route[route[1] === "private" ? 2 : 1] : route == null ? void 0 : route[0];
      const mainWorkspace = Array.from(TOP_LEVEL_WORKSPACES).find(
        (name) => frappe.router.slug(name) === frappe.router.slug(workspaceRoute || "")
      );
      if (mainWorkspace)
        return { main: mainWorkspace, child: "" };
      if (VAN_PAGE_TO_CHILD[route == null ? void 0 : route[0]]) {
        return { main: "Van Sales", child: VAN_PAGE_TO_CHILD[route[0]] };
      }
      const pageTitle = (_c2 = (_b2 = document.querySelector(".page-title .title-text, .title-text")) == null ? void 0 : _b2.innerText) == null ? void 0 : _c2.trim();
      if (pageTitle === "Van Sales Invoice") {
        return { main: "Van Sales", child: "Van Sales Invoice" };
      }
      const reportItems = view === "query-report" ? Array.from(dynamicSidebarItems.values()).filter((item) => {
        var _a3;
        return item.is_report_link && ((_a3 = item.route) == null ? void 0 : _a3[1]) === route[1];
      }) : [];
      let storedChild;
      try {
        storedChild = (_d = JSON.parse(sessionStorage.getItem(SIDEBAR_CONTEXT_KEY) || "null")) == null ? void 0 : _d.child;
      } catch (error) {
      }
      const selectedReport = reportItems.find((item) => item.name === storedChild);
      if (selectedReport)
        return { main: "Reports", child: selectedReport.name };
      const mappedChild = getMappedChildFromRoute(route, filters);
      if (isItemFamilyPageRoute(route)) {
        return { main: "Items", child: "Item Family List" };
      }
      if (mappedChild) {
        return { main: getTopParentLabel(mappedChild) || DOCTYPE_TO_WORKSPACE[route == null ? void 0 : route[1]], child: mappedChild };
      }
      if (reportItems.length)
        return { main: "Reports", child: reportItems[0].name };
      if (view === "workspaces" || view === "workspace") {
        const title = decodeURIComponent(route[route[1] === "private" ? 2 : 1] || "");
        if (CHILD_TO_PARENT[title]) {
          return { main: CHILD_TO_PARENT[title], child: title };
        }
        return { main: title, child: "" };
      }
      const workspaceSlug = frappe.router.slug(
        (route == null ? void 0 : route[0]) === "private" ? (route == null ? void 0 : route[1]) || "" : (route == null ? void 0 : route[0]) || ""
      );
      const workspaceTitle = (_f = (_e = frappe.workspaces) == null ? void 0 : _e[workspaceSlug]) == null ? void 0 : _f.title;
      if (workspaceTitle) {
        if (CHILD_TO_PARENT[workspaceTitle]) {
          return { main: CHILD_TO_PARENT[workspaceTitle], child: workspaceTitle };
        }
        return { main: workspaceTitle, child: "" };
      }
      if (view === "list" || view === "form") {
        const doctype = route[1];
        let child = DOCTYPE_TO_CHILD[doctype];
        if (doctype === "Sales Invoice" && isReturnFilter(filters.is_return)) {
          child = "Sales Returns";
        } else if (doctype === "Purchase Receipt" && isReturnFilter(filters.is_return)) {
          child = "Purchase Returns";
        }
        return { main: DOCTYPE_TO_WORKSPACE[doctype], child };
      }
      return {};
    }
    function ensureRetailCss() {
      const fontHref = "/assets/frappe/css/fonts/fontawesome/font-awesome.min.css";
      if (!document.querySelector(`link[href="${fontHref}"]`)) {
        const fontLink = document.createElement("link");
        fontLink.rel = "stylesheet";
        fontLink.href = fontHref;
        document.head.appendChild(fontLink);
      }
      const href = "/assets/retail/css/retail_icons.css?v=32";
      if (document.querySelector('link[href^="/assets/retail/css/retail_icons.css"]'))
        return;
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = href;
      link.type = "text/css";
      link.onload = () => debugLog("retail_navigation: retail_icons.css loaded");
      link.onerror = () => console.error("retail_navigation: failed to load retail_icons.css");
      document.head.appendChild(link);
    }
    function injectRetailInlineCss() {
      if (document.getElementById("retail-icons-inline-css"))
        return;
      const css = `
        @media (min-width: 992px) {
            .sidebar-item-container .sidebar-item-icon > svg,
            .sidebar-item-container .sidebar-item-icon > .icon-sm,
            .sidebar-item-container .sidebar-item-icon > .es-icon { display: none !important; }

            .retail-icon {
                font-family: "FontAwesome" !important;
                font-weight: normal !important;
                width: 24px !important;
                text-align: center !important;
                margin-right: 10px !important;
                font-size: 15px !important;
                display: inline-block !important;
                vertical-align: middle !important;
            }

            .color-items    { color: #06b6d4 !important; }
            .color-sales    { color: #3b82f6 !important; }
            .color-purchase { color: #8b5cf6 !important; }
            .color-stock    { color: #f97316 !important; }
            .color-accounts { color: #10b981 !important; }
            .color-settings { color: #64748b !important; }
            .color-hr { color: #8b5cf6 !important; }
            .color-hr-recruitment { color: #ec4899 !important; }
            .color-hr-lifecycle { color: #06b6d4 !important; }
            .color-hr-performance { color: #f59e0b !important; }
            .color-hr-attendance { color: #3b82f6 !important; }
            .color-hr-expenses { color: #ef4444 !important; }
            .color-hr-leaves { color: #10b981 !important; }
            .color-pos-profiles { color: #8b5cf6 !important; }
            .color-pos-invoices { color: #0ea5e9 !important; }
            .color-pos-counters { color: #f97316 !important; }
            .color-pos-cashier-shifts { color: #14b8a6 !important; }
            .color-pos-counter-sessions { color: #2563eb !important; }
            .color-pos-opening { color: #10b981 !important; }
            .color-pos-closing { color: #ef4444 !important; }
            .color-pos-day-closing { color: #f59e0b !important; }
            .color-pos-sync { color: #64748b !important; }
            .color-pos-reports { color: #ec4899 !important; }

            .sidebar-item-label { display: inline-block !important; vertical-align: middle !important; }

            html[data-retail-brand-theme] .container,
            html[data-retail-brand-theme] .container-sm,
            html[data-retail-brand-theme] .container-md,
            html[data-retail-brand-theme] .container-lg,
            html[data-retail-brand-theme] .container-xl,
            body.retail-wide-desk .main-section,
            body.retail-wide-desk #body,
            body.retail-wide-desk .content,
            body.retail-wide-desk .navbar > .container,
            body.retail-wide-desk .page-head,
            body.retail-wide-desk .page-head .container,
            body.retail-wide-desk .page-container,
            body.retail-wide-desk .page-content,
            body.retail-wide-desk .page-wrapper,
            body.retail-wide-desk .layout-main,
            body.retail-wide-desk .page-body,
            body.retail-wide-desk .container,
            body.retail-wide-desk .layout-main-section-wrapper,
            body.retail-wide-desk .layout-main-section,
            body.retail-wide-desk .std-form-layout,
            body.retail-wide-desk .form-layout,
            body.retail-wide-desk .form-page {
                max-width: none !important;
                width: 100% !important;
            }

            body.retail-wide-desk .layout-main,
            body.retail-wide-desk .layout-main-section-wrapper {
                padding-left: 12px !important;
                padding-right: 12px !important;
            }

            body:has(.modal.show)[data-route^="Form/"] .form-grid,
            body:has(.modal.show)[data-route^="Form/"] .grid-body,
            body:has(.modal.show)[data-route^="Form/"] .rows,
            body:has(.modal.show)[data-route^="Form/"] .grid-row,
            body:has(.modal.show)[data-route^="Form/"] .data-row,
            body:has(.modal.show)[data-route^="Form/"] .grid-static-col,
            body:has(.modal.show)[data-route^="Form/"] .field-area {
                z-index: auto !important;
            }

            .retail-open-work {
                position: fixed;
                right: 10px;
                top: 112px;
                width: 48px;
                max-height: calc(100vh - 132px);
                background: rgba(255, 255, 255, 0.95);
                border: 1px solid var(--border-color);
                border-radius: 8px;
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
                display: flex;
                flex-direction: column;
                height: calc(100vh - 132px);
                overflow: hidden;
                pointer-events: auto;
                transition: width 160ms ease;
                z-index: 2000;
            }

            .retail-open-work:hover,
            .retail-open-work:focus-within {
                width: 248px;
            }

            .retail-open-work__head {
                align-items: center;
                display: grid;
                gap: 8px;
                grid-template-columns: 28px 1fr 28px;
                min-height: 42px;
                padding: 8px 10px;
                border-bottom: 1px solid var(--border-color);
                font-weight: 600;
                white-space: nowrap;
            }

            .retail-open-work__count {
                align-items: center;
                background: var(--blue-50);
                border-radius: 999px;
                color: var(--blue-700);
                display: inline-flex;
                font-size: 12px;
                height: 22px;
                justify-content: center;
                min-width: 22px;
            }

            .retail-open-work__title {
                opacity: 0;
                transition: opacity 120ms ease;
            }

            .retail-open-work:hover .retail-open-work__title,
            .retail-open-work:focus-within .retail-open-work__title {
                opacity: 1;
            }

            .retail-open-work__clear {
                align-items: center;
                background: transparent;
                border: 0;
                border-radius: 6px;
                color: var(--text-muted);
                cursor: pointer;
                display: inline-flex;
                font-size: 16px;
                height: 28px;
                justify-content: center;
                opacity: 0;
                width: 28px;
            }

            .retail-open-work:hover .retail-open-work__clear,
            .retail-open-work:focus-within .retail-open-work__clear {
                opacity: 1;
            }

            .retail-open-work__clear:hover,
            .retail-open-work__close:hover {
                background: var(--control-bg);
                color: var(--text-color);
            }

            .retail-open-work__list {
                display: block;
                flex: 1 1 auto;
                height: 100%;
                max-height: none;
                min-height: 0;
                overscroll-behavior: contain;
                overflow-y: scroll;
                overflow-x: hidden;
                padding: 6px;
                scrollbar-width: thin;
                -webkit-overflow-scrolling: touch;
            }

            .retail-open-work__item {
                align-items: center;
                background: transparent;
                border: 0;
                border-radius: 6px;
                color: var(--text-color);
                cursor: pointer;
                display: grid;
                gap: 8px;
                grid-template-columns: 28px 10px 1fr 24px;
                min-height: 36px;
                padding: 4px;
                text-align: left;
                text-decoration: none;
                width: 100%;
            }

            .retail-open-work__item + .retail-open-work__item {
                margin-top: 4px;
            }

            .retail-open-work__item:hover,
            .retail-open-work__item.is-active {
                background: var(--control-bg);
            }

            .retail-open-work__abbr {
                align-items: center;
                background: var(--gray-100);
                border-radius: 6px;
                color: var(--text-muted);
                display: inline-flex;
                font-size: 11px;
                font-weight: 700;
                height: 28px;
                justify-content: center;
                width: 28px;
            }

            .retail-open-work__item.is-active .retail-open-work__abbr {
                background: var(--blue-100);
                color: var(--blue-700);
            }

            .retail-open-work__status-dot {
                align-self: center;
                border-radius: 50%;
                display: inline-block;
                height: 8px;
                opacity: 0.95;
                width: 8px;
            }

            .retail-open-work__status-dot.is-not-saved {
                background: #ef4444;
            }

            .retail-open-work__status-dot.is-saved {
                background: #f97316;
            }

            .retail-open-work__status-dot.is-final {
                background: #22c55e;
            }

            .retail-open-work__status-dot.is-page {
                background: #94a3b8;
            }

            .retail-open-work__label {
                min-width: 0;
                opacity: 0;
                overflow: hidden;
                text-overflow: ellipsis;
                transition: opacity 120ms ease;
                white-space: nowrap;
            }

            .retail-open-work:hover .retail-open-work__label,
            .retail-open-work:focus-within .retail-open-work__label {
                opacity: 1;
            }

            .retail-open-work__close {
                align-items: center;
                background: transparent;
                border: 0;
                border-radius: 6px;
                color: var(--text-muted);
                cursor: pointer;
                display: inline-flex;
                height: 24px;
                justify-content: center;
                opacity: 0;
                width: 24px;
            }

            .retail-open-work:hover .retail-open-work__close,
            .retail-open-work:focus-within .retail-open-work__close {
                opacity: 1;
            }

            .retail-open-work__status {
                border-top: 1px solid var(--border-color);
                color: var(--text-muted);
                font-size: 11px;
                opacity: 0;
                overflow: hidden;
                padding: 6px 10px;
                text-overflow: ellipsis;
                transition: opacity 120ms ease;
                white-space: nowrap;
            }

            .retail-open-work:hover .retail-open-work__status,
            .retail-open-work:focus-within .retail-open-work__status {
                opacity: 1;
            }
        }

        @media (max-width: 991px) {
            .retail-open-work { display: none !important; }
        }
        `;
      const style = document.createElement("style");
      style.id = "retail-icons-inline-css";
      style.appendChild(document.createTextNode(css));
      document.head.appendChild(style);
    }
    function applyIcons() {
      const containers = document.querySelectorAll(".sidebar-item-container");
      if (!containers.length) {
        debugLog("retail_navigation: no sidebar containers found");
        return;
      }
      debugLog("retail_navigation: sidebar containers found", containers.length);
      containers.forEach((container) => {
        const labelEl = container.querySelector(":scope > .desk-sidebar-item > .item-anchor .sidebar-item-label");
        const iconContainer = container.querySelector(":scope > .desk-sidebar-item > .item-anchor .sidebar-item-icon");
        const labelText = normalizeText(getSidebarIconLabel(container) || (labelEl == null ? void 0 : labelEl.innerText));
        const config = findIconConfig(labelText);
        if (!config)
          return;
        debugLog("retail_navigation: matched item", labelText, config.icon, config.cls);
        if (iconContainer) {
          if (iconContainer.querySelector(".retail-icon"))
            return;
          iconContainer.innerHTML = "";
          iconContainer.appendChild(createIconElement(config));
        } else if (labelEl) {
          if (container.querySelector(".retail-icon"))
            return;
          labelEl.prepend(createIconElement(config));
        }
      });
    }
    function applyDisplayLabels() {
      document.querySelectorAll(".sidebar-item-container").forEach((container) => {
        var _a2;
        const workspaceName = container.getAttribute("item-workspace-name");
        const labelEl = container.querySelector(":scope > .desk-sidebar-item > .item-anchor .sidebar-item-label");
        const rawLabel = (_a2 = labelEl == null ? void 0 : labelEl.innerText) == null ? void 0 : _a2.trim();
        const displayLabel = WORKSPACE_DISPLAY_LABELS[workspaceName] || WORKSPACE_DISPLAY_LABELS[rawLabel];
        if (!displayLabel)
          return;
        if (!labelEl || labelEl.innerText.trim() === displayLabel)
          return;
        labelEl.innerText = __(displayLabel);
        const anchor = container.querySelector(":scope > .desk-sidebar-item > .item-anchor");
        anchor == null ? void 0 : anchor.setAttribute("title", __(displayLabel));
      });
    }
    function hideStandardHomeSidebarItems() {
      document.querySelectorAll(".sidebar-item-container").forEach((container) => {
        const label = getItemLabel(container);
        const workspaceName = container.getAttribute("item-workspace-name") || label;
        if (HIDDEN_SIDEBAR_LABELS.has(label) || HIDDEN_SIDEBAR_LABELS.has(workspaceName)) {
          container.classList.add("hidden");
          container.style.display = "none";
          return;
        }
        if (workspaceName === "Business Home" || label === "Business Home")
          return;
        if (label !== "Home" && workspaceName !== "Home")
          return;
        container.classList.add("hidden");
        container.style.display = "none";
      });
    }
    function hideUnauthorizedSidebarItems() {
      var _a2;
      if (getRoleAllowedSidebarWorkspaces() === null && !Array.isArray((_a2 = frappe.boot) == null ? void 0 : _a2.retail_sidebar_selection))
        return;
      document.querySelectorAll(".sidebar-item-container").forEach((container) => {
        const label = getItemLabel(container);
        const workspaceName = container.getAttribute("item-workspace-name");
        if (HIDDEN_SIDEBAR_LABELS.has(label) || HIDDEN_SIDEBAR_LABELS.has(workspaceName)) {
          container.classList.add("hidden");
          container.style.display = "none";
          return;
        }
        const allowed = sidebarItemIsAllowed({
          name: workspaceName || label,
          title: workspaceName || label
        });
        container.classList.toggle("hidden", !allowed);
        container.style.display = allowed ? "" : "none";
      });
    }
    function setDropIcon(container, open) {
      var _a2, _b2;
      const use = container == null ? void 0 : container.querySelector(":scope > .desk-sidebar-item .drop-icon use");
      if (use)
        use.setAttribute("href", open ? "#es-small-down" : "#es-small-right");
      (_a2 = container == null ? void 0 : container.querySelector(":scope > .desk-sidebar-item .drop-icon")) == null ? void 0 : _a2.setAttribute("aria-expanded", String(!!open));
      (_b2 = container == null ? void 0 : container.querySelector(":scope > .desk-sidebar-item > .item-anchor[data-retail-report-group]")) == null ? void 0 : _b2.setAttribute("aria-expanded", String(!!open));
    }
    function getSmallDropIcon(open) {
      return `<svg class="es-icon retail-small-chevron" aria-hidden="true">
            <use href="${open ? "#es-small-down" : "#es-small-right"}"></use>
        </svg>`;
    }
    function setSidebarExpanded(container, open) {
      const section = container == null ? void 0 : container.querySelector(":scope > .sidebar-child-item");
      if (!section)
        return;
      section.classList.toggle("hidden", !open);
      if (open) {
        section.querySelectorAll(":scope > .sidebar-item-container").forEach((child) => {
          if (!sidebarItemIsAllowed({ name: getWorkspaceName(child), title: getItemLabel(child) }))
            return;
          child.classList.remove("hidden");
          child.style.removeProperty("display");
        });
      }
      setDropIcon(container, open);
    }
    function getVanForcedChildLabel() {
      var _a2, _b2;
      const path = window.location.pathname.replace(/\/+$/, "");
      const title = (_b2 = (_a2 = document.querySelector(".page-title .title-text, .title-text")) == null ? void 0 : _a2.innerText) == null ? void 0 : _b2.trim();
      const route = frappe.get_route();
      const routeMap = {
        "List:Van Fleet": "Van Sales Fleet Link",
        "List:Driver": "Van Sales Driver Link",
        "List:Van Session": "Van Sales Sessions Link",
        "List:Item": "Van Sales Items Link",
        "List:Warehouse": "Van Sales Warehouses Link",
        "query-report:Van Daily Sales Summary": "Van Sales Reports Link",
        "query-report:Van Daily Stock Summary": "Van Sales Reports Link",
        "query-report:Van Detailed Sales Summary": "Van Sales Reports Link",
        "query-report:Van Profit Report": "Van Sales Reports Link",
        "query-report:Van Wastage Report": "Van Sales Reports Link",
        "query-report:Van Outstanding Collection Summary": "Van Sales Reports Link"
      };
      const pageTitleMap = {
        "Van Fleet": "Van Sales Fleet Link",
        "Driver": "Van Sales Driver Link",
        "Van Session": "Van Sales Sessions Link",
        "Van Sessions": "Van Sales Sessions Link",
        "Van Sales Invoice": "Van Sales Invoice",
        "Van Payment": "Van Payments",
        "Van Payments": "Van Payments",
        "Stock Request": "Stock Request",
        "Van Stock Entries": "Van Stock Entries",
        "Van Stock View": "Van Stock View",
        "Van Customers": "Van Customers",
        "Item": "Van Sales Items Link",
        "Item List": "Van Sales Items Link",
        "Warehouse": "Van Sales Warehouses Link",
        "Warehouse List": "Van Sales Warehouses Link",
        "Van Sales Reports": "Van Sales Reports Link"
      };
      const pathMap = {
        "/app/retail-van-sales-invoice": "Van Sales Invoice",
        "/app/van-payments": "Van Payments",
        "/app/van-stock-request": "Stock Request",
        "/app/van-stock-entries": "Van Stock Entries",
        "/app/van-stock-view": "Van Stock View",
        "/app/van-customers": "Van Customers"
      };
      return routeMap[`${route == null ? void 0 : route[0]}:${route == null ? void 0 : route[1]}`] || pathMap[path] || pageTitleMap[title] || "";
    }
    function getContainerDisplayLabel(container) {
      const label = getItemLabel(container);
      const workspaceName = container == null ? void 0 : container.getAttribute("item-workspace-name");
      return WORKSPACE_DISPLAY_LABELS[workspaceName] || WORKSPACE_DISPLAY_LABELS[label] || label;
    }
    function forceVanSidebarSelection() {
      const state = getRouteState();
      if (state.main && state.main !== "Van Sales")
        return;
      const forcedChild = getVanForcedChildLabel();
      if (!forcedChild)
        return;
      getSelectableSidebarContainers().forEach((container) => {
        const displayLabel = getContainerDisplayLabel(container);
        const routingLabel = getSidebarRoutingLabel(container);
        const directItem = container.querySelector(":scope > .desk-sidebar-item");
        const childSection = container.querySelector(":scope > .sidebar-child-item");
        const isVanMain = displayLabel === "Van Sales";
        const isVanChild = CHILD_TO_PARENT[routingLabel] === "Van Sales" || CHILD_TO_PARENT[displayLabel] === "Van Sales";
        const isForcedChild = displayLabel === forcedChild || routingLabel === forcedChild;
        if (isVanMain && childSection && !manuallyClosedSidebarGroups.has("Van Sales")) {
          childSection.classList.remove("hidden");
          setDropIcon(container, true);
        }
        if (!isVanMain && !isVanChild)
          return;
        container.classList.toggle("retail-primary-active", isVanMain);
        container.classList.toggle("retail-secondary-active", isForcedChild);
        directItem == null ? void 0 : directItem.classList.toggle("selected", isVanMain || isForcedChild);
      });
    }
    function syncSidebarState() {
      const state = getRouteState();
      const routeKey = (frappe.get_route() || []).join("/");
      if (routeKey !== lastSidebarStateRouteKey) {
        manuallyClosedSidebarGroups.clear();
        lastSidebarStateRouteKey = routeKey;
      }
      const userOpenGroups = readOpenSidebarGroups();
      getSelectableSidebarContainers().forEach((container) => {
        const label = getItemLabel(container);
        const routingLabel = getSidebarRoutingLabel(container);
        const displayRoutingLabel = WORKSPACE_DISPLAY_LABELS[routingLabel] || routingLabel;
        const directItem = container.querySelector(":scope > .desk-sidebar-item");
        const childSection = container.querySelector(":scope > .sidebar-child-item");
        const isMain = label && state.main === label;
        const isChild = routingLabel && state.child === routingLabel || displayRoutingLabel && state.child === displayRoutingLabel || label && state.child === label;
        const displayMatchKey = Object.keys(WORKSPACE_DISPLAY_LABELS).find(
          (key) => WORKSPACE_DISPLAY_LABELS[key] === state.child
        );
        const stateChild = getParentLabel(state.child) ? state.child : displayMatchKey;
        const isAncestor = !!(routingLabel && stateChild && isDescendantOf(stateChild, routingLabel));
        const wasOpenedByUser = userOpenGroups.has(routingLabel) || userOpenGroups.has(label);
        const wasClosedByUser = manuallyClosedSidebarGroups.has(routingLabel) || manuallyClosedSidebarGroups.has(label);
        const shouldOpen = !wasClosedByUser && (isMain || wasOpenedByUser || isAncestor);
        container.classList.toggle("retail-primary-active", !!isMain);
        container.classList.toggle("retail-secondary-active", !!isChild);
        container.classList.toggle("retail-ancestor-active", isAncestor && !isMain);
        directItem == null ? void 0 : directItem.classList.toggle("selected", !!(isMain || isChild));
        if (childSection) {
          setSidebarExpanded(container, !!shouldOpen);
        }
      });
    }
    function ensureWorkspaceDropIcons() {
      var _a2;
      if (!isWorkspaceRoute(frappe.get_route()))
        return;
      (_a2 = getCurrentPage()) == null ? void 0 : _a2.querySelectorAll(".desk-sidebar:not(.retail-persistent-sidebar) .sidebar-item-container").forEach((container) => {
        const childSection = container.querySelector(":scope > .sidebar-child-item");
        const control = container.querySelector(":scope > .desk-sidebar-item > .sidebar-item-control");
        if (!childSection || !control || !childSection.children.length)
          return;
        let button = control.querySelector(":scope > .retail-drop-icon");
        if (!button) {
          button = document.createElement("button");
          button.className = "btn-reset drop-icon retail-drop-icon";
          button.type = "button";
          button.innerHTML = getSmallDropIcon(!childSection.classList.contains("hidden"));
          control.querySelectorAll(":scope > .drop-icon").forEach((icon) => icon.remove());
          control.appendChild(button);
        }
        button.classList.remove("hidden");
        setDropIcon(container, !childSection.classList.contains("hidden"));
      });
    }
    function syncDesktopSidebarClass() {
      const hasSidebar = isDesktop() && !!document.querySelector(".layout-side-section .retail-persistent-sidebar");
      document.body.classList.toggle("retail-has-persistent-sidebar", hasSidebar);
    }
    function isWideDeskRoute(route = frappe.get_route()) {
      if (!isDesktop() || !Array.isArray(route) || route.length === 0) {
        return false;
      }
      return !["Form", "query-report"].includes(route[0]);
    }
    function applyWideTransactionLayout() {
      const enabled = isWideDeskRoute();
      document.body.classList.toggle("retail-wide-transaction-form", enabled);
      document.body.classList.toggle("retail-wide-desk", enabled);
      const selectors = [
        ".main-section",
        "#body",
        ".content",
        ".navbar > .container",
        ".container-sm",
        ".container-md",
        ".container-lg",
        ".container-xl",
        ".page-head",
        ".page-head .container",
        ".page-container",
        ".page-content",
        ".page-wrapper",
        ".layout-main",
        ".page-body",
        ".container",
        ".layout-main-section-wrapper",
        ".layout-main-section",
        ".std-form-layout",
        ".form-layout",
        ".form-page"
      ];
      selectors.forEach((selector) => {
        document.querySelectorAll(selector).forEach((element) => {
          if (enabled) {
            element.style.setProperty("max-width", "none", "important");
            element.style.setProperty("width", "100%", "important");
          } else {
            element.style.removeProperty("max-width");
            element.style.removeProperty("width");
          }
        });
      });
      document.querySelectorAll(".layout-main-section-wrapper").forEach((element) => {
        if (enabled) {
          element.style.setProperty("padding-left", "12px", "important");
          element.style.setProperty("padding-right", "12px", "important");
        } else {
          element.style.removeProperty("padding-left");
          element.style.removeProperty("padding-right");
        }
      });
    }
    function readOpenWorkTabs() {
      try {
        const tabs = JSON.parse(sessionStorage.getItem(OPEN_WORK_STORAGE_KEY) || "[]");
        const cutoff = Date.now() - OPEN_WORK_TTL_MS;
        const validTabs = Array.isArray(tabs) ? tabs.filter((tab) => (tab == null ? void 0 : tab.key) && Array.isArray(tab.route) && (tab.updated_at || 0) >= cutoff) : [];
        const seen = /* @__PURE__ */ new Set();
        return validTabs.filter((tab) => {
          if (seen.has(tab.key))
            return false;
          seen.add(tab.key);
          return true;
        });
      } catch (error) {
        return [];
      }
    }
    function writeOpenWorkTabs(tabs) {
      sessionStorage.setItem(OPEN_WORK_STORAGE_KEY, JSON.stringify(tabs));
    }
    function getCurrentWorkTab() {
      const route = frappe.get_route();
      if (!Array.isArray(route) || !route.length)
        return null;
      const view = route[0];
      if (isItemFamilyPageRoute(route)) {
        return {
          key: route.join("/"),
          route: route.filter((part) => typeof part !== "object"),
          label: "Item Family List",
          type: "Item Family List",
          status: "page",
          updated_at: Date.now()
        };
      }
      if (!["Form", "List", "query-report"].includes(view))
        return null;
      const doctype = route[1] || view;
      const name = route[2] || "";
      const doc = view === "Form" ? cur_frm == null ? void 0 : cur_frm.doc : null;
      const routeParts = route.filter((part) => typeof part !== "object");
      const key = (doc == null ? void 0 : doc.__islocal) ? `Form/${doctype}/__new__` : routeParts.join("/");
      const title = (doc == null ? void 0 : doc.__islocal) ? `New ${doctype}` : (doc == null ? void 0 : doc.title) || (doc == null ? void 0 : doc.supplier_name) || (doc == null ? void 0 : doc.customer_name) || (doc == null ? void 0 : doc.item_name) || name || doctype;
      return {
        key,
        route: routeParts,
        label: view === "List" ? doctype : title,
        type: doctype,
        status: getCurrentWorkStatus(view, doc),
        updated_at: Date.now()
      };
    }
    function getCurrentWorkStatus(view, doc) {
      var _a2;
      if (view !== "Form" || !doc)
        return "page";
      if ((_a2 = cur_frm == null ? void 0 : cur_frm.is_dirty) == null ? void 0 : _a2.call(cur_frm))
        return "not_saved";
      if (doc.docstatus === 1)
        return "final";
      if (doc.docstatus === 0)
        return "saved";
      return "page";
    }
    function getWorkStatusClass(status) {
      return {
        not_saved: "is-not-saved",
        saved: "is-saved",
        final: "is-final",
        page: "is-page"
      }[status] || "is-page";
    }
    function getWorkStatusLabel(status) {
      return {
        not_saved: __("Not saved"),
        saved: __("Saved"),
        final: __("Final"),
        page: __("Page")
      }[status] || __("Page");
    }
    function upsertCurrentWorkTab() {
      const tab = getCurrentWorkTab();
      if (!tab)
        return;
      if (openWorkClearedRouteKey === tab.key)
        return;
      openWorkClearedRouteKey = null;
      const tabs = readOpenWorkTabs();
      const existingIndex = tabs.findIndex((existing) => existing.key === tab.key);
      if (existingIndex >= 0) {
        tabs[existingIndex] = __spreadValues(__spreadValues({}, tabs[existingIndex]), tab);
      } else {
        tabs.unshift(tab);
      }
      writeOpenWorkTabs(tabs);
      renderOpenWorkTabs();
    }
    function closeOpenWorkTab(key) {
      var _a2;
      const currentKey = (_a2 = getCurrentWorkTab()) == null ? void 0 : _a2.key;
      if (key === currentKey) {
        openWorkClearedRouteKey = key;
      }
      writeOpenWorkTabs(readOpenWorkTabs().filter((tab) => tab.key !== key));
      renderOpenWorkTabs();
    }
    function closeAllOpenWorkTabs() {
      var _a2;
      openWorkClearedRouteKey = ((_a2 = getCurrentWorkTab()) == null ? void 0 : _a2.key) || null;
      sessionStorage.removeItem(OPEN_WORK_STORAGE_KEY);
      renderOpenWorkTabs();
    }
    function openWorkTab(tab) {
      var _a2;
      if (!((_a2 = tab == null ? void 0 : tab.route) == null ? void 0 : _a2.length))
        return;
      try {
        frappe.route_options = null;
        frappe.route_hash = null;
        frappe.set_route(...tab.route);
      } catch (error) {
        window.location.href = getOpenWorkHref(tab.route);
      }
    }
    function getOpenWorkHref(route) {
      try {
        return frappe.router.make_url(frappe.router.convert_from_standard_route(route));
      } catch (error) {
        return `/app/${route.map((part) => encodeURIComponent(String(part))).join("/")}`;
      }
    }
    function getWorkAbbr(tab) {
      const source = tab.type || tab.label || "";
      return source.split(/\s+/).filter(Boolean).slice(0, 2).map((word) => word[0]).join("").toUpperCase() || "W";
    }
    function escapeAttribute(value) {
      return String(value || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }
    function ensureOpenWorkPanel() {
      if (!isDesktop())
        return null;
      let panel = document.querySelector(".retail-open-work");
      if (panel)
        return panel;
      panel = document.createElement("aside");
      panel.className = "retail-open-work";
      panel.setAttribute("aria-label", __("Open Work"));
      document.body.appendChild(panel);
      return panel;
    }
    function handleOpenWorkPointer(event) {
      var _a2, _b2, _c2;
      const clearButton = event.target.closest(".retail-open-work__clear");
      if (clearButton) {
        if (!clearButton.closest(".retail-open-work"))
          return;
        event.preventDefault();
        event.stopPropagation();
        (_a2 = event.stopImmediatePropagation) == null ? void 0 : _a2.call(event);
        closeAllOpenWorkTabs();
        return;
      }
      const closeButton = event.target.closest(".retail-open-work__close");
      if (closeButton) {
        if (!closeButton.closest(".retail-open-work"))
          return;
        event.preventDefault();
        event.stopPropagation();
        (_b2 = event.stopImmediatePropagation) == null ? void 0 : _b2.call(event);
        closeOpenWorkTab(closeButton.dataset.key);
        return;
      }
      const item = event.target.closest(".retail-open-work__item");
      if (!item || !item.closest(".retail-open-work"))
        return;
      event.preventDefault();
      event.stopPropagation();
      (_c2 = event.stopImmediatePropagation) == null ? void 0 : _c2.call(event);
      const tab = readOpenWorkTabs().find((entry) => entry.key === item.dataset.key);
      openWorkTab(tab);
    }
    function bindOpenWorkEvents() {
      if (window.__retailOpenWorkEventsBound)
        return;
      window.__retailOpenWorkEventsBound = true;
      document.addEventListener("pointerdown", handleOpenWorkPointer, true);
    }
    function renderOpenWorkTabs() {
      var _a2, _b2;
      const tabs = readOpenWorkTabs();
      if (!tabs.length) {
        (_a2 = document.querySelector(".retail-open-work")) == null ? void 0 : _a2.remove();
        return;
      }
      const panel = ensureOpenWorkPanel();
      if (!panel)
        return;
      const currentKey = (_b2 = getCurrentWorkTab()) == null ? void 0 : _b2.key;
      const status = panel.dataset.status || __("Recent Tabs");
      panel.innerHTML = `
            <div class="retail-open-work__head">
                <span class="retail-open-work__count">${tabs.length}</span>
                <span class="retail-open-work__title">${__("Open Work")}</span>
                <button class="retail-open-work__clear" type="button" title="${__("Close All")}" aria-label="${__("Close All")}">x</button>
            </div>
            <div class="retail-open-work__list">
                ${tabs.map((tab) => `
                    <a class="retail-open-work__item ${tab.key === currentKey ? "is-active" : ""}"
                        href="${escapeAttribute(getOpenWorkHref(tab.route))}"
                        data-key="${escapeAttribute(tab.key)}" title="${escapeAttribute(tab.label)}">
                        <span class="retail-open-work__abbr">${escapeHtml(getWorkAbbr(tab))}</span>
                        <span class="retail-open-work__status-dot ${getWorkStatusClass(tab.status)}"
                            title="${escapeAttribute(getWorkStatusLabel(tab.status))}"></span>
                        <span class="retail-open-work__label">${escapeHtml(tab.label)}</span>
                        <span class="retail-open-work__close" data-key="${escapeAttribute(tab.key)}" title="${__("Close")}">\xD7</span>
                    </a>
                `).join("")}
            </div>
            <div class="retail-open-work__status">${escapeHtml(status)}</div>
        `;
    }
    function removePersistentSidebar() {
      document.querySelectorAll(".retail-sidebar-overlay").forEach((sidebar) => sidebar.remove());
      document.querySelectorAll(".retail-persistent-sidebar").forEach((sidebar) => sidebar.remove());
      syncDesktopSidebarClass();
    }
    function getRetailSidebarHost(sideSection) {
      let host = sideSection.querySelector(":scope > .retail-sidebar-host");
      if (!host) {
        host = document.createElement("div");
        host.className = "retail-sidebar-host";
        sideSection.prepend(host);
      }
      return host;
    }
    function getWorkspaceName(container) {
      const label = getItemLabel(container);
      return (container == null ? void 0 : container.getAttribute("item-workspace-name")) || (container == null ? void 0 : container.getAttribute("item-name")) || WORKSPACE_ROUTE_NAMES[label] || label;
    }
    function readOpenSidebarGroups() {
      try {
        const groups = JSON.parse(sessionStorage.getItem(OPEN_SIDEBAR_STORAGE_KEY) || "[]");
        return new Set(Array.isArray(groups) ? groups.filter(Boolean) : []);
      } catch (error) {
        return /* @__PURE__ */ new Set();
      }
    }
    function writeOpenSidebarGroups(groups) {
      sessionStorage.setItem(OPEN_SIDEBAR_STORAGE_KEY, JSON.stringify(Array.from(groups)));
    }
    function rememberOpenSidebarGroup(label, open = true) {
      if (!label)
        return;
      const groups = readOpenSidebarGroups();
      if (open) {
        groups.add(label);
        manuallyClosedSidebarGroups.delete(label);
      } else {
        groups.delete(label);
        manuallyClosedSidebarGroups.add(label);
      }
      writeOpenSidebarGroups(groups);
    }
    function getSidebarMountSections() {
      const currentSideSection = getCurrentSideSection();
      if (!currentSideSection)
        return [];
      const overlay = currentSideSection.querySelector(".overlay-sidebar:not(.retail-sidebar-overlay)");
      return [isMobile() && overlay ? overlay : currentSideSection];
    }
    function buildPersistentSidebar(items) {
      registerSidebarItems(items);
      const seen = /* @__PURE__ */ new Set();
      const visibleItems = items.filter((item) => {
        const itemTitle = item.title || item.name;
        const key = `${item.parent_page || ""}:${itemTitle}`;
        if (seen.has(key))
          return false;
        seen.add(key);
        return !item.is_hidden && !["Home"].includes(itemTitle) && !HIDDEN_SIDEBAR_LABELS.has(itemTitle) && !HIDDEN_SIDEBAR_LABELS.has(item.name) && sidebarItemIsAllowed(item);
      });
      const publicItems = visibleItems.filter((item) => item.public);
      const roots = publicItems.filter((item) => !item.parent_page);
      const wrapper = document.createElement("div");
      wrapper.className = "retail-persistent-sidebar standard-sidebar-section nested-container";
      wrapper.dataset.title = "CELESTA";
      roots.forEach((item) => wrapper.appendChild(buildSidebarItem(item, publicItems)));
      return wrapper;
    }
    function mountPersistentSidebar(section, items) {
      var _a2;
      if (!section)
        return;
      const host = getRetailSidebarHost(section);
      const sideSection = section.closest(".layout-side-section") || section;
      const sidebars = Array.from(sideSection.querySelectorAll(".retail-persistent-sidebar"));
      const sidebar = sidebars.shift();
      sidebars.forEach((duplicate) => duplicate.remove());
      if (sidebar) {
        if (sidebar.parentElement !== host)
          host.prepend(sidebar);
      } else {
        host.prepend(buildPersistentSidebar(items));
      }
      if (isDesktop() && ((_a2 = frappe.get_route()) == null ? void 0 : _a2[1]) === "POS Operator Privilege") {
        sideSection.classList.remove("hide-sidebar");
        sideSection.style.removeProperty("display");
      }
      const route = frappe.get_route();
      sideSection.classList.toggle("retail-form-navigation", (route == null ? void 0 : route[0]) === "Form");
      if (isDesktop() && (route == null ? void 0 : route[0]) === "Form") {
        sideSection.classList.remove("hide-sidebar");
        sideSection.style.removeProperty("display");
      }
      section.classList.add("retail-form-sidebar-mounted");
      section.classList.toggle("retail-mobile-sidebar-mounted", section.classList.contains("overlay-sidebar"));
    }
    function configureReportGroupAnchor(anchor) {
      if (!anchor)
        return;
      anchor.removeAttribute("href");
      anchor.removeAttribute("data-retail-route-target");
      anchor.removeAttribute("data-retail-direct-link");
      anchor.setAttribute("data-retail-report-group", "1");
      anchor.setAttribute("role", "button");
      anchor.setAttribute("tabindex", "0");
    }
    function bindSubmenuRouting() {
      document.addEventListener("click", (event) => {
        var _a2;
        const container = event.target.closest(".sidebar-item-container");
        if (!container)
          return;
        const item = dynamicSidebarItems.get(getWorkspaceName(container));
        if (!(item == null ? void 0 : item.is_report_group) && container.dataset.retailReportGroup !== "1")
          return;
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        const section = container.querySelector(":scope > .sidebar-child-item");
        if (!section)
          return;
        const open = section.classList.contains("hidden");
        Array.from(((_a2 = container.parentElement) == null ? void 0 : _a2.children) || []).forEach((sibling) => {
          if (sibling === container || !sibling.matches(".sidebar-item-container"))
            return;
          setSidebarExpanded(sibling, false);
          rememberOpenSidebarGroup(getSidebarRoutingLabel(sibling) || getItemLabel(sibling), false);
        });
        setSidebarExpanded(container, open);
        rememberOpenSidebarGroup(getSidebarRoutingLabel(container) || getItemLabel(container), open);
      }, true);
      document.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ")
          return;
        const anchor = event.target.closest(".item-anchor[data-retail-report-group]");
        if (!anchor)
          return;
        event.preventDefault();
        anchor.click();
      });
      document.addEventListener("click", (event) => {
        var _a2, _b2;
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)
          return;
        const targetElement = event.target.closest("a, button, .shortcut-widget-box, .widget, .sidebar-item-container");
        if (!targetElement)
          return;
        const text = normalizeText(targetElement.innerText || targetElement.textContent || "");
        const title = normalizeText(((_a2 = targetElement.getAttribute) == null ? void 0 : _a2.call(targetElement, "title")) || "");
        const pageTargets = {
          "van stock view": ["van-stock-view", "Van Stock View"],
          "stock request": ["van-stock-request", "Stock Request"],
          "van stock request": ["van-stock-request", "Stock Request"]
        };
        const pageTarget = pageTargets[text] || pageTargets[title];
        if (!pageTarget)
          return;
        if (!routeIsAllowed([pageTarget[0]]))
          return;
        event.preventDefault();
        event.stopPropagation();
        (_b2 = event.stopImmediatePropagation) == null ? void 0 : _b2.call(event);
        rememberSidebarContext(pageTarget[1]);
        routeToTarget([pageTarget[0]]).then(() => {
          syncSidebarState();
          scheduleRetry();
        });
      }, true);
      document.addEventListener("click", (event) => {
        var _a2;
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)
          return;
        const container = event.target.closest(".sidebar-item-container");
        const children = container == null ? void 0 : container.querySelector(":scope > .sidebar-child-item");
        const mainLabel = getItemLabel(container);
        if (TOP_LEVEL_WORKSPACES.has(mainLabel) && !event.target.closest(".drop-icon, .sidebar-item-control")) {
          event.preventDefault();
          event.stopImmediatePropagation();
          const open = !(children == null ? void 0 : children.children.length) || children.classList.contains("hidden");
          getSelectableSidebarContainers().forEach((item) => {
            const section = item.querySelector(":scope > .sidebar-child-item");
            const expanded = open && getItemLabel(item) === mainLabel;
            if (section)
              setSidebarExpanded(item, expanded);
            rememberOpenSidebarGroup(getSidebarRoutingLabel(item) || getItemLabel(item), expanded);
          });
          if (!open)
            return;
          rememberSidebarContext(mainLabel);
          frappe.route_options = null;
          Promise.resolve(frappe.set_route(getWorkspaceUrl(mainLabel, true).replace(/^\/app\//, ""))).then(() => scheduleSidebarEnhancements());
          return;
        }
        if (children == null ? void 0 : children.children.length) {
          event.preventDefault();
          event.stopImmediatePropagation();
          const open = children.classList.contains("hidden");
          const siblings = ((_a2 = container.parentElement) == null ? void 0 : _a2.children) || [];
          Array.from(siblings).forEach((sibling) => {
            const section = sibling.querySelector(":scope > .sidebar-child-item");
            if (section)
              setSidebarExpanded(sibling, false);
            rememberOpenSidebarGroup(getSidebarRoutingLabel(sibling) || getItemLabel(sibling), false);
          });
          setSidebarExpanded(container, open);
          rememberOpenSidebarGroup(getSidebarRoutingLabel(container) || mainLabel, open);
          setDropIcon(container, open);
          return;
        }
        if (event.target.closest(".drop-icon, .sidebar-item-control"))
          return;
        const anchor = event.target.closest(".item-anchor") || (container == null ? void 0 : container.querySelector(":scope > .desk-sidebar-item > .item-anchor"));
        const label = getItemLabel(container);
        const routingLabel = getSidebarRoutingLabel(container);
        const parent = CHILD_TO_PARENT[routingLabel];
        const target = getSidebarTarget({
          name: getWorkspaceName(container),
          title: routingLabel || label
        }) || getAnchorRouteTarget(anchor) || getTargetFromUrl(anchor);
        if (target) {
          event.preventDefault();
          event.stopPropagation();
          event.stopImmediatePropagation();
          rememberSidebarContext(routingLabel || label);
          Promise.resolve(routeToTarget(target)).then(() => {
            syncSidebarState();
            scheduleRetry();
          });
          return;
        }
        if (parent) {
          event.preventDefault();
          event.stopPropagation();
          event.stopImmediatePropagation();
          rememberSidebarContext(routingLabel || label);
          frappe.route_options = null;
          frappe.set_route(getWorkspaceUrl(getWorkspaceName(container), true).replace(/^\/app\//, ""));
          return;
        }
        if (!target && !TOP_LEVEL_WORKSPACES.has(label) && !CHILD_TO_PARENT[routingLabel])
          return;
        event.preventDefault();
        frappe.route_options = null;
        rememberSidebarContext(routingLabel || label);
        frappe.set_route(getWorkspaceUrl(getWorkspaceName(container), true).replace(/^\/app\//, ""));
      }, true);
    }
    function applyDirectLinks() {
      document.querySelectorAll(".sidebar-item-container").forEach((container) => {
        var _a2;
        const label = getItemLabel(container);
        const routingLabel = getSidebarRoutingLabel(container);
        const anchor = container.querySelector(":scope > .desk-sidebar-item > .item-anchor");
        if (((_a2 = dynamicSidebarItems.get(getWorkspaceName(container))) == null ? void 0 : _a2.is_report_group) || container.dataset.retailReportGroup === "1") {
          configureReportGroupAnchor(anchor);
          return;
        }
        const target = getSidebarTarget({
          name: getWorkspaceName(container),
          title: routingLabel || label
        });
        if (target) {
          anchor == null ? void 0 : anchor.setAttribute("href", getTargetUrl(target));
          anchor == null ? void 0 : anchor.setAttribute("data-retail-direct-link", "1");
          setAnchorRouteTarget(anchor, target);
        } else if (CHILD_TO_PARENT[routingLabel]) {
          anchor == null ? void 0 : anchor.setAttribute("href", getWorkspaceUrl(getWorkspaceName(container), true));
          anchor == null ? void 0 : anchor.setAttribute("data-retail-direct-link", "1");
          anchor == null ? void 0 : anchor.removeAttribute("data-retail-route-target");
        } else if (TOP_LEVEL_WORKSPACES.has(label)) {
          anchor == null ? void 0 : anchor.setAttribute("href", getWorkspaceUrl(getWorkspaceName(container), true));
          anchor == null ? void 0 : anchor.setAttribute("data-retail-direct-link", "1");
          anchor == null ? void 0 : anchor.removeAttribute("data-retail-route-target");
        }
      });
    }
    function buildSidebarItem(item, pages) {
      var _a2;
      const title = item.title;
      const displayTitle = WORKSPACE_DISPLAY_LABELS[item.name] || title;
      const children = pages.filter((page) => page.parent_page === title && sidebarItemIsAllowed(page));
      const target = getSidebarTarget(item);
      const href = target ? getTargetUrl(target) : getWorkspaceUrl(item.name || title, item.public);
      const routeTargetAttribute = target ? ` data-retail-route-target="${escapeHtml(JSON.stringify(target))}"` : "";
      const container = document.createElement("div");
      container.className = "sidebar-item-container retail-sidebar-item";
      let parent = item.parent_page;
      let level = 0;
      const seenParents = /* @__PURE__ */ new Set();
      while (parent && !seenParents.has(parent)) {
        seenParents.add(parent);
        level += 1;
        parent = (_a2 = pages.find((page) => page.title === parent || page.name === parent)) == null ? void 0 : _a2.parent_page;
      }
      container.dataset.retailLevel = level;
      if (item.is_report_group)
        container.dataset.retailReportGroup = "1";
      if (item.is_report_link)
        container.dataset.retailReportLink = "1";
      container.setAttribute("item-name", displayTitle);
      container.setAttribute("item-workspace-name", item.name || title);
      container.setAttribute("item-parent", item.parent_page || "");
      container.setAttribute("item-public", item.public || 0);
      container.setAttribute("item-is-hidden", item.is_hidden || 0);
      container.innerHTML = `
            <div class="desk-sidebar-item standard-sidebar-item">
                <a href="${href}" class="item-anchor block-click" title="${escapeHtml(__(displayTitle))}"${routeTargetAttribute}>
                    <span class="sidebar-item-icon"></span>
                    <span class="sidebar-item-label">${escapeHtml(__(displayTitle))}</span>
                </a>
                <div class="sidebar-item-control"></div>
            </div>
            <div class="sidebar-child-item nested-container hidden"></div>
        `;
      if (item.is_report_group) {
        configureReportGroupAnchor(container.querySelector(":scope > .desk-sidebar-item > .item-anchor"));
      }
      const iconConfig = findIconConfig(displayTitle) || findIconConfig(item.name || title);
      const iconContainer = container.querySelector(":scope > .desk-sidebar-item .sidebar-item-icon");
      if (iconConfig && iconContainer) {
        iconContainer.innerHTML = "";
        iconContainer.appendChild(createIconElement(iconConfig));
      }
      if (children.length) {
        const control = container.querySelector(".sidebar-item-control");
        const childSection = container.querySelector(".sidebar-child-item");
        const button = document.createElement("button");
        button.className = "btn-reset drop-icon retail-drop-icon";
        button.type = "button";
        button.setAttribute("aria-expanded", "false");
        button.innerHTML = getSmallDropIcon(false);
        control.appendChild(button);
        children.forEach((child) => childSection.appendChild(buildSidebarItem(child, pages)));
      }
      return container;
    }
    function ensureBusinessHomeSidebarItem(items) {
      var _a2;
      if (!Array.isArray(items))
        return [];
      if (Array.isArray((_a2 = frappe.boot) == null ? void 0 : _a2.retail_sidebar_selection) && !workspaceIsAllowed("Business Home"))
        return items;
      const hasBusinessHome = items.some((item) => (item.title || item.name) === "Business Home");
      if (hasBusinessHome)
        return items;
      return [
        {
          name: "Business Home",
          title: "Business Home",
          public: 1,
          parent_page: "",
          is_hidden: 0
        },
        ...items
      ];
    }
    function ensureVanSalesSidebarChildren(items) {
      if (!Array.isArray(items))
        return [];
      const hasVanSales = items.some((item) => (item.title || item.name) === "Van Sales");
      if (!hasVanSales || !sidebarWorkspaceIsAllowed("Van Sales"))
        return items;
      const nextItems = [...items];
      function insertOrMoveRequiredChild(child) {
        const _a2 = child, { insert_after } = _a2, childItem = __objRest(_a2, ["insert_after"]);
        const existingIndex = nextItems.findIndex((item) => item.name === child.name || item.title === child.title || WORKSPACE_DISPLAY_LABELS[item.name] === child.title);
        const existingItem = existingIndex >= 0 ? nextItems[existingIndex] : {};
        const sidebarChild = __spreadProps(__spreadValues(__spreadValues({}, existingItem), childItem), {
          name: existingItem.name || childItem.name,
          title: childItem.title,
          parent_page: "Van Sales",
          public: 1,
          is_hidden: 0
        });
        if (!sidebarItemIsAllowed(sidebarChild))
          return;
        if (existingIndex >= 0)
          nextItems.splice(existingIndex, 1);
        const insertAfterLabels = insert_after || ["Van Sessions"];
        const insertAfterIndex = nextItems.findIndex((item) => {
          const displayLabel = WORKSPACE_DISPLAY_LABELS[item.name] || item.title;
          return insertAfterLabels.includes(item.name) || insertAfterLabels.includes(item.title) || insertAfterLabels.includes(displayLabel);
        });
        if (insertAfterIndex >= 0) {
          nextItems.splice(insertAfterIndex + 1, 0, sidebarChild);
        } else {
          nextItems.push(sidebarChild);
        }
      }
      REQUIRED_VAN_SALES_CHILDREN.forEach(insertOrMoveRequiredChild);
      return nextItems;
    }
    function getSidebarItems() {
      var _a2, _b2;
      if (sidebarItemsCache)
        return Promise.resolve(sidebarItemsCache);
      if (useBootSidebarItems && ((_a2 = frappe.boot) == null ? void 0 : _a2.retail_workspace_sidebar_groups) && Array.isArray((_b2 = frappe.boot) == null ? void 0 : _b2.allowed_workspaces)) {
        useBootSidebarItems = false;
        sidebarItemsCache = ensureVanSalesSidebarChildren(
          ensureBusinessHomeSidebarItem(frappe.boot.allowed_workspaces)
        );
        registerSidebarItems(sidebarItemsCache);
        return Promise.resolve(sidebarItemsCache);
      }
      useBootSidebarItems = false;
      if (!sidebarItemsPromise) {
        const generation = sidebarItemsGeneration;
        sidebarItemsPromise = frappe.xcall("retail.workspace_permissions.get_workspace_sidebar_items").then((result) => {
          const items = ensureVanSalesSidebarChildren(
            ensureBusinessHomeSidebarItem(Array.isArray(result) ? result : (result == null ? void 0 : result.pages) || [])
          );
          if (generation === sidebarItemsGeneration) {
            sidebarItemsCache = items;
            registerSidebarItems(items);
            sidebarItemsPromise = null;
          }
          return items;
        }).catch((error) => {
          if (generation === sidebarItemsGeneration)
            sidebarItemsPromise = null;
          throw error;
        });
      }
      return sidebarItemsPromise;
    }
    function renderPersistentSidebar() {
      const route = frappe.get_route();
      if (isWorkspaceRoute(frappe.get_route()) && !isItemFamilyPageRoute()) {
        removePersistentSidebar();
        syncDesktopSidebarClass();
        return;
      }
      const sideSections = getSidebarMountSections();
      if (!sideSections.length) {
        syncDesktopSidebarClass();
        if (sidebarRenderRetryCount < 8 && !sidebarRenderRetryTimer) {
          sidebarRenderRetryCount += 1;
          sidebarRenderRetryTimer = setTimeout(() => {
            sidebarRenderRetryTimer = null;
            renderPersistentSidebar();
          }, 250);
        }
        return;
      }
      clearTimeout(sidebarRenderRetryTimer);
      sidebarRenderRetryTimer = null;
      sidebarRenderRetryCount = 0;
      if (sideSections.every((section) => section.querySelector(".retail-persistent-sidebar"))) {
        sideSections.forEach((section) => mountPersistentSidebar(section, []));
        syncDesktopSidebarClass();
        return;
      }
      const generation = sidebarItemsGeneration;
      getSidebarItems().then((items) => {
        if (generation !== sidebarItemsGeneration)
          return;
        if (isWorkspaceRoute(frappe.get_route()) && !isItemFamilyPageRoute()) {
          removePersistentSidebar();
          return;
        }
        getSidebarMountSections().forEach((section) => mountPersistentSidebar(section, items));
        hideUnauthorizedSidebarItems();
        applyIcons();
        syncSidebarState();
        syncDesktopSidebarClass();
      }).catch((error) => {
        console.error("retail_navigation: failed to render persistent sidebar", error);
        syncDesktopSidebarClass();
      });
    }
    let sidebarObserver;
    function refreshSidebarEnhancements() {
      hideStandardHomeSidebarItems();
      applyDisplayLabels();
      applyDirectLinks();
      hideUnauthorizedSidebarItems();
      applyIcons();
      ensureWorkspaceDropIcons();
      syncSidebarState();
      forceVanSidebarSelection();
      renderPersistentSidebar();
      syncDesktopSidebarClass();
      applyWideTransactionLayout();
      upsertCurrentWorkTab();
      sidebarObserver == null ? void 0 : sidebarObserver.takeRecords();
    }
    function scheduleSidebarEnhancements(delay = 80) {
      clearTimeout(observerRefreshTimer);
      observerRefreshTimer = setTimeout(refreshSidebarEnhancements, delay);
    }
    function observeSidebarChanges() {
      const sidebarSelector = ".desk-sidebar, .layout-side-section, .overlay-sidebar, .workspace-sidebar";
      sidebarObserver = new MutationObserver((mutations) => {
        if (mutations.some((m) => {
          if (!(m.target instanceof Element))
            return false;
          if (m.target.closest(".retail-open-work"))
            return false;
          if (m.target.closest(sidebarSelector))
            return m.addedNodes.length || m.removedNodes.length;
          return Array.from(m.addedNodes).some((node) => node instanceof Element && (node.matches(sidebarSelector) || node.querySelector(sidebarSelector)));
        })) {
          debugLog("retail_navigation: sidebar DOM mutated, reapplying icons");
          scheduleSidebarEnhancements();
        }
      });
      sidebarObserver.observe(document.body, {
        childList: true,
        subtree: true
      });
    }
    function scheduleRetry() {
      scheduleSidebarEnhancements(250);
    }
    function scheduleMobileSidebarRender() {
      if (!isMobile())
        return;
      scheduleSidebarEnhancements(80);
    }
    function bindMobileSidebarToggle() {
      if (window.__retailMobileSidebarToggleBound)
        return;
      window.__retailMobileSidebarToggleBound = true;
      $(document.body).on("toggleSidebar.retailMobileSidebar", scheduleMobileSidebarRender);
      document.addEventListener("click", (event) => {
        if (event.target.closest(".sidebar-toggle-btn")) {
          scheduleMobileSidebarRender();
        }
      }, true);
    }
    function redirectItemFamilyListRoute() {
      const route = frappe.get_route();
      if (!Array.isArray(route) || !route.length)
        return false;
      const view = String(route[0] || "").toLowerCase();
      const title = decodeURIComponent(String(route[route[1] === "private" ? 2 : 1] || ""));
      const slug = frappe.router.slug(title || route[0] || "");
      const isOldItemFamilyRoute = view === "query-report" && title === "Item Family List" || (view === "workspaces" || view === "workspace") && title === "Item Family List" || slug === "item-family-list";
      if (!isOldItemFamilyRoute)
        return false;
      frappe.set_route("retail-item-family-l");
      return true;
    }
    function installPOSBreadcrumbs() {
      const breadcrumbs = frappe.breadcrumbs;
      if (!(breadcrumbs == null ? void 0 : breadcrumbs.set_workspace_breadcrumb) || breadcrumbs.__retail_pos_installed)
        return;
      const posDoctypes = /* @__PURE__ */ new Set([
        "POS Branch Counter",
        "POS Cashier Shift",
        "POS Counter Session",
        "POS Closing Entry",
        "POS Branch Day Closing",
        "POS Sync Log"
      ]);
      const original = breadcrumbs.set_workspace_breadcrumb;
      breadcrumbs.set_workspace_breadcrumb = function(entry) {
        if (posDoctypes.has(entry.doctype)) {
          entry = __spreadProps(__spreadValues({}, entry), { workspace: "POS" });
        }
        return original.call(this, entry);
      };
      breadcrumbs.__retail_pos_installed = true;
    }
    function init() {
      var _a2, _b2, _c2, _d;
      installPOSBreadcrumbs();
      registerSidebarItems(((_a2 = frappe.boot) == null ? void 0 : _a2.allowed_workspaces) || []);
      injectRetailInlineCss();
      bindNavbarHomeToBusinessHome();
      bindViewWebsiteToRetailHome();
      redirectStandardHomeToBusinessHome();
      redirectItemFamilyListRoute();
      enforceAllowedRoute();
      waitForWorkspaceModule();
      waitForSearchFilters();
      applyDisplayLabels();
      applyDirectLinks();
      bindViewWebsiteToRetailHome();
      applyIcons();
      ensureWorkspaceDropIcons();
      syncSidebarState();
      renderPersistentSidebar();
      applyWideTransactionLayout();
      upsertCurrentWorkTab();
      observeSidebarChanges();
      scheduleRetry();
      bindSubmenuRouting();
      bindOpenWorkEvents();
      bindMobileSidebarToggle();
      (_b2 = frappe.realtime) == null ? void 0 : _b2.on("retail_sidebar_permissions_changed", () => window.location.reload());
      if ((_d = (_c2 = window.frappe) == null ? void 0 : _c2.router) == null ? void 0 : _d.on) {
        frappe.router.on("change", () => {
          sidebarItemsGeneration += 1;
          sidebarItemsCache = null;
          sidebarItemsPromise = null;
          useBootSidebarItems = false;
          if (redirectStandardHomeToBusinessHome())
            return;
          if (enforceAllowedRoute())
            return;
          redirectItemFamilyListRoute();
          clearTimeout(routeRefreshTimer);
          routeRefreshTimer = setTimeout(refreshSidebarEnhancements, 120);
          setTimeout(applyWideTransactionLayout, 350);
          setTimeout(applyWideTransactionLayout, 900);
          setTimeout(upsertCurrentWorkTab, 350);
        });
      }
      window.matchMedia(DESKTOP_MEDIA).addEventListener("change", () => {
        refreshSidebarEnhancements();
        renderOpenWorkTabs();
      });
    }
    if ((_c = window.frappe) == null ? void 0 : _c.ready) {
      frappe.ready(init);
    } else if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", init);
    } else {
      init();
    }
  })();

  // ../retail/retail/public/js/pages/van_stock_view.js
  (function() {
    frappe.provide("retail");
    frappe.pages = frappe.pages || {};
    frappe.standard_pages = frappe.standard_pages || {};
    const van_stock_view_page = {};
    frappe.standard_pages["van-stock-view"] = function() {
      const wrapper = frappe.container.add_page("van-stock-view");
      frappe.pages["van-stock-view"] = wrapper;
      wrapper.on_page_load = van_stock_view_page.on_page_load;
      wrapper.on_page_show = van_stock_view_page.on_page_show;
      wrapper.on_page_load(wrapper);
      $(wrapper).on("show", function() {
        var _a;
        (_a = wrapper.on_page_show) == null ? void 0 : _a.call(wrapper, wrapper);
      });
    };
    van_stock_view_page.on_page_load = function(wrapper) {
      const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Van Stock View"),
        single_column: true
      });
      try {
        wrapper.van_stock_view = new retail.VanStockView(page);
      } catch (error) {
        console.error("Unable to render Van Stock View", error);
        $(page.body).html(`<div class="van-stock-empty">${__("Unable to load Van Stock View. Please refresh and try again.")}</div>`);
      }
    };
    van_stock_view_page.on_page_show = function(wrapper) {
      var _a;
      (_a = wrapper.van_stock_view) == null ? void 0 : _a.refresh(true);
    };
    retail.VanStockView = class VanStockView {
      constructor(page) {
        this.page = page;
        this.body = $('<div class="van-stock-view"></div>').appendTo(page.body);
        this.controls = {};
        this.make();
      }
      make() {
        this.filter_area = $('<div class="van-stock-filters"></div>').appendTo(this.body);
        this.make_control("company", "Link", __("Company"), "Company", frappe.defaults.get_default("company"));
        this.make_control("posting_date", "Date", __("As On Date"), null, frappe.datetime.get_today());
        this.make_control("van", "Link", __("Van"), "Van Fleet");
        this.make_control("warehouse", "Link", __("Warehouse"), "Warehouse");
        this.make_control("item_code", "Link", __("Item"), "Item");
        this.refresh_button = $('<button class="btn btn-primary btn-sm">' + __("Refresh") + "</button>").appendTo($("<div></div>").appendTo(this.filter_area)).on("click", () => this.refresh(true));
        this.summary_area = $('<div class="van-stock-summary"></div>').appendTo(this.body);
        this.table_area = $("<div></div>").appendTo(this.body);
      }
      make_control(fieldname, fieldtype, label, options, default_value) {
        const field = frappe.ui.form.make_control({
          parent: $("<div></div>").appendTo(this.filter_area),
          df: {
            fieldname,
            fieldtype,
            label,
            options,
            default: default_value,
            change: () => this.refresh()
          },
          render_input: true
        });
        field.set_value(default_value || "");
        this.controls[fieldname] = field;
      }
      get_filters() {
        const filters = {};
        Object.keys(this.controls).forEach((fieldname) => {
          const value = this.controls[fieldname].get_value();
          if (value)
            filters[fieldname] = value;
        });
        return filters;
      }
      refresh(force) {
        clearTimeout(this.refresh_timer);
        this.refresh_timer = setTimeout(() => this.fetch(), force ? 0 : 250);
      }
      fetch() {
        this.refresh_button.prop("disabled", true);
        this.table_area.html(`<div class="van-stock-empty">${__("Loading stock...")}</div>`);
        frappe.call({
          method: "retail.van_stock.get_van_stock_view",
          args: this.get_filters()
        }).then((response) => {
          const result = response.message || {};
          this.render_summary(result.summary || {});
          this.render_table(result.rows || []);
        }).always(() => {
          this.refresh_button.prop("disabled", false);
        });
      }
      render_summary(summary) {
        const cards = [
          [__("Vans"), summary.vans || 0],
          [__("Warehouses"), summary.warehouses || 0],
          [__("Items"), summary.items || 0],
          [__("Total Qty"), flt(summary.total_qty || 0, 3)]
        ];
        this.summary_area.html(cards.map(([label, value]) => `
				<div class="van-stock-summary-card">
					<div class="van-stock-summary-label">${frappe.utils.escape_html(label)}</div>
					<div class="van-stock-summary-value">${frappe.utils.escape_html(String(value))}</div>
				</div>
			`).join(""));
      }
      render_table(rows) {
        if (!rows.length) {
          this.table_area.html(`<div class="van-stock-empty">${__("No stock found for the selected filters.")}</div>`);
          return;
        }
        const html = `
				<div class="van-stock-table-wrap">
					<table class="van-stock-table">
						<thead>
							<tr>
								<th>${__("No.")}</th>
								<th>${__("Van")}</th>
								<th>${__("Warehouse")}</th>
								<th>${__("Item Code")}</th>
								<th>${__("Item Name")}</th>
								<th>${__("UOM")}</th>
								<th class="numeric">${__("Qty")}</th>
								<th class="numeric">${__("Valuation Rate")}</th>
								<th>${__("Last Movement")}</th>
							</tr>
						</thead>
						<tbody>
							${rows.map((row, index) => this.render_row(row, index + 1)).join("")}
						</tbody>
					</table>
				</div>
			`;
        this.table_area.html(html);
      }
      render_row(row, index) {
        const link = (doctype, name, label) => {
          if (!name)
            return "";
          const text = frappe.utils.escape_html(label || name);
          const href = frappe.router.make_url(["Form", doctype, name]);
          return `<a href="${href}">${text}</a>`;
        };
        return `
				<tr>
					<td>${index}</td>
					<td>${link("Van Fleet", row.van, row.vehicle_name || row.van)}</td>
					<td>${link("Warehouse", row.warehouse)}</td>
					<td>${link("Item", row.item_code)}</td>
					<td>${frappe.utils.escape_html(row.item_name || "")}</td>
					<td>${frappe.utils.escape_html(row.stock_uom || "")}</td>
					<td class="numeric">${frappe.format(row.qty || 0, { fieldtype: "Float" })}</td>
					<td class="numeric">${frappe.format(row.valuation_rate || 0, { fieldtype: "Currency" })}</td>
					<td>${frappe.utils.escape_html(row.last_movement || "")}</td>
				</tr>
			`;
      }
    };
  })();

  // ../retail/retail/public/js/van_document_wrapper.js
  frappe.provide("retail");
  retail.van_sales_report_filters = function() {
    return [
      {
        fieldname: "company",
        label: __("Company"),
        fieldtype: "Link",
        options: "Company",
        default: frappe.defaults.get_user_default("Company")
      },
      {
        fieldname: "from_date",
        label: __("From Date"),
        fieldtype: "Date",
        default: frappe.datetime.get_today(),
        reqd: 1
      },
      {
        fieldname: "to_date",
        label: __("To Date"),
        fieldtype: "Date",
        default: frappe.datetime.get_today(),
        reqd: 1
      },
      {
        fieldname: "van_session",
        label: __("Van Session"),
        fieldtype: "Link",
        options: "Van Session"
      },
      {
        fieldname: "van",
        label: __("Van"),
        fieldtype: "Link",
        options: "Van Fleet"
      },
      {
        fieldname: "driver",
        label: __("Driver"),
        fieldtype: "Link",
        options: "Driver"
      }
    ];
  };
  retail.VanDocumentWrapper = class VanDocumentWrapper {
    constructor(options) {
      var _a;
      this.options = options;
      this.page = options.page;
      this.options.set_van_breadcrumbs = () => this.set_van_breadcrumbs();
      this.make_list_view();
      setTimeout(() => this.set_van_breadcrumbs(), 100);
      setTimeout(() => this.set_van_breadcrumbs(), 500);
      (_a = frappe.after_ajax) == null ? void 0 : _a.call(frappe, () => this.set_van_breadcrumbs());
    }
    set_van_breadcrumbs() {
      frappe.breadcrumbs.add({
        type: "Custom",
        route: "/app/van-sales",
        label: __("Van Sales")
      });
    }
    make_list_view() {
      var _a;
      const wrapper_options = this.options;
      class VanListView extends frappe.views.ListView {
        setup_defaults() {
          return Promise.resolve(super.setup_defaults()).then(() => {
            this.page_title = wrapper_options.title || this.page_title;
            this.filters = this.with_wrapper_filters(this.filters || []);
            this.sort_by = wrapper_options.sort_by || this.sort_by;
            this.sort_order = wrapper_options.sort_order || this.sort_order;
          });
        }
        async set_fields() {
          await super.set_fields();
          (wrapper_options.fields || []).filter((fieldname) => frappe.meta.has_field(this.doctype, fieldname) || frappe.model.std_fields_list.includes(fieldname)).forEach((fieldname) => this._add_field(fieldname));
          this.build_fields();
        }
        setup_columns() {
          var _a2;
          super.setup_columns();
          if (!Array.isArray(wrapper_options.columns) || !wrapper_options.columns.length)
            return;
          const existing = new Set((this.columns || []).map((column) => {
            var _a3;
            return ((_a3 = column.df) == null ? void 0 : _a3.fieldname) || column.fieldname;
          }));
          const metaFields = new Map((((_a2 = this.meta) == null ? void 0 : _a2.fields) || []).map((df) => [df.fieldname, df]));
          wrapper_options.columns.forEach((column) => {
            if (!column.fieldname || existing.has(column.fieldname))
              return;
            const metaField = metaFields.get(column.fieldname) || {};
            if (!metaField.fieldname && !frappe.model.std_fields_list.includes(column.fieldname))
              return;
            const df = {
              fieldname: column.fieldname,
              label: column.label || metaField.label || column.fieldname,
              fieldtype: column.type || metaField.fieldtype || "Data",
              options: column.options || metaField.options
            };
            this.columns.push({
              type: "Field",
              df
            });
          });
        }
        with_wrapper_filters(filters) {
          const van_filter = [
            this.doctype,
            wrapper_options.flag_field,
            "=",
            wrapper_options.flag_value === void 0 ? 1 : wrapper_options.flag_value
          ];
          const blocked_fields = /* @__PURE__ */ new Set([wrapper_options.flag_field, ...wrapper_options.clear_fields || []]);
          return [
            van_filter,
            ...filters.filter((filter) => Array.isArray(filter) && !blocked_fields.has(filter[1]))
          ];
        }
        set_title() {
          var _a2;
          this.page.set_title(wrapper_options.title || this.page_title, null, true, "", (_a2 = this.meta) == null ? void 0 : _a2.description);
        }
        set_breadcrumbs() {
          var _a2;
          (_a2 = wrapper_options.set_van_breadcrumbs) == null ? void 0 : _a2.call(wrapper_options);
        }
        set_primary_action() {
          if (!this.can_create || frappe.boot.read_only) {
            this.page.clear_primary_action();
            return;
          }
          this.page.set_primary_action(
            `${__("Add")} ${wrapper_options.title || __(this.doctype)}`,
            () => this.make_new_doc(),
            "add"
          );
        }
        make_new_doc() {
          frappe.route_options = __spreadValues({}, wrapper_options.new_doc_values || {});
          frappe.new_doc(this.doctype);
        }
      }
      this.list_view = new VanListView({
        doctype: this.options.doctype,
        parent: this.page.parent,
        page_title: this.options.title
      });
      (_a = this.list_view.init_promise) == null ? void 0 : _a.catch((error) => {
        console.error(`Unable to render ${this.options.title || this.options.doctype}`, error);
        $(this.page.main || this.page.body).html(
          `<div class="text-muted p-4">${__("Unable to load this Van Sales page. Please refresh and try again.")}</div>`
        );
      });
    }
    refresh() {
      var _a;
      this.set_van_breadcrumbs();
      (_a = this.list_view) == null ? void 0 : _a.refresh();
    }
  };
  (function() {
    frappe.pages = frappe.pages || {};
    frappe.standard_pages = frappe.standard_pages || {};
    const page_specs = {
      "van-stock-request": {
        title: __("Stock Request"),
        doctype: "Material Request",
        flag_field: "custom_is_van_stock_request",
        list_title: __("Stock Request"),
        new_doc_values: {
          custom_is_van_stock_request: 1,
          material_request_type: "Material Transfer",
          custom_van_request_type: "Loading"
        },
        columns: [
          { fieldname: "name", label: __("Request"), link: true },
          { fieldname: "transaction_date", label: __("Date"), type: "Date" },
          { fieldname: "custom_van_request_type", label: __("Type") },
          { fieldname: "custom_van_session", label: __("Session") },
          { fieldname: "custom_van", label: __("Van") },
          { fieldname: "custom_van_warehouse", label: __("Warehouse") },
          { fieldname: "custom_driver_name", label: __("Driver") },
          { fieldname: "status", label: __("Status") }
        ],
        fields: [
          "name",
          "transaction_date",
          "custom_van_request_type",
          "custom_van_session",
          "custom_van",
          "custom_van_warehouse",
          "custom_driver_name",
          "status"
        ]
      },
      "van-stock-entries": {
        title: __("Van Stock Entries"),
        doctype: "Stock Entry",
        flag_field: "custom_is_van_stock_entry",
        list_title: __("Van Stock Entry"),
        new_doc_values: {
          custom_is_van_stock_entry: 1
        },
        columns: [
          { fieldname: "name", label: __("Stock Entry"), link: true },
          { fieldname: "posting_date", label: __("Date"), type: "Date" },
          { fieldname: "stock_entry_type", label: __("Stock Entry Type") },
          { fieldname: "custom_van_stock_entry_type", label: __("Van Type") },
          { fieldname: "custom_van_session", label: __("Session") },
          { fieldname: "docstatus", label: __("Status"), type: "DocStatus" }
        ],
        fields: ["name", "posting_date", "stock_entry_type", "custom_van_stock_entry_type", "custom_van_session", "docstatus"]
      },
      "retail-van-sales-invoice": {
        title: __("Van Sales Invoice"),
        doctype: "Sales Invoice",
        flag_field: "custom_is_van_sale",
        clear_fields: ["is_return"],
        list_title: __("Van Sales Invoice"),
        new_doc_values: {
          custom_is_van_sale: 1,
          update_stock: 1
        },
        columns: [
          { fieldname: "name", label: __("Invoice"), link: true },
          { fieldname: "posting_date", label: __("Date"), type: "Date" },
          { fieldname: "customer_name", label: __("Customer") },
          { fieldname: "custom_van_session", label: __("Session") },
          { fieldname: "grand_total", label: __("Grand Total"), type: "Currency" },
          { fieldname: "outstanding_amount", label: __("Outstanding"), type: "Currency" },
          { fieldname: "status", label: __("Status") }
        ],
        fields: ["name", "posting_date", "customer_name", "custom_van_session", "grand_total", "outstanding_amount", "status"]
      },
      "van-payments": {
        title: __("Van Payments"),
        doctype: "Payment Entry",
        flag_field: "custom_is_van_payment",
        list_title: __("Van Payment"),
        new_doc_values: {
          custom_is_van_payment: 1,
          payment_type: "Receive"
        },
        columns: [
          { fieldname: "name", label: __("Payment"), link: true },
          { fieldname: "posting_date", label: __("Date"), type: "Date" },
          { fieldname: "payment_type", label: __("Type") },
          { fieldname: "party", label: __("Party") },
          { fieldname: "mode_of_payment", label: __("Mode") },
          { fieldname: "paid_amount", label: __("Paid Amount"), type: "Currency" },
          { fieldname: "custom_van_session", label: __("Session") }
        ],
        fields: ["name", "posting_date", "payment_type", "party", "mode_of_payment", "paid_amount", "custom_van_session"]
      }
    };
    Object.keys(page_specs).forEach((route) => {
      const spec = page_specs[route];
      frappe.standard_pages[route] = function() {
        const wrapper = frappe.container.add_page(route);
        frappe.pages[route] = wrapper;
        wrapper.on_page_load = function(page_wrapper) {
          const page = frappe.ui.make_app_page({
            parent: page_wrapper,
            title: spec.title,
            single_column: false
          });
          try {
            page_wrapper.van_sales_wrapper = new retail.VanDocumentWrapper({
              page,
              doctype: spec.doctype,
              flag_field: spec.flag_field,
              flag_value: spec.flag_value,
              clear_fields: spec.clear_fields,
              title: spec.list_title,
              new_doc_values: spec.new_doc_values,
              columns: spec.columns,
              fields: spec.fields,
              sort_by: spec.sort_by,
              sort_order: spec.sort_order
            });
          } catch (error) {
            console.error(`Unable to render ${route}`, error);
            $(page.body).html(`<div class="text-muted p-4">${__("Unable to load this Van Sales page. Please refresh and try again.")}</div>`);
          }
        };
        wrapper.on_page_show = function(page_wrapper) {
          var _a;
          (_a = page_wrapper.van_sales_wrapper) == null ? void 0 : _a.refresh();
        };
        wrapper.on_page_load(wrapper);
        $(wrapper).on("show", function() {
          var _a;
          (_a = wrapper.on_page_show) == null ? void 0 : _a.call(wrapper, wrapper);
        });
      };
    });
  })();

  // ../retail/retail/public/js/local_draft_recovery.js
  (function() {
    if (window.__retail_local_draft_recovery_booted)
      return;
    window.__retail_local_draft_recovery_booted = true;
    const DB_NAME = "retail_local_draft_recovery";
    const DB_VERSION = 1;
    const STORE_NAME = "drafts";
    const SESSION_ID_KEY = "retail_local_draft_recovery_session_id";
    const EMERGENCY_DRAFT_PREFIX = "retail_local_draft_recovery_emergency::";
    const CRITICAL_EXPIRY_MS = 48 * 60 * 60 * 1e3;
    const SMALL_FORM_EXPIRY_MS = 12 * 60 * 60 * 1e3;
    const CRITICAL_SAVE_DELAY_MS = 3e4;
    const SMALL_FORM_SAVE_DELAY_MS = 5e3;
    const MAX_DRAFT_BYTES = 8 * 1024 * 1024;
    const MAX_SMALL_FORM_ROWS = 250;
    const MAX_FULL_DOC_ROWS = 500;
    const LOCAL_DRAFT_PROMPT_IGNORE_FIELDS = /* @__PURE__ */ new Set([
      "doctype",
      "name",
      "owner",
      "creation",
      "modified",
      "modified_by",
      "docstatus",
      "idx",
      "__islocal",
      "naming_series",
      "company",
      "currency",
      "conversion_rate",
      "price_list_currency",
      "plc_conversion_rate",
      "posting_date",
      "posting_time",
      "set_posting_time",
      "transaction_date",
      "schedule_date",
      "delivery_date",
      "due_date",
      "payment_due_date",
      "status"
    ]);
    const CRITICAL_DOCTYPES = [
      "Sales Invoice",
      "Purchase Invoice",
      "Purchase Receipt",
      "Delivery Note",
      "Stock Entry",
      "Stock Reconciliation",
      "Sales Order",
      "Purchase Order"
    ];
    const SMALL_FORM_DOCTYPES = [
      "Item",
      "Customer",
      "Supplier",
      "Item Price",
      "Item Group",
      "Brand",
      "UOM",
      "Warehouse",
      "Price List",
      "Address",
      "Contact",
      "Customer Group",
      "Supplier Group",
      "Territory",
      "Sales Person",
      "Sales Partner",
      "Mode of Payment",
      "Payment Terms Template",
      "Terms and Conditions",
      "Tax Category",
      "Item Tax Template",
      "Sales Taxes and Charges Template",
      "Purchase Taxes and Charges Template"
    ];
    const TRACKED_DOCTYPES = Array.from(/* @__PURE__ */ new Set([...CRITICAL_DOCTYPES, ...SMALL_FORM_DOCTYPES]));
    let navigation_guard_installed = false;
    let navigation_bypass = false;
    let navigation_dialog_open = false;
    let dirty_form_state = null;
    function boot() {
      var _a, _b;
      if (!((_b = (_a = window.frappe) == null ? void 0 : _a.ui) == null ? void 0 : _b.form)) {
        setTimeout(boot, 150);
        return;
      }
      registerHandlers();
      setupNavigationGuard();
      cleanupOldDrafts();
      exposeDebugTools();
    }
    function registerHandlers() {
      TRACKED_DOCTYPES.forEach((doctype) => {
        frappe.ui.form.on(doctype, {
          refresh(frm) {
            if (!shouldTrack(frm))
              return;
            cleanupOldDrafts();
            offerRecovery(frm);
            updateCleanBaseline(frm);
            bindFormDirtyTracker(frm);
            if (isCriticalDoctype(frm.doctype) && canUseFullDocDraft(frm)) {
              setupAutoSaveLoop(frm);
            }
            scheduleCleanDirtyStateChecks(frm);
            scheduleDraftSave(frm);
          },
          after_save(frm) {
            deleteDraft(frm);
            updateCleanBaseline(frm);
            clearDirtyFormState(frm);
            scheduleCleanDirtyStateChecks(frm);
          },
          on_submit(frm) {
            deleteDraft(frm);
            updateCleanBaseline(frm);
            clearDirtyFormState(frm);
          },
          before_discard(frm) {
            deleteDraft(frm);
            updateCleanBaseline(frm);
            clearDirtyFormState(frm);
          }
        });
      });
      $(document).on("form-dirty", () => {
        const frm = window.cur_frm;
        if (shouldTrack(frm)) {
          handleTrackedFormDirty(frm);
        }
      });
      document.addEventListener("visibilitychange", () => {
        var _a;
        if (document.visibilityState !== "hidden")
          return;
        const frm = window.cur_frm;
        if (shouldTrack(frm) && ((_a = frm.is_dirty) == null ? void 0 : _a.call(frm)) && canUseFullDocDraft(frm)) {
          saveEmergencyDraft(frm);
          saveDraft(frm);
        }
      });
      window.addEventListener("pagehide", () => {
        var _a;
        const frm = window.cur_frm;
        if (shouldTrack(frm) && ((_a = frm.is_dirty) == null ? void 0 : _a.call(frm)) && canUseFullDocDraft(frm)) {
          saveEmergencyDraft(frm);
        }
      });
    }
    function setupNavigationGuard() {
      var _a, _b;
      if (navigation_guard_installed || !((_a = frappe.router) == null ? void 0 : _a.set_route) || !((_b = frappe.router) == null ? void 0 : _b.route))
        return;
      navigation_guard_installed = true;
      const original_set_route = frappe.router.set_route.bind(frappe.router);
      const original_route = frappe.router.route.bind(frappe.router);
      const original_history_back = window.history.back.bind(window.history);
      const original_history_go = window.history.go.bind(window.history);
      frappe.router.set_route = function() {
        if (navigation_bypass)
          return original_set_route.apply(frappe.router, arguments);
        const frm = getDirtyNavigationForm();
        if (!hasUnsavedNavigationChanges(frm)) {
          return original_set_route.apply(frappe.router, arguments);
        }
        const args = Array.from(arguments);
        showUnsavedNavigationDialog(frm, () => {
          navigation_bypass = true;
          original_set_route.apply(frappe.router, args).finally(() => {
            navigation_bypass = false;
          });
        });
        return Promise.resolve(false);
      };
      frappe.router.route = async function() {
        if (navigation_bypass)
          return original_route();
        const frm = getDirtyNavigationForm();
        const next_sub_path = frappe.router.get_sub_path();
        const current_sub_path = frappe.router.current_sub_path;
        if (!current_sub_path || next_sub_path === current_sub_path || !hasUnsavedNavigationChanges(frm)) {
          return original_route();
        }
        showUnsavedNavigationDialog(
          frm,
          () => {
            navigation_bypass = true;
            original_route().finally(() => {
              navigation_bypass = false;
            });
          },
          () => restoreFormRoute(frm)
        );
        return false;
      };
      window.addEventListener(
        "beforeunload",
        (event) => {
          const frm = getDirtyNavigationForm();
          if (!hasUnsavedNavigationChanges(frm))
            return;
          saveEmergencyDraft(frm);
          if (canUseFullDocDraft(frm))
            saveDraft(frm);
          event.preventDefault();
          event.returnValue = "";
          return "";
        },
        { capture: true }
      );
      window.history.back = function() {
        if (navigation_bypass)
          return original_history_back();
        const frm = getDirtyNavigationForm();
        if (!hasUnsavedNavigationChanges(frm))
          return original_history_back();
        showUnsavedNavigationDialog(
          frm,
          () => {
            navigation_bypass = true;
            original_history_back();
            setTimeout(() => {
              navigation_bypass = false;
            }, 500);
          },
          () => restoreFormRoute(frm)
        );
      };
      window.history.go = function(delta) {
        if (navigation_bypass || delta >= 0)
          return original_history_go(delta);
        const frm = getDirtyNavigationForm();
        if (!hasUnsavedNavigationChanges(frm))
          return original_history_go(delta);
        showUnsavedNavigationDialog(
          frm,
          () => {
            navigation_bypass = true;
            original_history_go(delta);
            setTimeout(() => {
              navigation_bypass = false;
            }, 500);
          },
          () => restoreFormRoute(frm)
        );
      };
    }
    function hasUnsavedNavigationChanges(frm) {
      var _a;
      return !!(shouldTrack(frm) && ((_a = frm.is_dirty) == null ? void 0 : _a.call(frm)) && !frm.__retail_local_draft_discarded);
    }
    function getDirtyNavigationForm() {
      var _a;
      const current_sub_path = (_a = frappe.router) == null ? void 0 : _a.current_sub_path;
      const frm = window.cur_frm;
      if (hasUnsavedNavigationChanges(frm) && isCurrentFormRoute(frm, current_sub_path)) {
        return frm;
      }
      if ((dirty_form_state == null ? void 0 : dirty_form_state.frm) && dirty_form_state.sub_path === current_sub_path && hasUnsavedNavigationChanges(dirty_form_state.frm)) {
        return dirty_form_state.frm;
      }
      return null;
    }
    function isCurrentFormRoute(frm, current_sub_path = ((_a) => (_a = frappe.router) == null ? void 0 : _a.current_sub_path)()) {
      const form_sub_path = getFormSubPath(frm);
      return !!form_sub_path && current_sub_path === form_sub_path;
    }
    function getFormSubPath(frm) {
      var _a, _b;
      const docname = ((_a = frm == null ? void 0 : frm.doc) == null ? void 0 : _a.name) || (frm == null ? void 0 : frm.docname);
      if (!(frm == null ? void 0 : frm.doctype) || !docname || !((_b = frappe.router) == null ? void 0 : _b.make_url))
        return null;
      return frappe.router.get_sub_path(frappe.router.make_url(["Form", frm.doctype, docname]));
    }
    function bindFormDirtyTracker(frm) {
      if (!(frm == null ? void 0 : frm.$wrapper) || frm.__retail_local_draft_dirty_tracker_bound)
        return;
      frm.__retail_local_draft_dirty_tracker_bound = true;
      frm.$wrapper.on("dirty.retailLocalDraftRecovery", () => handleTrackedFormDirty(frm));
    }
    function handleTrackedFormDirty(frm) {
      if (!shouldTrack(frm))
        return;
      dirty_form_state = {
        frm,
        sub_path: getFormSubPath(frm),
        updated_at: Date.now()
      };
      saveEmergencyDraft(frm);
      scheduleDraftSave(frm);
    }
    function clearDirtyFormState(frm) {
      if ((dirty_form_state == null ? void 0 : dirty_form_state.frm) === frm) {
        dirty_form_state = null;
      }
    }
    function showUnsavedNavigationDialog(frm, onDiscard, onContinue) {
      if (navigation_dialog_open)
        return;
      navigation_dialog_open = true;
      let dialog_action_taken = false;
      const dialog = new frappe.ui.Dialog({
        title: __("Unsaved Changes"),
        fields: [
          {
            fieldtype: "HTML",
            fieldname: "message",
            options: `<div class="frappe-confirm-message">${__(
              "This form has unsaved changes. Discard them and leave this form?"
            )}</div>`
          }
        ],
        primary_action_label: __("Discard Changes"),
        primary_action: async () => {
          dialog_action_taken = true;
          await discardUnsavedForNavigation(frm);
          dialog.hide();
          onDiscard == null ? void 0 : onDiscard();
        },
        secondary_action_label: __("Continue Editing"),
        secondary_action: () => {
          dialog_action_taken = true;
          dialog.hide();
          onContinue == null ? void 0 : onContinue();
        }
      });
      dialog.$wrapper.find(".btn-primary").removeClass("btn-primary").addClass("btn-danger");
      dialog.onhide = () => {
        navigation_dialog_open = false;
        if (!dialog_action_taken) {
          onContinue == null ? void 0 : onContinue();
        }
      };
      dialog.show();
    }
    async function discardUnsavedForNavigation(frm) {
      clearTimeout(frm == null ? void 0 : frm.__retail_local_draft_timer);
      frm.__retail_local_draft_discarded = true;
      await deleteDraft(frm);
      clearDirtyFormState(frm);
      if (frm == null ? void 0 : frm.doc)
        frm.doc.__unsaved = 0;
      if (frm == null ? void 0 : frm.beforeUnloadListener) {
        removeEventListener("beforeunload", frm.beforeUnloadListener, { capture: true });
      }
    }
    function restoreFormRoute(frm) {
      const form_sub_path = getFormSubPath(frm);
      if (!form_sub_path)
        return;
      navigation_bypass = true;
      frappe.router.set_route(form_sub_path).finally(() => {
        navigation_bypass = false;
      });
    }
    function shouldTrack(frm) {
      return !!((frm == null ? void 0 : frm.doctype) && TRACKED_DOCTYPES.includes(frm.doctype) && frm.doc && !frm.doc.__unsaved_recovered_prompt);
    }
    function getExpiryMs(doctype) {
      return CRITICAL_DOCTYPES.includes(doctype) ? CRITICAL_EXPIRY_MS : SMALL_FORM_EXPIRY_MS;
    }
    function getSaveDelayMs(doctype) {
      return isCriticalDoctype(doctype) ? CRITICAL_SAVE_DELAY_MS : SMALL_FORM_SAVE_DELAY_MS;
    }
    function isCriticalDoctype(doctype) {
      return CRITICAL_DOCTYPES.includes(doctype);
    }
    function scheduleDraftSave(frm) {
      var _a;
      if (frm == null ? void 0 : frm.__retail_local_draft_discarded)
        return;
      if (!((_a = frm == null ? void 0 : frm.is_dirty) == null ? void 0 : _a.call(frm)))
        return;
      if (!hasChangedFromCleanBaseline(frm))
        return;
      clearTimeout(frm.__retail_local_draft_timer);
      frm.__retail_local_draft_timer = setTimeout(() => requestIdleSave(frm), getSaveDelayMs(frm.doctype));
    }
    function setupAutoSaveLoop(frm) {
      clearInterval(frm.__retail_local_draft_interval);
      frm.__retail_local_draft_interval = setInterval(() => {
        var _a;
        if (window.cur_frm !== frm) {
          clearInterval(frm.__retail_local_draft_interval);
          return;
        }
        if (shouldTrack(frm) && ((_a = frm.is_dirty) == null ? void 0 : _a.call(frm)) && hasChangedFromCleanBaseline(frm) && canUseFullDocDraft(frm)) {
          requestIdleSave(frm);
        }
      }, CRITICAL_SAVE_DELAY_MS);
    }
    function requestIdleSave(frm) {
      if (frm.__retail_local_draft_saving)
        return;
      const run = () => saveDraft(frm);
      if (window.requestIdleCallback) {
        requestIdleCallback(run, { timeout: 1e4 });
      } else {
        setTimeout(run, 500);
      }
    }
    async function offerRecovery(frm) {
      var _a;
      const key = getDraftKey(frm);
      if (!key || frm.__retail_recovery_checked)
        return;
      frm.__retail_recovery_checked = true;
      const indexed_draft = await getDraft(key);
      const emergency_draft = getEmergencyDraft(key);
      const draft = indexed_draft || emergency_draft;
      if (!draft || !draft.doc || draft.saved_docname !== getDocName(frm))
        return;
      if (draft.user && draft.user !== frappe.session.user) {
        await deleteDraftByKey(key);
        return;
      }
      if (isExpiredDraft(draft)) {
        await deleteDraftByKey(key);
        return;
      }
      if (isDraftOlderThanCurrentDoc(frm, draft)) {
        await deleteDraftByKey(key);
        return;
      }
      if (((_a = frm.is_dirty) == null ? void 0 : _a.call(frm)) && !isLocalDoc(frm))
        return;
      if (isLocalDoc(frm) && !hasRecoverableLocalDraftContent(frm, draft.doc)) {
        await deleteDraftByKey(key);
        return;
      }
      if (!hasRecoverableDraftDifference(frm, draft.doc)) {
        await deleteDraftByKey(key);
        deleteEmergencyDraftByKey(key);
        return;
      }
      if (draft.prompted_at)
        return;
      await markDraftPrompted(key, draft, {
        has_indexed_draft: !!indexed_draft,
        has_emergency_draft: !!emergency_draft
      });
      frm.__retail_local_draft_prompted = true;
      frappe.confirm(
        __("Recover unsaved local draft from {0}?", [frappe.datetime.str_to_user(draft.updated_at_iso)]),
        () => restoreDraft(frm, draft),
        () => discardDraft(frm, key)
      );
    }
    async function saveDraft(frm) {
      var _a;
      if (frm == null ? void 0 : frm.__retail_local_draft_discarded)
        return;
      if (!(frm == null ? void 0 : frm.doc) || !((_a = frm.is_dirty) == null ? void 0 : _a.call(frm)))
        return;
      if (!hasChangedFromCleanBaseline(frm))
        return;
      if (!canUseFullDocDraft(frm)) {
        scheduleDraftSave(frm);
        return;
      }
      const key = getDraftKey(frm);
      if (!key)
        return;
      frm.__retail_local_draft_saving = true;
      let serialized;
      try {
        serialized = serializeDoc(frm);
      } finally {
        frm.__retail_local_draft_saving = false;
      }
      if (!serialized)
        return;
      if (isLocalDoc(frm) && !hasRecoverableLocalDraftContent(frm, serialized.doc)) {
        await deleteDraftByKey(key);
        return;
      }
      const now = Date.now();
      const expiry_ms = getExpiryMs(frm.doctype);
      const prompted_at = frm.__retail_local_draft_prompted ? now : null;
      await putDraft({
        key,
        user: frappe.session.user,
        doctype: frm.doctype,
        docname: getDocName(frm),
        saved_docname: getDocName(frm),
        updated_at: now,
        expires_at: now + expiry_ms,
        expiry_hours: Math.round(expiry_ms / (60 * 60 * 1e3)),
        updated_at_iso: new Date(now).toISOString(),
        browser_session_id: getBrowserSessionId(),
        doc: serialized.doc,
        bytes: serialized.bytes,
        prompted_at,
        prompted_at_iso: prompted_at ? new Date(prompted_at).toISOString() : null
      });
      deleteEmergencyDraftByKey(key);
    }
    function saveEmergencyDraft(frm) {
      var _a;
      if (frm == null ? void 0 : frm.__retail_local_draft_discarded)
        return;
      if (!(frm == null ? void 0 : frm.doc) || !((_a = frm.is_dirty) == null ? void 0 : _a.call(frm)) || !hasChangedFromCleanBaseline(frm))
        return;
      const key = getDraftKey(frm);
      if (!key)
        return;
      const serialized = serializeDoc(frm);
      if (!serialized)
        return;
      if (isLocalDoc(frm) && !hasRecoverableLocalDraftContent(frm, serialized.doc)) {
        deleteEmergencyDraftByKey(key);
        return;
      }
      const now = Date.now();
      const expiry_ms = getExpiryMs(frm.doctype);
      const prompted_at = frm.__retail_local_draft_prompted ? now : null;
      try {
        localStorage.setItem(
          getEmergencyDraftKey(key),
          JSON.stringify({
            key,
            user: frappe.session.user,
            doctype: frm.doctype,
            docname: getDocName(frm),
            saved_docname: getDocName(frm),
            updated_at: now,
            expires_at: now + expiry_ms,
            expiry_hours: Math.round(expiry_ms / (60 * 60 * 1e3)),
            updated_at_iso: new Date(now).toISOString(),
            browser_session_id: getBrowserSessionId(),
            doc: serialized.doc,
            bytes: serialized.bytes,
            emergency: true,
            prompted_at,
            prompted_at_iso: prompted_at ? new Date(prompted_at).toISOString() : null
          })
        );
      } catch (error) {
        console.warn("retail_local_draft_recovery: emergency draft save failed", error);
      }
    }
    function getEmergencyDraft(key) {
      try {
        const value = localStorage.getItem(getEmergencyDraftKey(key));
        return value ? JSON.parse(value) : null;
      } catch (e) {
        return null;
      }
    }
    async function markDraftPrompted(key, draft, options = {}) {
      const now = Date.now();
      const prompted_draft = __spreadProps(__spreadValues({}, draft), {
        prompted_at: now,
        prompted_at_iso: new Date(now).toISOString()
      });
      if (options.has_indexed_draft) {
        await putDraft(prompted_draft);
      }
      if (options.has_emergency_draft) {
        try {
          localStorage.setItem(getEmergencyDraftKey(key), JSON.stringify(prompted_draft));
        } catch (e) {
        }
      }
    }
    function isExpiredDraft(draft) {
      const now = Date.now();
      if (draft.expires_at)
        return now > draft.expires_at;
      return now - draft.updated_at > getExpiryMs(draft.doctype);
    }
    function isDraftOlderThanCurrentDoc(frm, draft) {
      var _a;
      if (isLocalDoc(frm) || !((_a = frm.doc) == null ? void 0 : _a.modified) || !draft.updated_at)
        return false;
      const modified = frappe.datetime.str_to_obj(frm.doc.modified);
      if (!modified)
        return false;
      return draft.updated_at <= modified.getTime();
    }
    function hasRecoverableLocalDraftContent(frm, draftDoc) {
      var _a;
      const metaFields = ((_a = frm.meta) == null ? void 0 : _a.fields) || [];
      const tableFields = new Set(metaFields.filter((df) => df.fieldtype === "Table").map((df) => df.fieldname));
      const fieldnames = new Set(metaFields.map((df) => df.fieldname));
      for (const [fieldname, value] of Object.entries(draftDoc || {})) {
        if (tableFields.has(fieldname)) {
          if (hasRecoverableTableRows(value))
            return true;
          continue;
        }
        if (!fieldnames.has(fieldname) || LOCAL_DRAFT_PROMPT_IGNORE_FIELDS.has(fieldname))
          continue;
        if (hasMeaningfulValue(value))
          return true;
      }
      return false;
    }
    function hasRecoverableTableRows(rows) {
      if (!Array.isArray(rows))
        return false;
      return rows.some((row) => {
        return Object.entries(row || {}).some(([fieldname, value]) => {
          if (LOCAL_DRAFT_PROMPT_IGNORE_FIELDS.has(fieldname) || ["parent", "parenttype", "parentfield"].includes(fieldname)) {
            return false;
          }
          return hasMeaningfulValue(value);
        });
      });
    }
    function hasMeaningfulValue(value) {
      if (value == null || value === "" || value === 0 || value === false)
        return false;
      if (Array.isArray(value))
        return value.length > 0;
      if (typeof value === "object")
        return Object.keys(value).length > 0;
      return true;
    }
    function restoreDraft(frm, draft) {
      frm.__retail_local_draft_discarded = false;
      frm.__retail_local_draft_prompted = true;
      frm.doc.__unsaved_recovered_prompt = true;
      restoreFormDraft(frm, draft.doc);
      frm.refresh();
      frm.dirty();
      frappe.show_alert({ message: __("Local draft recovered"), indicator: "green" });
      setTimeout(() => {
        delete frm.doc.__unsaved_recovered_prompt;
        scheduleDraftSave(frm);
      }, 1e3);
    }
    async function discardDraft(frm, key) {
      clearTimeout(frm == null ? void 0 : frm.__retail_local_draft_timer);
      frm.__retail_local_draft_discarded = true;
      await deleteDraftByKey(key);
      deleteEmergencyDraftByKey(key);
      frappe.show_alert({ message: __("Local draft discarded"), indicator: "orange" });
    }
    function restoreFormDraft(frm, draftDoc) {
      var _a;
      const metaFields = ((_a = frm.meta) == null ? void 0 : _a.fields) || [];
      const tableFields = new Set(metaFields.filter((df) => df.fieldtype === "Table").map((df) => df.fieldname));
      const fieldnames = new Set(metaFields.map((df) => df.fieldname));
      const skippedFields = /* @__PURE__ */ new Set(["doctype", "name", "owner", "creation", "modified", "modified_by", "docstatus", "idx"]);
      let restoredFields = 0;
      let restoredRows = 0;
      for (const [fieldname, value] of Object.entries(draftDoc || {})) {
        if (skippedFields.has(fieldname) || tableFields.has(fieldname) || !fieldnames.has(fieldname))
          continue;
        frm.doc[fieldname] = cloneValue(value);
        restoredFields += 1;
      }
      tableFields.forEach((fieldname) => {
        if (!Array.isArray(draftDoc == null ? void 0 : draftDoc[fieldname]))
          return;
        frm.clear_table(fieldname);
        draftDoc[fieldname].forEach((sourceRow) => {
          const row = frm.add_child(fieldname);
          Object.entries(sourceRow || {}).forEach(([key, value]) => {
            if (skippedFields.has(key) || ["parent", "parenttype", "parentfield"].includes(key))
              return;
            row[key] = cloneValue(value);
          });
          restoredRows += 1;
        });
        frm.refresh_field(fieldname);
      });
      frm.refresh_fields();
      console.info("retail_local_draft_recovery: restored local draft", {
        doctype: frm.doctype,
        fields: restoredFields,
        rows: restoredRows
      });
    }
    function cloneValue(value) {
      if (value == null || typeof value !== "object")
        return value;
      return JSON.parse(JSON.stringify(value));
    }
    function serializeDoc(frm) {
      const row_count = getChildRowCount(frm.doc);
      if (!isCriticalDoctype(frm.doctype) && row_count > MAX_SMALL_FORM_ROWS) {
        console.warn("retail_local_draft_recovery: skipped large small-form draft", frm.doctype);
        return null;
      }
      if (row_count > MAX_FULL_DOC_ROWS) {
        console.warn("retail_local_draft_recovery: skipped large full-document draft", frm.doctype, row_count);
        return null;
      }
      const json = JSON.stringify(frm.doc, (key, value) => {
        if (key.startsWith("__"))
          return void 0;
        if (typeof value === "function")
          return void 0;
        return value;
      });
      const bytes = new Blob([json]).size;
      if (bytes > MAX_DRAFT_BYTES) {
        console.warn("retail_local_draft_recovery: skipped oversized draft", frm.doctype, bytes);
        return null;
      }
      return { doc: JSON.parse(json), bytes };
    }
    function updateCleanBaseline(frm) {
      var _a;
      if ((_a = frm.is_dirty) == null ? void 0 : _a.call(frm))
        return;
      frm.__retail_local_draft_baseline = getRecoveryFingerprint(frm, frm.doc);
    }
    function scheduleCleanDirtyStateChecks(frm) {
      if (!shouldTrack(frm) || isLocalDoc(frm))
        return;
      frm.__retail_local_draft_user_changed = false;
      bindUserChangeTracker(frm);
      [100, 500, 1200, 2500].forEach((delay) => {
        setTimeout(() => clearCleanDirtyState(frm), delay);
      });
    }
    function bindUserChangeTracker(frm) {
      if (!(frm == null ? void 0 : frm.$wrapper) || frm.__retail_local_draft_user_tracker_bound)
        return;
      frm.__retail_local_draft_user_tracker_bound = true;
      const markUserChanged = (event) => {
        var _a;
        if (!((_a = event.originalEvent) == null ? void 0 : _a.isTrusted))
          return;
        frm.__retail_local_draft_user_changed = true;
        frm.__retail_local_draft_last_user_event_at = Date.now();
      };
      const markUserEdited = (event) => {
        var _a, _b;
        markUserChanged(event);
        if (!((_a = event.originalEvent) == null ? void 0 : _a.isTrusted) || !shouldTrack(frm))
          return;
        if (!((_b = frm.is_dirty) == null ? void 0 : _b.call(frm))) {
          frm.dirty();
        }
        handleTrackedFormDirty(frm);
      };
      frm.$wrapper.on(
        "input.retailLocalDraftRecovery change.retailLocalDraftRecovery paste.retailLocalDraftRecovery cut.retailLocalDraftRecovery",
        ":input, .control-input, .form-control, .awesomplete, [data-fieldname]",
        markUserEdited
      );
      frm.$wrapper.on(
        "pointerdown.retailLocalDraftRecovery click.retailLocalDraftRecovery",
        ":input, .control-input, .grid-row, .form-control, .awesomplete, [data-fieldname]",
        markUserChanged
      );
    }
    function clearCleanDirtyState(frm) {
      var _a, _b, _c;
      if (!shouldTrack(frm) || !((_a = frm.is_dirty) == null ? void 0 : _a.call(frm)) || isLocalDoc(frm))
        return;
      if (frm.__retail_local_draft_user_changed)
        return;
      const current_fingerprint = getRecoveryFingerprint(frm, frm.doc);
      if (!frm.__retail_local_draft_baseline) {
        frm.__retail_local_draft_baseline = current_fingerprint;
      }
      if (frm.__retail_local_draft_baseline !== current_fingerprint)
        return;
      clearTimeout(frm.__retail_local_draft_timer);
      frm.doc.__unsaved = 0;
      if (frm.beforeUnloadListener) {
        removeEventListener("beforeunload", frm.beforeUnloadListener, { capture: true });
      }
      (_c = (_b = frm.toolbar) == null ? void 0 : _b.refresh) == null ? void 0 : _c.call(_b);
    }
    function hasChangedFromCleanBaseline(frm) {
      var _a;
      if (!(frm == null ? void 0 : frm.doc))
        return false;
      if (!frm.__retail_local_draft_baseline) {
        updateCleanBaseline(frm);
        return ((_a = frm.is_dirty) == null ? void 0 : _a.call(frm)) && isLocalDoc(frm) && hasRecoverableLocalDraftContent(frm, frm.doc);
      }
      return frm.__retail_local_draft_baseline !== getRecoveryFingerprint(frm, frm.doc);
    }
    function hasRecoverableDraftDifference(frm, draftDoc) {
      return getRecoveryFingerprint(frm, frm.doc) !== getRecoveryFingerprint(frm, draftDoc);
    }
    function getRecoveryFingerprint(frm, doc) {
      return JSON.stringify(getRecoveryComparableDoc(frm, doc));
    }
    function getRecoveryComparableDoc(frm, doc) {
      var _a;
      const metaFields = ((_a = frm.meta) == null ? void 0 : _a.fields) || [];
      const tableFields = new Set(metaFields.filter((df) => df.fieldtype === "Table").map((df) => df.fieldname));
      const fieldnames = new Set(metaFields.map((df) => df.fieldname));
      const comparable = {};
      metaFields.forEach((df) => {
        const fieldname = df.fieldname;
        if (!fieldname || !fieldnames.has(fieldname) || LOCAL_DRAFT_PROMPT_IGNORE_FIELDS.has(fieldname))
          return;
        if (tableFields.has(fieldname)) {
          const rows = Array.isArray(doc == null ? void 0 : doc[fieldname]) ? doc[fieldname] : [];
          const comparableRows = rows.map((row) => getComparableChildRow(row)).filter((row) => Object.keys(row).length);
          if (comparableRows.length)
            comparable[fieldname] = comparableRows;
          return;
        }
        const value = normalizeComparableValue(doc == null ? void 0 : doc[fieldname]);
        if (hasMeaningfulValue(value))
          comparable[fieldname] = value;
      });
      return comparable;
    }
    function getComparableChildRow(row) {
      const comparable = {};
      Object.entries(row || {}).forEach(([fieldname, value]) => {
        if (LOCAL_DRAFT_PROMPT_IGNORE_FIELDS.has(fieldname) || ["name", "parent", "parenttype", "parentfield", "idx"].includes(fieldname)) {
          return;
        }
        value = normalizeComparableValue(value);
        if (hasMeaningfulValue(value))
          comparable[fieldname] = value;
      });
      return comparable;
    }
    function normalizeComparableValue(value) {
      if (value == null)
        return "";
      if (Array.isArray(value))
        return value.map(normalizeComparableValue);
      if (typeof value === "object") {
        const normalized = {};
        Object.keys(value).sort().forEach((key) => {
          normalized[key] = normalizeComparableValue(value[key]);
        });
        return normalized;
      }
      return value;
    }
    function getChildRowCount(doc) {
      return Object.values(doc || {}).reduce((total, value) => {
        return total + (Array.isArray(value) ? value.length : 0);
      }, 0);
    }
    function canUseFullDocDraft(frm) {
      return getChildRowCount(frm == null ? void 0 : frm.doc) <= MAX_FULL_DOC_ROWS;
    }
    function getDraftKey(frm) {
      if (!(frm == null ? void 0 : frm.doctype) || !(frm == null ? void 0 : frm.doc))
        return null;
      const company = frm.doc.company || frappe.defaults.get_default("company") || "";
      return [frappe.session.user, company, frm.doctype, getDocName(frm)].join("::");
    }
    function getDocName(frm) {
      if (!(frm == null ? void 0 : frm.doc))
        return "";
      if (isLocalDoc(frm))
        return "__new__";
      if (!frm.doc.__islocal && frm.doc.name)
        return frm.doc.name;
      return frm.doc.name || "new";
    }
    function isLocalDoc(frm) {
      var _a, _b;
      return !!((_a = frm == null ? void 0 : frm.doc) == null ? void 0 : _a.__islocal) || String(((_b = frm == null ? void 0 : frm.doc) == null ? void 0 : _b.name) || "").startsWith("new-");
    }
    function getBrowserSessionId() {
      let session_id = sessionStorage.getItem(SESSION_ID_KEY);
      if (!session_id) {
        session_id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
        sessionStorage.setItem(SESSION_ID_KEY, session_id);
      }
      return session_id;
    }
    async function deleteDraft(frm) {
      clearTimeout(frm == null ? void 0 : frm.__retail_local_draft_timer);
      const key = getDraftKey(frm);
      if (key) {
        await deleteDraftByKey(key);
        deleteEmergencyDraftByKey(key);
      }
    }
    function getEmergencyDraftKey(key) {
      return `${EMERGENCY_DRAFT_PREFIX}${key}`;
    }
    function deleteEmergencyDraftByKey(key) {
      try {
        localStorage.removeItem(getEmergencyDraftKey(key));
      } catch (e) {
      }
    }
    function openDb() {
      if (window.__retail_local_draft_db)
        return window.__retail_local_draft_db;
      window.__retail_local_draft_db = new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);
        request.onupgradeneeded = () => {
          const db = request.result;
          if (!db.objectStoreNames.contains(STORE_NAME)) {
            const store = db.createObjectStore(STORE_NAME, { keyPath: "key" });
            store.createIndex("updated_at", "updated_at", { unique: false });
          }
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
      return window.__retail_local_draft_db;
    }
    async function putDraft(draft) {
      const db = await openDb();
      return txRequest(db, "readwrite", (store) => store.put(draft));
    }
    async function getDraft(key) {
      const db = await openDb();
      return txRequest(db, "readonly", (store) => store.get(key));
    }
    async function deleteDraftByKey(key) {
      const db = await openDb();
      return txRequest(db, "readwrite", (store) => store.delete(key));
    }
    async function cleanupOldDrafts() {
      const db = await openDb();
      return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, "readwrite");
        const request = tx.objectStore(STORE_NAME).openCursor();
        request.onsuccess = () => {
          const cursor = request.result;
          if (!cursor)
            return;
          if (isExpiredDraft(cursor.value)) {
            cursor.delete();
          }
          cursor.continue();
        };
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
        tx.onabort = () => reject(tx.error);
      });
    }
    function exposeDebugTools() {
      window.retailLocalDraftRecovery = {
        async current() {
          var _a;
          const frm = window.cur_frm;
          if (!frm)
            return null;
          const key = getDraftKey(frm);
          return {
            key,
            tracked: shouldTrack(frm),
            dirty: !!((_a = frm.is_dirty) == null ? void 0 : _a.call(frm)),
            delay_ms: getSaveDelayMs(frm.doctype),
            draft: key ? await getDraft(key) : null
          };
        },
        async saveNow() {
          const frm = window.cur_frm;
          if (!shouldTrack(frm))
            return false;
          await saveDraft(frm);
          return true;
        }
      };
    }
    function txRequest(db, mode, callback) {
      return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, mode);
        const store = tx.objectStore(STORE_NAME);
        const request = callback(store);
        let result;
        request.onsuccess = () => {
          result = request.result;
        };
        tx.oncomplete = () => resolve(result);
        tx.onerror = () => reject(tx.error);
        tx.onabort = () => reject(tx.error);
      });
    }
    boot();
  })();

  // ../retail/retail/public/js/forms/transaction_items.js
  (function() {
    if (window.__retail_transaction_items_booted)
      return;
    window.__retail_transaction_items_booted = true;
    function boot() {
      var _a, _b, _c;
      if (typeof ((_c = (_b = (_a = window.frappe) == null ? void 0 : _a.ui) == null ? void 0 : _b.form) == null ? void 0 : _c.on) !== "function") {
        setTimeout(boot, 100);
        return;
      }
      registerTransactionItems();
    }
    function registerTransactionItems() {
      if (window.__retail_transaction_items_registered)
        return;
      window.__retail_transaction_items_registered = true;
      const vatItemDoctypes = [
        "Purchase Order Item",
        "Purchase Receipt Item",
        "Purchase Invoice Item",
        "Supplier Quotation Item",
        "Material Request Item",
        "Subcontracting Order Item",
        "Subcontracting Receipt Item",
        "Sales Order Item",
        "Delivery Note Item",
        "Sales Invoice Item",
        "POS Invoice Item",
        "Quotation Item",
        "Opportunity Item",
        "Blanket Order Item"
      ];
      const totalsFormDoctypes = {};
      const liveVatFormDoctypes = {
        "Purchase Order": "Purchase Tax",
        "Purchase Receipt": "Purchase Tax",
        "Purchase Invoice": "Purchase Tax",
        "Sales Invoice": "Sales Tax",
        "Sales Order": "Sales Tax",
        "Delivery Note": "Sales Tax",
        "POS Invoice": "Sales Tax",
        "Quotation": "Sales Tax"
      };
      const totalsItemDoctypes = [
        "Purchase Order Item",
        "Purchase Receipt Item",
        "Purchase Invoice Item",
        "Sales Order Item"
      ];
      vatItemDoctypes.forEach((doctype) => {
        frappe.ui.form.on(doctype, {
          item_code(frm, cdt, cdn) {
            syncVatRates(frm, cdt, cdn, "rate");
            scheduleVatSync(frm, cdt, cdn, "rate");
            scheduleVatTaxRowsSync(frm);
            renderTransactionTotals(frm);
          },
          rate(frm, cdt, cdn) {
            syncVatRates(frm, cdt, cdn, "rate");
            queueVatTaxRowsSync(frm);
            renderTransactionTotals(frm);
          },
          price_list_rate(frm, cdt, cdn) {
            syncVatRates(frm, cdt, cdn, "rate");
            queueVatTaxRowsSync(frm);
            renderTransactionTotals(frm);
          },
          net_amount(frm) {
            refreshRowVatAmounts(frm);
          },
          net_rate(frm, cdt, cdn) {
            syncVatRates(frm, cdt, cdn, "rate");
            queueVatTaxRowsSync(frm);
            renderTransactionTotals(frm);
          },
          item_tax_template(frm, cdt, cdn) {
            syncVatRates(frm, cdt, cdn, "rate");
            queueVatTaxRowsSync(frm);
            renderTransactionTotals(frm);
          },
          tax_rate(frm, cdt, cdn) {
            syncVatRates(frm, cdt, cdn, "rate");
            queueVatTaxRowsSync(frm);
            renderTransactionTotals(frm);
          },
          qty(frm, cdt, cdn) {
            syncVatRates(frm, cdt, cdn, "qty");
            queueVatTaxRowsSync(frm);
            renderTransactionTotals(frm);
          },
          custom_rate_including_vat(frm, cdt, cdn) {
            syncVatRates(frm, cdt, cdn, "inclusive");
            queueVatTaxRowsSync(frm);
            renderTransactionTotals(frm);
          },
          amount(frm, cdt, cdn) {
            syncVatRates(frm, cdt, cdn, "exclusive_amount");
            queueVatTaxRowsSync(frm);
            renderTransactionTotals(frm);
          },
          custom_amount_including_vat(frm, cdt, cdn) {
            syncVatRates(frm, cdt, cdn, "inclusive_amount");
            queueVatTaxRowsSync(frm);
            renderTransactionTotals(frm);
          },
          items_remove(frm) {
            queueVatTaxRowsSync(frm);
          }
        });
      });
      vatItemDoctypes.forEach((child) => {
        frappe.ui.form.on(child.replace(/ Item$/, ""), {
          refresh: refreshRowVatAmounts,
          total_taxes_and_charges: refreshRowVatAmounts
        });
      });
      function isCompletedPos(frm) {
        var _a;
        return ((_a = frm == null ? void 0 : frm.doc) == null ? void 0 : _a.doctype) === "POS Invoice" && !!frm.doc.custom_pos_completed_payload;
      }
      async function refreshRowVatAmounts(frm) {
        var _a, _b, _c, _d, _e;
        if (isCompletedPos(frm))
          return;
        const grid = (_a = frm.fields_dict.items) == null ? void 0 : _a.grid;
        (_b = grid == null ? void 0 : grid.update_docfield_property) == null ? void 0 : _b.call(grid, "custom_vat_amount", "read_only", 1);
        for (const row of frm.doc.items || []) {
          const field = frappe.meta.get_docfield(row.doctype, "custom_vat_amount", row.name);
          if (!field)
            continue;
          field.read_only = 1;
          const rate = row.item_code ? await getVatRate(frm, row, row.doctype) : 0;
          const amount = flt(row.qty) * flt(row.rate);
          const precision = cint(field.precision) || 2;
          row.custom_vat_amount = flt(amount * rate / 100, precision);
          (_e = (_d = (_c = grid == null ? void 0 : grid.grid_rows_by_docname) == null ? void 0 : _c[row.name]) == null ? void 0 : _d.refresh_field) == null ? void 0 : _e.call(_d, "custom_vat_amount");
        }
      }
      Object.keys(liveVatFormDoctypes).forEach((doctype) => {
        frappe.ui.form.on(doctype, {
          refresh(frm) {
            placeVatFieldBeforeGrandTotal(frm);
          },
          company(frm) {
            queueVatTaxRowsSync(frm);
          },
          cost_center(frm) {
            queueVatTaxRowsSync(frm);
          },
          taxes_and_charges(frm) {
            queueVatTaxRowsSync(frm);
          },
          apply_discount_on(frm) {
            runErpnextTotals(frm);
            placeVatFieldBeforeGrandTotal(frm);
          },
          additional_discount_percentage(frm) {
            runErpnextTotals(frm);
            placeVatFieldBeforeGrandTotal(frm);
          },
          discount_amount(frm) {
            runErpnextTotals(frm);
            placeVatFieldBeforeGrandTotal(frm);
          },
          total_taxes_and_charges(frm) {
            placeVatFieldBeforeGrandTotal(frm);
          },
          grand_total(frm) {
            placeVatFieldBeforeGrandTotal(frm);
          }
        });
      });
      Object.keys(totalsFormDoctypes).forEach((doctype) => {
        frappe.ui.form.on(doctype, {
          refresh(frm) {
            renderTransactionTotals(frm);
          },
          net_total(frm) {
            renderTransactionTotals(frm);
          },
          total_taxes_and_charges(frm) {
            renderTransactionTotals(frm);
          },
          grand_total(frm) {
            renderTransactionTotals(frm);
          },
          rounded_total(frm) {
            renderTransactionTotals(frm);
          },
          taxes_and_charges(frm) {
            renderTransactionTotals(frm);
          }
        });
      });
      totalsItemDoctypes.forEach((doctype) => {
        frappe.ui.form.on(doctype, {
          net_amount(frm) {
            renderTransactionTotals(frm);
          },
          item_tax_template(frm) {
            renderTransactionTotals(frm);
          },
          items_remove(frm) {
            renderTransactionTotals(frm);
          }
        });
      });
      frappe.ui.form.on("Sales Taxes and Charges", taxHandlers());
      frappe.ui.form.on("Purchase Taxes and Charges", taxHandlers());
      function scheduleVatTaxRowsSync(frm) {
        [250, 700].forEach((delay) => {
          setTimeout(() => queueVatTaxRowsSync(frm), delay);
        });
      }
      function scheduleVatSync(frm, cdt, cdn, source) {
        [150, 500].forEach((delay) => {
          setTimeout(() => {
            var _a;
            if (!((_a = locals[cdt]) == null ? void 0 : _a[cdn]))
              return;
            syncVatRates(frm, cdt, cdn, source);
          }, delay);
        });
      }
      async function syncVatRates(frm, cdt, cdn, source) {
        var _a, _b, _c;
        if (isCompletedPos(frm))
          return;
        if (!isEditableDraft(frm))
          return;
        const row = (_a = locals[cdt]) == null ? void 0 : _a[cdn];
        if (!row || row.__retail_vat_syncing || !row.item_code)
          return;
        if (!frappe.meta.get_docfield(cdt, "custom_rate_including_vat", cdn))
          return;
        row.__retail_vat_syncing = true;
        try {
          const vatRate = await getVatRate(frm, row, cdt);
          const factor = 1 + flt(vatRate) / 100;
          const precision = cint((_b = frappe.meta.get_docfield(cdt, "rate", cdn)) == null ? void 0 : _b.precision) || 2;
          const amountPrecision = cint((_c = frappe.meta.get_docfield(cdt, "amount", cdn)) == null ? void 0 : _c.precision) || precision;
          const amountField = frappe.meta.get_docfield(cdt, "amount", cdn);
          const qty = flt(row.qty);
          const values = {};
          let inclusiveRate = flt(row.custom_rate_including_vat);
          let exclusiveRate = getExclusiveRateForVat(row, qty);
          if (source === "inclusive") {
            exclusiveRate = factor ? inclusiveRate / factor : inclusiveRate;
            values.rate = flt(exclusiveRate, precision);
            if (amountField) {
              values.amount = flt(qty * exclusiveRate, amountPrecision);
            }
          } else if (source === "inclusive_amount") {
            const inclusiveAmount = flt(row.custom_amount_including_vat);
            inclusiveRate = qty ? inclusiveAmount / qty : 0;
            exclusiveRate = factor ? inclusiveRate / factor : inclusiveRate;
            values.custom_rate_including_vat = flt(inclusiveRate, precision);
            values.rate = flt(exclusiveRate, precision);
            if (amountField) {
              values.amount = flt(qty * exclusiveRate, amountPrecision);
            }
          } else if (source === "exclusive_amount") {
            const exclusiveAmount = flt(row.amount);
            exclusiveRate = qty ? exclusiveAmount / qty : 0;
            inclusiveRate = flt(exclusiveRate * factor, precision);
            values.rate = flt(exclusiveRate, precision);
            values.custom_rate_including_vat = inclusiveRate;
            if (row.custom_amount_including_vat !== void 0) {
              values.custom_amount_including_vat = flt(qty * inclusiveRate, amountPrecision);
            }
          } else {
            inclusiveRate = flt(exclusiveRate * factor, precision);
            values.custom_rate_including_vat = inclusiveRate;
            if (amountField) {
              values.amount = flt(qty * exclusiveRate, amountPrecision);
            }
          }
          if (source !== "inclusive_amount" && row.custom_amount_including_vat !== void 0) {
            values.custom_amount_including_vat = flt(qty * inclusiveRate, amountPrecision);
          }
          if (frappe.meta.get_docfield(cdt, "custom_vat_amount", cdn)) {
            values.custom_vat_amount = flt(qty * exclusiveRate * flt(vatRate) / 100, amountPrecision);
          }
          if (!Object.keys(values).length)
            return;
          await setRowValues(frm, cdt, cdn, values);
          queueVatTaxRowsSync(frm);
          renderTransactionTotals(frm);
        } finally {
          if (row)
            row.__retail_vat_syncing = false;
        }
      }
      function queueVatTaxRowsSync(frm) {
        if (!canSyncVatTaxRows(frm))
          return;
        clearTimeout(frm.__retail_vat_tax_rows_timer);
        frm.__retail_vat_tax_rows_timer = setTimeout(() => {
          syncVatTaxRows(frm);
        }, 200);
      }
      function canSyncVatTaxRows(frm) {
        var _a;
        return Boolean(
          (frm == null ? void 0 : frm.doc) && liveVatFormDoctypes[frm.doc.doctype] && isEditableDraft(frm) && ((_a = frm.fields_dict) == null ? void 0 : _a.taxes) && Array.isArray(frm.doc.items)
        );
      }
      function isEditableDraft(frm) {
        var _a;
        return cint((_a = frm == null ? void 0 : frm.doc) == null ? void 0 : _a.docstatus) === 0;
      }
      async function syncVatTaxRows(frm) {
        if (isCompletedPos(frm))
          return;
        if (!canSyncVatTaxRows(frm) || frm.__retail_syncing_vat_tax_rows)
          return;
        frm.__retail_syncing_vat_tax_rows = true;
        try {
          const response = await frappe.call({
            method: "retail.domains.transactions.vat.get_transaction_vat_tax_rows",
            args: {
              doc: frm.doc
            }
          });
          const setup = normalizeVatTaxSetup(response.message);
          applyItemTaxRates(frm, setup.item_tax_rates);
          replaceManagedVatTaxRows(frm, setup.tax_rows);
          await runErpnextTotals(frm);
          placeVatFieldBeforeGrandTotal(frm);
        } finally {
          frm.__retail_syncing_vat_tax_rows = false;
        }
      }
      function normalizeVatTaxSetup(message) {
        if (Array.isArray(message)) {
          return { tax_rows: message, item_tax_rates: {} };
        }
        return {
          tax_rows: (message == null ? void 0 : message.tax_rows) || [],
          item_tax_rates: (message == null ? void 0 : message.item_tax_rates) || {}
        };
      }
      function applyItemTaxRates(frm, itemTaxRates) {
        Object.entries(itemTaxRates || {}).forEach(([rowName, itemTaxRate]) => {
          var _a, _b, _c, _d, _e;
          const row = (frm.doc.items || []).find((item) => item.name === rowName);
          if (!row || row.item_tax_rate === void 0)
            return;
          row.item_tax_rate = itemTaxRate || "{}";
          (_e = (_d = (_c = (_b = (_a = frm.fields_dict.items) == null ? void 0 : _a.grid) == null ? void 0 : _b.grid_rows_by_docname) == null ? void 0 : _c[row.name]) == null ? void 0 : _d.refresh_field) == null ? void 0 : _e.call(_d, "item_tax_rate");
        });
      }
      function replaceManagedVatTaxRows(frm, taxRows) {
        const taxLabel = liveVatFormDoctypes[frm.doc.doctype];
        const taxTable = frm.doc.taxes || [];
        const managedRows = taxTable.filter((row) => isManagedVatTaxRow(row, taxLabel));
        managedRows.forEach((row) => frappe.model.clear_doc(row.doctype, row.name));
        frm.doc.taxes = taxTable.filter((row) => !isManagedVatTaxRow(row, taxLabel));
        taxRows.forEach((values) => {
          const row = frm.add_child("taxes");
          Object.assign(row, values);
        });
        refreshTaxTable(frm);
      }
      async function runErpnextTotals(frm) {
        var _a;
        if (isCompletedPos(frm))
          return;
        if (!(frm == null ? void 0 : frm.doc) || frm.__retail_running_erpnext_totals)
          return;
        frm.__retail_running_erpnext_totals = true;
        try {
          if ((_a = frm.cscript) == null ? void 0 : _a.calculate_taxes_and_totals) {
            await frm.cscript.calculate_taxes_and_totals();
          } else {
            frm.refresh_fields();
          }
          placeVatFieldBeforeGrandTotal(frm);
        } finally {
          frm.__retail_running_erpnext_totals = false;
        }
      }
      function placeVatFieldBeforeGrandTotal(frm) {
        var _a, _b, _c, _d;
        if (!liveVatFormDoctypes[(_a = frm == null ? void 0 : frm.doc) == null ? void 0 : _a.doctype])
          return;
        const vatField = (_b = frm.fields_dict) == null ? void 0 : _b.total_taxes_and_charges;
        const grandField = (_c = frm.fields_dict) == null ? void 0 : _c.grand_total;
        if (!vatField || !grandField)
          return;
        frm.set_df_property("total_taxes_and_charges", "hidden", 0);
        frm.set_df_property("total_taxes_and_charges", "label", __("VAT"));
        vatField.df.hidden = 0;
        vatField.df.label = __("VAT");
        (_d = vatField.refresh) == null ? void 0 : _d.call(vatField);
        const vatWrapper = $(vatField.wrapper);
        const grandWrapper = $(grandField.wrapper);
        if (!vatWrapper.length || !grandWrapper.length)
          return;
        vatWrapper.removeClass("hide-control").show();
        vatWrapper.insertBefore(grandWrapper);
      }
      function refreshTaxTable(frm) {
        frm.refresh_field("taxes");
      }
      function isManagedVatTaxRow(row, taxLabel) {
        const description = String((row == null ? void 0 : row.description) || "").trim();
        return description.startsWith(`${taxLabel} [`);
      }
      async function setRowValues(frm, cdt, cdn, values) {
        var _a, _b, _c;
        for (const [fieldname, value] of Object.entries(values)) {
          await frappe.model.set_value(cdt, cdn, fieldname, value);
        }
        const gridRow = (_c = (_b = (_a = frm.fields_dict.items) == null ? void 0 : _a.grid) == null ? void 0 : _b.grid_rows_by_docname) == null ? void 0 : _c[cdn];
        Object.keys(values).forEach((fieldname) => {
          var _a2;
          return (_a2 = gridRow == null ? void 0 : gridRow.refresh_field) == null ? void 0 : _a2.call(gridRow, fieldname);
        });
      }
      function getExclusiveRateForVat(row, qty) {
        if (hasEnteredValue(row.rate))
          return flt(row.rate);
        if (qty && hasEnteredValue(row.amount) && flt(row.amount))
          return flt(row.amount) / qty;
        if (hasEnteredValue(row.net_rate) && flt(row.net_rate))
          return flt(row.net_rate);
        if (hasEnteredValue(row.price_list_rate) && flt(row.price_list_rate))
          return flt(row.price_list_rate);
        return flt(row.rate);
      }
      async function getVatRate(frm, row, childDoctype) {
        const parentDoc = (frm == null ? void 0 : frm.doc) || {};
        const rowRate = flt(row.tax_rate);
        if (rowRate)
          return rowRate;
        const response = await frappe.call({
          method: "retail.domains.transactions.vat.get_transaction_item_vat_rate",
          args: {
            item_code: row.item_code,
            child_doctype: childDoctype,
            parent_doctype: parentDoc.doctype,
            transaction_type: parentDoc.transaction_type,
            item_tax_template: row.item_tax_template
          }
        });
        return flt(response.message);
      }
      function taxHandlers() {
        return {
          tax_amount_after_discount_amount(frm) {
            renderTransactionTotals(frm);
          },
          tax_amount(frm) {
            renderTransactionTotals(frm);
          },
          rate(frm) {
            renderTransactionTotals(frm);
          },
          description(frm) {
            renderTransactionTotals(frm);
          }
        };
      }
      function renderTransactionTotals(frm) {
        if (!totalsFormDoctypes[frm.doctype])
          return;
        const field = frm.fields_dict.custom_retail_totals_summary;
        if (!field)
          return;
        applyTotalsLayout(field);
        const currency = frm.doc.currency;
        const subtotal = getSubtotal(frm);
        const tax = getTaxAmount(frm);
        const inclusiveTotal = getInclusiveTotal(frm);
        const total = hasEnteredValue(inclusiveTotal) ? inclusiveTotal : hasEnteredValue(frm.doc.grand_total) ? flt(frm.doc.grand_total) : subtotal + tax;
        field.$wrapper.html(`
			<style>
				.retail-transaction-totals {
					border-top: 1px solid var(--border-color);
					margin-top: 8px;
					max-width: 100%;
				}
				.retail-transaction-totals-section > .section-body {
					align-items: flex-start;
					display: flex;
				}
				.retail-transaction-totals-section > .section-body > .retail-transaction-spacer-column {
					display: none !important;
				}
				.retail-transaction-totals-section > .section-body > .retail-transaction-quantity-column {
					flex: 0 0 32% !important;
					max-width: 32% !important;
				}
				.retail-transaction-totals-section > .section-body > .retail-transaction-totals-column {
					flex: 0 0 50% !important;
					margin-left: auto;
					max-width: 50% !important;
				}
				@media (max-width: 767.98px) {
					.retail-transaction-totals-section > .section-body {
						display: block;
					}
					.retail-transaction-totals-section > .section-body > .retail-transaction-quantity-column,
					.retail-transaction-totals-section > .section-body > .retail-transaction-totals-column {
						flex: 0 0 100% !important;
						max-width: 100% !important;
					}
				}
				.retail-transaction-total-row {
					align-items: center;
					border-bottom: 1px solid var(--border-color);
					display: grid;
					grid-template-columns: minmax(0, 1fr) auto;
					gap: 16px;
					min-height: 42px;
					padding: 8px 4px;
				}
				.retail-transaction-total-row.total {
					background: var(--subtle-fg);
					font-weight: 700;
					padding-left: 8px;
					padding-right: 8px;
				}
				.retail-transaction-total-label {
					color: var(--text-muted);
					overflow-wrap: anywhere;
				}
				.retail-transaction-total-row.total .retail-transaction-total-label,
				.retail-transaction-total-row.total .retail-transaction-total-value {
					color: var(--primary);
				}
				.retail-transaction-total-value {
					font-variant-numeric: tabular-nums;
					text-align: right;
				}
			</style>
			<div class="retail-transaction-totals">
				${getTotalRow(__("Sub Total"), subtotal, currency)}
				${getTotalRow(getTaxLabel(frm), tax, currency)}
				${getTotalRow(__("Total ({0})", [currency || ""]), total, currency, true)}
			</div>
		`);
      }
      function applyTotalsLayout(field) {
        const section = field.$wrapper.closest(".form-section");
        if (!(section == null ? void 0 : section.length))
          return;
        const columns = section.children(".section-body").children(".form-column");
        const totalsColumn = field.$wrapper.closest(".form-column");
        const quantityColumn = columns.filter((_, column) => $(column).find('[data-fieldname="total_qty"]').length).first();
        section.addClass("retail-transaction-totals-section");
        columns.removeClass(
          "retail-transaction-quantity-column retail-transaction-totals-column retail-transaction-spacer-column"
        );
        quantityColumn.addClass("retail-transaction-quantity-column");
        totalsColumn.addClass("retail-transaction-totals-column");
        columns.not(quantityColumn).not(totalsColumn).addClass("retail-transaction-spacer-column");
      }
      function getTotalRow(label, value, currency, isTotal) {
        return `
			<div class="retail-transaction-total-row ${isTotal ? "total" : ""}">
				<div class="retail-transaction-total-label">${escapeHtml(label)}</div>
				<div class="retail-transaction-total-value">${format_currency(value, currency)}</div>
			</div>
		`;
      }
      function getSubtotal(frm) {
        const items = frm.doc.items || [];
        const itemSubtotal = items.reduce((total, row) => total + getExclusiveAmount(row), 0);
        if (items.length)
          return flt(itemSubtotal);
        return flt(itemSubtotal || frm.doc.net_total || frm.doc.total || frm.doc.base_net_total || frm.doc.base_total);
      }
      function getTaxAmount(frm) {
        const items = frm.doc.items || [];
        const hasInclusiveAmount = items.some((row) => hasEnteredValue(getInclusiveAmount(row)));
        const itemTax = items.reduce((total, row) => {
          const inclusiveAmount = getInclusiveAmount(row);
          if (!hasEnteredValue(inclusiveAmount))
            return total;
          return total + (inclusiveAmount - getExclusiveAmount(row));
        }, 0);
        if (hasInclusiveAmount)
          return flt(itemTax);
        const rowTax = (frm.doc.taxes || []).reduce((total, row) => {
          var _a;
          const amount = (_a = row.tax_amount_after_discount_amount) != null ? _a : row.tax_amount;
          return total + flt(amount);
        }, 0);
        if (rowTax)
          return rowTax;
        return flt(frm.doc.total_taxes_and_charges);
      }
      function getInclusiveTotal(frm) {
        const items = frm.doc.items || [];
        if (!items.some((row) => hasEnteredValue(getInclusiveAmount(row))))
          return null;
        return flt(items.reduce((total, row) => total + flt(getInclusiveAmount(row)), 0));
      }
      function getInclusiveAmount(row) {
        const exclusiveAmount = getExclusiveAmount(row);
        const inclusiveRate = flt(row.custom_rate_including_vat);
        if (hasEnteredValue(row.custom_rate_including_vat) && (inclusiveRate || !exclusiveAmount)) {
          return flt(row.qty) * inclusiveRate;
        }
        const inclusiveAmount = flt(row.custom_amount_including_vat);
        if (hasEnteredValue(row.custom_amount_including_vat) && (inclusiveAmount || !exclusiveAmount)) {
          return inclusiveAmount;
        }
        return null;
      }
      function getExclusiveAmount(row) {
        if (hasEnteredValue(row.rate))
          return flt(row.qty) * flt(row.rate);
        return flt(row.amount);
      }
      function getTaxLabel(frm) {
        const template = frm.doc.taxes_and_charges;
        if (template)
          return __("{0} [{1}]", [totalsFormDoctypes[frm.doctype], template]);
        const taxRows = frm.doc.taxes || [];
        const rates = [...new Set(taxRows.map((row) => flt(row.rate)).filter((rate) => rate))];
        if (rates.length === 1)
          return __("{0} [{1}%]", [totalsFormDoctypes[frm.doctype], rates[0]]);
        const description = taxRows.map((row) => row.description).filter(Boolean)[0];
        if (!description)
          return __(totalsFormDoctypes[frm.doctype]);
        if (description.startsWith(`${totalsFormDoctypes[frm.doctype]} [`))
          return __(description);
        return __("{0} [{1}]", [totalsFormDoctypes[frm.doctype], description]);
      }
      function hasEnteredValue(value) {
        return value !== void 0 && value !== null && value !== "";
      }
      function escapeHtml(value) {
        var _a;
        if ((_a = frappe.utils) == null ? void 0 : _a.escape_html)
          return frappe.utils.escape_html(String(value || ""));
        return String(value || "").replace(/[&<>"']/g, (char) => ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;"
        })[char]);
      }
    }
    boot();
  })();

  // ../retail/retail/public/js/scale_sales.js
  (() => {
    frappe.provide("retail.scale_sales");
    const sales = /* @__PURE__ */ new Set(["Sales Invoice", "Sales Order", "Delivery Note", "Quotation", "POS Invoice"]);
    function preparePrecision(frm) {
      const child = frm.fields_dict.items.grid.doctype;
      for (const field of ["qty", "rate", "price_list_rate"]) {
        const df = frappe.meta.get_docfield(child, field, frm.doc.name);
        if (df)
          df.precision = 9;
      }
    }
    retail.scale_sales.apply = async function(frm, row, label) {
      if (frm.doc.docstatus !== 0)
        frappe.throw(__("Scale labels can only be applied to draft sales."));
      preparePrecision(frm);
      let qty = label.scale_qty;
      let rate = label.scale_rate == null ? flt(row.rate) : label.scale_rate;
      const amount = label.scale_amount;
      if (qty == null) {
        qty = rate ? amount / rate : 1;
        if (!rate)
          rate = amount;
      } else if (amount != null) {
        rate = amount / qty;
      } else if (!rate && label.scale_rate == null) {
        rate = await new Promise((resolve, reject) => {
          const dialog = frappe.prompt({
            fieldname: "rate",
            label: __("Selling Rate"),
            fieldtype: "Currency",
            reqd: 1
          }, (values) => {
            if (flt(values.rate) <= 0) {
              reject(new Error(__("Enter a positive selling rate.")));
              return;
            }
            resolve(flt(values.rate));
          }, __("Enter New Price"));
          dialog.$wrapper.on("hidden.bs.modal", () => reject(new Error(__("Scale sale cancelled."))));
        });
      }
      await frappe.model.set_value(row.doctype, row.name, "qty", frm.doc.is_return ? -qty : qty);
      await frappe.model.set_value(row.doctype, row.name, {
        price_list_rate: rate,
        discount_percentage: 0,
        discount_amount: 0,
        margin_type: "",
        margin_rate_or_amount: 0,
        rate,
        barcode: label.barcode
      });
      await frm.cscript.calculate_taxes_and_totals();
      frm.refresh_field("items");
    };
    function install() {
      var _a, _b, _c;
      const prototype = (_c = (_b = (_a = window.erpnext) == null ? void 0 : _a.utils) == null ? void 0 : _b.BarcodeScanner) == null ? void 0 : _c.prototype;
      if (!prototype || prototype.__retail_scale_sales)
        return;
      prototype.__retail_scale_sales = true;
      const scan = prototype.scan_api_call;
      prototype.scan_api_call = function(input, callback) {
        if (!sales.has(this.frm.doc.doctype) || ![
          "erpnext.stock.utils.scan_barcode",
          "retail.domains.item.packing_scan.scan_barcode"
        ].includes(this.scan_api)) {
          return scan.call(this, input, callback);
        }
        return frappe.call({
          method: "retail.domains.item.packing_scan.scan_barcode",
          args: { search_value: input, ctx: {
            set_warehouse: this.frm.doc.set_warehouse,
            company: this.frm.doc.company
          } }
        }).then(callback);
      };
      const update = prototype.update_table;
      prototype.update_table = async function(data) {
        if (!sales.has(this.frm.doc.doctype) || !data.scale_barcode_type)
          return update.call(this, data);
        if (this.frm.doc.docstatus !== 0 || this.dont_allow_new_row) {
          frappe.throw(__("Add scale labels to an editable sales document."));
        }
        const grid = this.frm.fields_dict[this.items_table_name].grid;
        const row = (this.frm.doc[this.items_table_name] || []).find((item) => !item.item_code) || frappe.model.add_child(this.frm.doc, grid.doctype, this.items_table_name);
        await this.frm.script_manager.trigger(`${this.items_table_name}_add`, row.doctype, row.name);
        await this.set_warehouse(row);
        await frappe.model.set_value(row.doctype, row.name, "item_code", data.item_code);
        await frappe.model.set_value(row.doctype, row.name, "uom", data.uom);
        await retail.scale_sales.apply(this.frm, row, data);
        this.clean_up();
        return row;
      };
    }
    install();
    $(document).on("startup", install);
    for (const doctype of sales)
      frappe.ui.form.on(doctype, { setup: install, async refresh(frm) {
        install();
        if (frm.doc.docstatus !== 0)
          return;
        for (const row of frm.doc.items || []) {
          if (!/^99\d{11}$|^99\d{12}$|^99\d{17}$/.test(row.barcode || ""))
            continue;
          const { message } = await frappe.call({
            method: "retail.domains.item.packing_scan.scan_barcode",
            args: { search_value: row.barcode }
          });
          if ((message == null ? void 0 : message.scale_barcode_type) && message.item_code === row.item_code) {
            preparePrecision(frm);
            break;
          }
        }
      } });
  })();

  // ../retail/retail/public/js/zebra_label_loader.js
  (function() {
    frappe.provide("retail.zebra");
    let loading;
    async function openBulkPrintDialog(opts) {
      loading || (loading = frappe.require("retail_labels.bundle.js"));
      await loading;
      if (retail.zebra.open_bulk_print_dialog === openBulkPrintDialog) {
        loading = null;
        throw new Error("Unable to load label printing. Please try again.");
      }
      return retail.zebra.open_bulk_print_dialog(opts);
    }
    retail.zebra.open_bulk_print_dialog = openBulkPrintDialog;
  })();

  // ../retail/retail/public/js/brand_theme_switcher.js
  (function() {
    const STORAGE_KEY = "retail.brand_theme";
    const ATTRIBUTE = "data-retail-brand-theme";
    const DEFAULT_THEME = "executive-navy";
    const THEMES = [
      {
        name: "classic",
        label: "Classic ERPNext",
        description: "Original ERPNext look. Safest fallback.",
        preview: {
          primary: "#64748b",
          accent: "#94a3b8",
          bg: "#f8fafc",
          surface: "#ffffff",
          muted: "#cbd5e1"
        }
      },
      {
        name: "executive-navy",
        label: "Executive Navy",
        description: "Premium corporate navy with muted gold.",
        preview: {
          primary: "#0b1f3a",
          accent: "#c9a227",
          bg: "#f5f7fa",
          surface: "#ffffff",
          muted: "#94a3b8"
        }
      },
      {
        name: "modern-blue",
        label: "Modern Blue",
        description: "Clean, bright, and technology-focused.",
        preview: {
          primary: "#1d4ed8",
          accent: "#0ea5e9",
          bg: "#f8fafc",
          surface: "#ffffff",
          muted: "#bfdbfe"
        }
      },
      {
        name: "graphite-pro",
        label: "Graphite Pro",
        description: "Minimal, operational, and neutral.",
        preview: {
          primary: "#2f3437",
          accent: "#3b82f6",
          bg: "#f6f7f8",
          surface: "#ffffff",
          muted: "#d1d5db"
        }
      },
      {
        name: "emerald-business",
        label: "Emerald Business",
        description: "Calm, fresh, and reliable.",
        preview: {
          primary: "#047857",
          accent: "#14b8a6",
          bg: "#f7faf8",
          surface: "#ffffff",
          muted: "#a7f3d0"
        }
      },
      {
        name: "burgundy-formal",
        label: "Burgundy Formal",
        description: "Established, warm, and formal.",
        preview: {
          primary: "#7f1d1d",
          accent: "#c8a45d",
          bg: "#fbfaf7",
          surface: "#ffffff",
          muted: "#eadfd3"
        }
      }
    ];
    function getSavedTheme() {
      return localStorage.getItem(STORAGE_KEY) || DEFAULT_THEME;
    }
    function setDocumentTheme(themeName) {
      if (themeName === "classic") {
        document.documentElement.removeAttribute(ATTRIBUTE);
        return;
      }
      document.documentElement.setAttribute(ATTRIBUTE, themeName);
    }
    function saveTheme(themeName) {
      localStorage.setItem(STORAGE_KEY, themeName);
      setDocumentTheme(themeName);
    }
    function getTheme(themeName) {
      return THEMES.find((theme) => theme.name === themeName) || THEMES[0];
    }
    function buildPreview(theme, selectedTheme) {
      const isSelected = theme.name === selectedTheme;
      const preview = theme.preview;
      const card = $(`
            <button type="button" class="retail-brand-theme-card ${isSelected ? "selected" : ""}">
                <div class="retail-brand-preview">
                    <div class="retail-brand-preview-header">
                        <span class="retail-brand-preview-dot"></span>
                        <span class="retail-brand-preview-line"></span>
                    </div>
                    <div class="retail-brand-preview-body">
                        <div class="retail-brand-preview-nav"></div>
                        <div class="retail-brand-preview-panel"></div>
                    </div>
                    <span class="retail-brand-check">${frappe.utils.icon("tick", "xs")}</span>
                </div>
                <div class="retail-brand-theme-title"></div>
                <p class="retail-brand-theme-description"></p>
            </button>
        `);
      card.css({
        "--retail-preview-primary": preview.primary,
        "--retail-preview-accent": preview.accent,
        "--retail-preview-bg": preview.bg,
        "--retail-preview-surface": preview.surface,
        "--retail-preview-muted": preview.muted
      });
      card.find(".retail-brand-theme-title").text(theme.label);
      card.find(".retail-brand-theme-description").text(theme.description);
      card.attr("aria-pressed", isSelected ? "true" : "false");
      card.attr("title", theme.description);
      return card;
    }
    function showBrandThemeDialog() {
      const selectedTheme = getSavedTheme();
      const dialog = new frappe.ui.Dialog({
        title: __("Switch Brand Theme"),
        size: "large"
      });
      dialog.$wrapper.addClass("retail-brand-theme-dialog");
      const grid = $('<div class="retail-brand-theme-grid"></div>').appendTo(dialog.$body);
      THEMES.forEach((theme) => {
        const card = buildPreview(theme, selectedTheme);
        card.on("click", () => {
          grid.find(".retail-brand-theme-card").removeClass("selected").attr("aria-pressed", "false");
          card.addClass("selected").attr("aria-pressed", "true");
          saveTheme(theme.name);
          frappe.show_alert(__("Brand theme changed to {0}", [theme.label]), 3);
          dialog.hide();
        });
        grid.append(card);
      });
      dialog.show();
    }
    function addMenuItem() {
      const menu = $("#toolbar-user");
      if (!menu.length || menu.find('[data-retail-action="switch-brand-theme"]').length) {
        return Boolean(menu.length);
      }
      const item = $(`
            <button class="btn-reset dropdown-item" data-retail-action="switch-brand-theme">
                ${__("Switch Brand Theme")}
            </button>
        `);
      item.on("click", (event) => {
        event.preventDefault();
        showBrandThemeDialog();
      });
      const firstDivider = menu.find(".dropdown-divider").first();
      if (firstDivider.length) {
        item.insertBefore(firstDivider);
      } else {
        menu.append(item);
      }
      return true;
    }
    function addMenuItemWhenReady(attemptsLeft) {
      if (addMenuItem() || attemptsLeft <= 0) {
        return;
      }
      setTimeout(() => addMenuItemWhenReady(attemptsLeft - 1), 500);
    }
    setDocumentTheme(getSavedTheme());
    $(document).on("app_ready", () => {
      addMenuItemWhenReady(10);
      setDocumentTheme(getSavedTheme());
    });
    $(document).ready(() => {
      addMenuItemWhenReady(10);
    });
    window.retailBrandTheme = {
      themes: THEMES,
      get current() {
        return getTheme(getSavedTheme());
      },
      switchTo: saveTheme,
      show: showBrandThemeDialog
    };
  })();

  // ../retail/retail/public/js/reports/gross_profit_item_filter.js
  (function() {
    const REPORT_NAME = "Gross Profit";
    function add_item_filter(settings) {
      if (!settings || !Array.isArray(settings.filters))
        return;
      if (settings.filters.some((filter) => filter.fieldname === "item_code"))
        return;
      const salesInvoiceIndex = settings.filters.findIndex(
        (filter) => filter.fieldname === "sales_invoice"
      );
      const insertAt = salesInvoiceIndex >= 0 ? salesInvoiceIndex + 1 : settings.filters.length;
      settings.filters.splice(insertAt, 0, {
        fieldname: "item_code",
        label: __("Item Code"),
        fieldtype: "Link",
        options: "Item",
        get_query: function() {
          return {
            filters: {
              is_sales_item: 1,
              disabled: 0
            }
          };
        }
      });
    }
    function patch_query_report() {
      var _a, _b;
      const QueryReport = (_a = frappe == null ? void 0 : frappe.views) == null ? void 0 : _a.QueryReport;
      if (!((_b = QueryReport == null ? void 0 : QueryReport.prototype) == null ? void 0 : _b.get_report_settings))
        return false;
      if (QueryReport.prototype.__retail_gross_profit_item_filter)
        return true;
      const original = QueryReport.prototype.get_report_settings;
      QueryReport.prototype.get_report_settings = function() {
        return Promise.resolve(original.apply(this, arguments)).then((result) => {
          var _a2;
          if (this.report_name === REPORT_NAME) {
            add_item_filter(this.report_settings);
            add_item_filter((_a2 = frappe.query_reports) == null ? void 0 : _a2[REPORT_NAME]);
          }
          return result;
        });
      };
      QueryReport.prototype.__retail_gross_profit_item_filter = true;
      return true;
    }
    if (!patch_query_report()) {
      const timer = setInterval(() => {
        if (patch_query_report())
          clearInterval(timer);
      }, 100);
      setTimeout(() => clearInterval(timer), 1e4);
    }
  })();

  // ../retail/retail/public/js/reports/pos_report_filters.js
  window.get_pos_report_filters = function get_pos_report_filters(options = {}) {
    const filters = [
      {
        fieldname: "from_date",
        label: __("From Date"),
        fieldtype: "Date",
        default: frappe.datetime.get_today(),
        reqd: 1
      },
      {
        fieldname: "to_date",
        label: __("To Date"),
        fieldtype: "Date",
        default: frappe.datetime.get_today(),
        reqd: 1
      },
      {
        fieldname: "company",
        label: __("Company"),
        fieldtype: "Link",
        options: "Company",
        default: frappe.defaults.get_user_default("Company")
      },
      { fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch" },
      {
        fieldname: "counter",
        label: __("Counter"),
        fieldtype: "Link",
        options: "POS Branch Counter",
        get_query: function() {
          const branch = frappe.query_report.get_filter_value("branch");
          return branch ? { filters: { branch } } : {};
        }
      },
      { fieldname: "pos_profile", label: __("POS Profile"), fieldtype: "Link", options: "POS Profile" }
    ];
    if (options.include_cashier) {
      filters.push(
        {
          fieldname: "cashier_employee",
          label: __("Cashier Employee"),
          fieldtype: "Link",
          options: "Employee"
        },
        { fieldname: "cashier", label: __("Cashier User"), fieldtype: "Link", options: "User" }
      );
    }
    if (options.include_customer) {
      filters.push({ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" });
    }
    if (options.include_item_filters) {
      filters.push(
        { fieldname: "item_code", label: __("Item"), fieldtype: "Link", options: "Item" },
        { fieldname: "item_group", label: __("Item Group"), fieldtype: "Link", options: "Item Group" },
        { fieldname: "warehouse", label: __("Warehouse"), fieldtype: "Link", options: "Warehouse" }
      );
    } else if (options.include_item_group) {
      filters.push({ fieldname: "item_group", label: __("Item Group"), fieldtype: "Link", options: "Item Group" });
    }
    if (options.include_shift) {
      filters.push({ fieldname: "shift", label: __("Shift"), fieldtype: "Link", options: "POS Cashier Shift" });
    }
    if (options.include_payment_mode) {
      filters.push({
        fieldname: "payment_mode",
        label: __("Mode of Payment"),
        fieldtype: "Link",
        options: "Mode of Payment"
      });
    }
    if (options.include_status) {
      filters.push({
        fieldname: "status",
        label: __("Status"),
        fieldtype: "Select",
        options: "\nPaid\nConsolidated\nReturn\nCancelled"
      });
    }
    if (options.include_movement_type) {
      filters.push({
        fieldname: "movement_type",
        label: __("Movement Type"),
        fieldtype: "Select",
        options: "\nCash In\nCash Out"
      });
    }
    return filters;
  };

  // ../retail/retail/public/js/reports/profitability.js
  window.retail_profitability_formatter = function(value, row, column, data, default_formatter) {
    const amounts = ["gross_sales", "discount", "sales_returns", "net_sales", "vat", "cost_amount", "gross_profit", "profit_percent"];
    if (data && amounts.includes(column.fieldname) && data[column.fieldname] == null) {
      return column.fieldname === "profit_percent" ? __("N/A") : "\u2014";
    }
    const formatted = default_formatter(value, row, column, data);
    return data && data.is_total_row ? `<strong>${formatted}</strong>` : formatted;
  };

  // ../retail/retail/public/js/reports/outstanding_footer.js
  (() => {
    const labels = {
      "Accounts Payable": "Total Payable: {0}",
      "Accounts Receivable": "Total Receivable: {0}"
    };
    const selector = ".retail-outstanding-footer";
    const clear = () => $(selector).remove();
    frappe.router.on("change", clear);
    const prototype = frappe.views.QueryReport.prototype;
    if (prototype.__retail_outstanding_footer)
      return;
    prototype.__retail_outstanding_footer = true;
    const refresh = prototype.refresh;
    prototype.refresh = function() {
      clear();
      const report_name = this.report_name;
      const result = refresh.apply(this, arguments);
      if (!labels[report_name])
        return result;
      return result.then((value) => {
        var _a, _b;
        const route = frappe.get_route();
        if (route[0] !== "query-report" || route[1] !== report_name)
          return value;
        if (this.report_name !== report_name)
          return value;
        let rows = this.data || [];
        if (((_a = this.raw_data) == null ? void 0 : _a.add_total_row) && rows.length)
          rows = rows.slice(0, -1);
        rows = rows.filter((row) => !row.is_total_row && !(row.bold && !row.voucher_no));
        const total = rows.reduce(
          (sum, row) => {
            var _a2;
            return sum + flt((_a2 = row.outstanding_amount) != null ? _a2 : row.outstanding);
          },
          0
        );
        const currency = ((_b = rows.find((row) => row.currency)) == null ? void 0 : _b.currency) || erpnext.get_currency(this.get_filter_value("company"));
        clear();
        $("<div>", { class: "retail-outstanding-footer", "aria-hidden": "true" }).css("height", "68px").appendTo(this.page.main);
        $("<div>", { class: "retail-outstanding-footer", role: "status" }).text(__(labels[report_name], [format_currency(total, currency)])).css({
          position: "fixed",
          bottom: 0,
          left: 0,
          right: 0,
          zIndex: 100,
          padding: "16px 24px",
          textAlign: "right",
          fontSize: "20px",
          lineHeight: "28px",
          fontWeight: 800,
          background: "var(--card-bg)",
          borderTop: "1px solid var(--border-color)"
        }).appendTo(document.body);
        return value;
      });
    };
  })();
})();
//# sourceMappingURL=retail_desk.bundle.NML2FPSC.js.map
