/* Shared display contract: unknown amounts stay unknown; return margins are N/A. */
window.retail_profitability_formatter = function (value, row, column, data, default_formatter) {
    const amounts = ["gross_sales", "discount", "sales_returns", "net_sales", "vat", "cost_amount", "gross_profit", "profit_percent"];
    if (data && amounts.includes(column.fieldname) && data[column.fieldname] == null) {
        return column.fieldname === "profit_percent" ? __("N/A") : "—";
    }
    const formatted = default_formatter(value, row, column, data);
    return data && data.is_total_row ? `<strong>${formatted}</strong>` : formatted;
};
