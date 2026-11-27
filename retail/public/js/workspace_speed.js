// Shared scope for Retail workspace optimizations. Forms/lists keep native loaders.
frappe.provide("retail.workspace_speed");
retail.workspace_speed.names = new Set([
 "Business Home", "Items", "Sales", "Purchases", "Stocks", "Accounts", "POS",
 "Reports", "Promotions", "Settings",
]);
retail.workspace_speed.active = function () {
 const route = frappe.get_route() || [];
 return route[0] === "Workspaces" && retail.workspace_speed.names.has(route[1]);
};
