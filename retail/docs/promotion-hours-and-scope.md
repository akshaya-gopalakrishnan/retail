# Promotion schedules and Promo Price scope

Promo Price, Buy X Get Y Promotion, and Gift Voucher Promotion have separate
Active From Date, Active To Date, Active From Time, and Active To Time fields.
All boundaries are optional and inclusive, using the site's local timezone.

- Dates only: leave both times blank for all-day validity.
- Hours only: leave both dates blank for a recurring daily promotion.
- Dates and hours: the daily hours apply on each date in the date range.
- An earlier end time means an overnight window, e.g. 22:00–02:00.
- A blank start or end means no restriction on that side. Blank dates and times
  mean unrestricted validity, subject to the existing enable/disable flag.

Invoice eligibility uses posting date and posting time. If posting time is
missing, Retail's direct eligibility checks use the current site-local time.
Generated pricing-rule hour conditions require a document with posting_time;
transactions without that field cannot qualify for a timed generated rule.
Existing date-only promotions keep their previous behavior.

Promo Price's **Apply Promotion To** options are ITEM, CATEGORY, BRAND, and
WHOLE BILL. Only the selected target field is editable and visible. Switching
scope clears the old target and item-specific price snapshots. The server
rejects incompatible hidden targets as well.

CATEGORY includes descendant Item Groups. BRAND matches the Item's Brand.
WHOLE BILL uses one promotion row and applies its price or percentage discount
to every eligible bill item, retaining existing quantity, sales value,
warehouse, price list, and free-goods rules. It is not an additional invoice
header discount. All scopes support fixed prices and percentage discounts;
Discount Amount requires an individual Item's selling-price snapshot.

## Offline POS integration

Retail's promotion APIs export `active_from`, `active_to`, `active_from_time`,
`active_to_time` and, for Promo Price, `promotion_scope` plus each row's `brand`.
The full Promo Price/Buy X Get Y snapshot now includes promotions with blank end
dates and disabled/expired records. Terminals must replace their full snapshot
or process the enable/disable flags and validity boundaries. Incremental sync
still filters by `modified_after`.

The external POS client must implement the same daily/overnight time logic,
Brand targeting, and Whole Bill targeting before these features affect offline
bills. Retail does not rewrite completed offline sale amounts or previously
issued vouchers during synchronization.

## Buy X Get Y scope

Buy X Get Y also offers ITEM, CATEGORY and BRAND for Buy Item rows, using the
same exclusive selection and hidden-field validation as Promo Price. Free Item
rows always require a specific Item. Same Product Only continues to give the
qualifying purchased Item. The existing buy/free quantity calculation is unchanged.
Both the standalone API and master-data `buy_x_get_y_promotions` return
`promotion_scope` and product `brand`.
