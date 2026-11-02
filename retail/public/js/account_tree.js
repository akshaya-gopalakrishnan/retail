/* Retail additions to the native Chart of Accounts. */
(() => {
	const settings = frappe.treeview_settings.Account;
	const original_onload = settings.onload;
	const original_post_render = settings.post_render;

	if (!document.getElementById("retail-account-tree-style")) {
		$("<style>", { id: "retail-account-tree-style" }).text(`
			.retail-account-tree .tree-node:has(> .tree-link.selected) {
				background: linear-gradient(var(--retail-account-selection), var(--retail-account-selection)) no-repeat;
				background-size: 100% 34px;
				border-radius: 5px;
			}
			.retail-account-tree {
				--retail-account-selection: #d4e2f0;
				--retail-account-hover: #e0e7ef;
			}
			[data-theme="dark"] .retail-account-tree {
				--retail-account-selection: #344c65;
				--retail-account-hover: #303e4e;
			}
			.retail-account-tree .tree-node.hover-active {
				background: linear-gradient(var(--retail-account-hover), var(--retail-account-hover)) no-repeat;
				background-size: 100% 34px;
				border-radius: 5px;
			}
			.retail-account-tree .tree-node.hover-active:has(> .tree-link.selected) {
				background-image: linear-gradient(var(--retail-account-selection), var(--retail-account-selection));
			}
			.retail-account-tree .tree-link.selected {
				background-color: var(--retail-account-selection) !important;
				box-shadow: inset 3px 0 var(--primary);
				border-radius: 4px;
			}
		`).appendTo(document.head);
	}

	settings.onload = function (view) {
		original_onload?.call(this, view);
		const search = view.page.add_field({
			fieldname: "retail_account_search",
			fieldtype: "Link",
			options: "Account",
			label: __("Search Ledger"),
			placeholder: __("Search Ledger"),
			get_query: () => ({ filters: { company: view.page.fields_dict.company.get_value() } }),
			change: async () => {
				const name = search.get_value();
				if (!name) return;
				const tree = view.tree;
				const company = view.page.fields_dict.company.get_value();
				const current = () => view.tree === tree && search.get_value() === name &&
					view.page.fields_dict.company.get_value() === company;
				try {
					const path = [];
					const seen = new Set();
					let account = name;
					while (account && !seen.has(account)) {
						seen.add(account);
						const { message } = await frappe.db.get_value("Account", account, ["parent_account", "company"]);
						if (!current()) return;
						if (!message || message.company !== company) return;
						path.unshift(account);
						account = message.parent_account;
					}
					if (!tree.root_node.loaded) await tree.load_children(tree.root_node);
					for (const value of path) {
						if (!current()) return;
						const node = tree.nodes[value];
						if (!node) {
							frappe.msgprint(__("Account could not be found in this company tree. Please refresh and try again."));
							return;
						}
						if (value === name) {
							tree.on_node_click(node);
							node.$tree_link[0].scrollIntoView({ block: "center", behavior: "smooth" });
						} else if (!node.loaded) {
							await tree.load_children(node);
						} else if (!node.expanded) {
							tree.expand_node(node, false);
						}
					}
				} catch (error) {
					if (current()) frappe.msgprint(__("Unable to locate this account. Please try again."));
					console.error("Retail account tree search", error);
				}
			},
		});
		search.$input.attr("aria-label", __("Search Ledger"));
	};

	settings.post_render = function (view) {
		original_post_render?.call(this, view);
		view.tree.wrapper.addClass("retail-account-tree");
		const search = view.page.fields_dict.retail_account_search;
		if (search?.get_value()) search.set_value("");
	};
})();
