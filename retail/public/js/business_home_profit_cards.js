// Share the initial page snapshot, including widgets whose definitions load late.
// Refresh and route entry discard it; failed requests are never retained.
(() => {
	const prefix = "retail.retail_app.retail_dashboard.";
	const cards = {
		"Today's Sales": ["get_today_sales", "sales", false],
		"Today's Profit": ["get_profit_number_card", "profit", false],
		"Invoice Count Today": ["get_invoice_count_today", "count", true],
		"Return Amount Today": ["get_return_amount_today", "returns", true],
	};
    const workspace_methods = new Set([
        prefix + "get_damage_amount_today", prefix + "get_cash_in_hand_today",
        "retail.retail_app.report.low_stock_reorder_report.low_stock_reorder_report.get_low_stock_items_count",
        "retail.retail_app.report.low_stock_reorder_report.low_stock_reorder_report.get_out_of_stock_items_count",
    ]);
	let pending = new Map();
	let queue = [];
	let scheduled = false;
	function request_context(context) {
		return new Promise((resolve, reject) => {
			queue.push({ context, resolve, reject });
			if (scheduled) return;
			scheduled = true;
			setTimeout(async () => {
				const batch = queue;
				queue = [];
				scheduled = false;
				try {
					const results = await frappe.xcall(prefix + "get_business_home_profit_cards", {
						contexts: batch.map((entry) => entry.context),
					});
					batch.forEach((entry, index) => entry.resolve(results[index]));
				} catch (error) {
					batch.forEach((entry) => entry.reject(error));
				}
			}, 0);
		});
	}
	frappe.router?.on("change", () => { pending = new Map(); });

	function install() {
		const factory = frappe.widget?.widget_factory;
		if (!factory?.number_card || factory.number_card.retail_shared_profit) return;
		const Base = factory.number_card;
		class BusinessHomeNumberCard extends Base {
			get_number_for_custom_card(res) {
				const result = super.get_number_for_custom_card(res);
				if (this.card_doc?.name === "Today's Sales" &&
					this.card_doc.method === prefix + "get_today_sales") {
					const value = typeof res === "object" ? res?.value : res;
					if (typeof value === "number" && Number.isFinite(value)) {
						this.formatted_number = value.toFixed(2);
					}
				}
				return result;
			}

            get_number_for_doctype_card(res) {
                const field = this.card_doc?.aggregate_function_based_on;
                const types = {"Bin.stock_value": "Currency"};
                const fieldtype = types[`${this.card_doc?.document_type}.${field}`];
                if (retail.workspace_speed.active() && this.card_doc.function === "Sum" && fieldtype) {
                    this.number = res;
                    return this.set_formatted_number({fieldtype});
                }
                return super.get_number_for_doctype_card(res);
            }

			async get_data() {
				const card = cards[this.card_doc?.name];
				if (!retail.workspace_speed.active()) return super.get_data();
                const legacy_card = card && this.card_doc.type === "Custom" &&
                    this.settings.method === prefix + card[0];
                const workspace_card = (this.card_doc.type === "Document Type" &&
                    this.settings.method === "frappe.desk.doctype.number_card.number_card.get_result") ||
                    (this.card_doc.type === "Custom" && workspace_methods.has(this.settings.method));
                if (!legacy_card && !workspace_card) return super.get_data();
				const args = this.settings.args || {};
				// These APIs ignore nested `filters`. Preserve their actual top-level
				// arguments; Count/Returns intentionally ignore dates/branch/counter.
				const context = legacy_card ? {
					company: args.company || null,
					today_only: card[2],
					from_date: (!card[2] && args.from_date) || null,
					to_date: (!card[2] && args.to_date) || null,
					branch: (!card[2] && args.branch) || null,
					counter: (!card[2] && args.counter) || null,
                } : {card_name: this.card_doc.name, filters: args.filters || []};
				const key = JSON.stringify({ ...context, today_only: undefined });
				// A second get_data on a widget is a refresh, not initial hydration.
				if (this.retail_profit_loaded) pending = new Map();
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
				this.data = result[legacy_card ? card[1] : "value"];
				return this.settings.get_number(this.data);
			}
		}
		BusinessHomeNumberCard.retail_shared_profit = true;
		factory.number_card = BusinessHomeNumberCard;
	}
	install();
	$(document).on("startup", install);
})();
