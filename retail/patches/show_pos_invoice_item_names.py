"""Show Item Name after Item Code while retaining saved POS column preferences."""

from retail.patches.repair_purchase_grid_defaults import apply_layouts


def execute():
	apply_layouts(("POS Invoice",))
