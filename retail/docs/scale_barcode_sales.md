# Selling scale-labelled items

In Item, check **Scale Item**, select **Scale Barcode Type**, and use a unique
7-digit numeric master barcode with any prefix. Automatic generation still uses
`99` followed by the lowest available five-digit number. Scanning the master barcode sells
normally. An exact saved barcode always takes priority over label decoding.
Only enabled sales items with Scale Item checked are decoded.

| Item scale type | Label fields | Total digits |
| --- | --- | --- |
| Weight | Master 7 + weight 5 + check 1 | 13 |
| Quantity | Master 7 + quantity 5 + check 1 | 13 |
| Price | Master 7 + total price 5 + check 1 | 13 |
| Weight+UPrice | Master 7 + weight 5 + unit price 5 + check 1 | 18 |
| Weight+TotPrice | Master 7 + weight 5 + total price 5 + check 1 | 18 |

Weights are grams: `00500` is 0.500 when selling in Kg, or 500 when selling in
Gram. Quantity is a whole number. Prices always contain two implied decimals:
`03050` means 30.50; maximum `99999` means 999.99.
The scale must print these same lengths. Six-digit price labels are
rejected. The last digit must be numeric and is excluded; its checksum is not
validated because the scale checksum algorithm has not been specified.

Weight and Quantity use the transaction's selling rate. Price derives quantity
from its total and the selling rate; if that rate is zero, quantity is 1 and rate
is the encoded total. Weight+UPrice uses the encoded rate. Weight+TotPrice derives
rate from its total and weight. Weight/Quantity with no selling rate prompt the
cashier for a positive rate. Zero weight/quantity and malformed labels are rejected.

Supported in the standard scan field on Sales Invoice, Sales Order, Delivery Note,
Quotation and POS Invoice forms, and in the Sales Invoice row barcode scan field.
Each label scan adds a separate row. Item/UOM lookup and taxes use the existing
transaction flow. Encoded unit prices and totals include VAT. The scale handler uses the existing
transaction Item VAT lookup to convert them to an exclusive rate; normal VAT
calculation supplies the tax and inclusive display values. Weight/Quantity labels
without encoded prices keep the normal selling-rate behavior.
Existing row discounts are reset when applying a label. Retail fixed-price
promotions do not replace a label's encoded price on save; later explicit changes
and bill discounts follow normal ERP behavior.

Document-local calculation precision retains scale-derived quantity/rate values.
No global precision setting is changed. Submitted records are not decoded or
repriced. The existing `retail.api.scale_item_api.parse_barcode` endpoint also
supports this layout. The external .NET client must implement the five-digit price
layout itself; this app change does not replace the .NET scanner or POS screen.
