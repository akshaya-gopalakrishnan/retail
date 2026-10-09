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
			async get_data() {
				const route = frappe.get_route();
				const card = cards[this.card_doc?.name];
				if (route[0] !== "Workspaces" || route[1] !== "Business Home" ||
					!card || this.card_doc.type !== "Custom" ||
					this.settings.method !== prefix + card[0]) return super.get_data();
				const args = this.settings.args || {};
				// These APIs ignore nested `filters`. Preserve their actual top-level
				// arguments; Count/Returns intentionally ignore dates/branch/counter.
				const context = {
					company: args.company || null,
					today_only: card[2],
					from_date: (!card[2] && args.from_date) || null,
					to_date: (!card[2] && args.to_date) || null,
					branch: (!card[2] && args.branch) || null,
					counter: (!card[2] && args.counter) || null,
				};
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
