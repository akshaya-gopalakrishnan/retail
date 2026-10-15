# List columns

Retail extends standard desktop List Views while retaining native list settings.

To add columns, open the list menu, choose **List Settings**, increase
**Maximum Number of Fields** (up to 50), then use **Add / Remove Fields** and save
both dialogs. This native configuration is shared for that DocType and requires
the existing List View Settings permissions. It does not automatically add fields
or change existing lists when Retail installs the customization.

Use the **⋮⋮** header grip to swap two columns. Drag the line on a header's right
edge to resize it. Widths and visual order are saved separately for each site,
user and DocType in that browser. A wide list scrolls horizontally. The list menu
contains **Reset Column Widths** and **Reset Column Order**; double-clicking a
resize line resets only that column's width. Both controls support arrow keys.

Mobile layouts retain native column behavior. Report, Kanban and Image views are
excluded from these desktop controls.

The extended count choices are installed after sync and migration by
`retail.list_view_columns.install`, using a Property Setter on
`List View Settings.total_fields.options`. Frappe and ERPNext source is unchanged.
Retail fetches fresh List View Settings metadata before opening the native dialog,
so a browser-cached 4-10 dropdown cannot hide newly installed count choices.
