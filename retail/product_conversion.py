"""Product Conversion: a reviewable document backed by one native Repack entry."""
import json
from collections import defaultdict
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import cint, flt, nowtime

from retail.repack import GROUP, _check_warehouse, _positive


def default_warehouses(company):
    abbreviation = frappe.get_cached_value('Company', company, 'abbr')
    name = f'Stores - {abbreviation}'
    return name if frappe.db.exists('Warehouse', {'name': name, 'company': company, 'is_group': 0, 'disabled': 0}) else None


@frappe.whitelist()
def get_defaults(company):
    frappe.has_permission('Product Conversion', 'create', throw=True)
    frappe.get_doc('Company', company).check_permission('read')
    values = frappe.get_cached_value('Company', company,
        ['default_currency', 'expenses_included_in_valuation', 'cost_center'], as_dict=True)
    return dict(source_warehouse=default_warehouses(company), target_warehouse=default_warehouses(company),
                currency=values.default_currency, labour_account=values.expenses_included_in_valuation,
                packing_account=values.expenses_included_in_valuation, cost_center=values.cost_center)


def stock_item(code):
    item = frappe.get_cached_doc('Item', code)
    item.check_permission('read')
    if not item.is_stock_item or item.disabled or item.has_variants:
        frappe.throw(_('Select an enabled stock item, not an item template.'))
    return item


def barcode(item):
    return next((r.barcode for r in item.get('barcodes') or [] if r.barcode), '')


@frappe.whitelist()
def get_stock_details(item_code, warehouse, company):
    frappe.has_permission('Product Conversion', 'read', throw=True)
    item = stock_item(item_code)
    _check_warehouse(warehouse, company)
    details = frappe.db.get_value('Bin', {'item_code': item_code, 'warehouse': warehouse},
                                  ['actual_qty', 'valuation_rate'], as_dict=True) or frappe._dict()
    return dict(current_stock=flt(details.actual_qty), stock_cost=flt(details.valuation_rate),
                stock_uom=item.stock_uom, item_name=item.item_name)


def normalize(doc):
    """Canonical stock-unit quantities and costs; never trust browser totals."""
    if not doc.company:
        frappe.throw(_('Select Company first.'))
    doc.currency = frappe.get_cached_value('Company', doc.company, 'default_currency')
    defaults = default_warehouses(doc.company)
    doc.source_warehouse = doc.source_warehouse or defaults
    doc.target_warehouse = doc.target_warehouse or defaults
    _check_warehouse(doc.source_warehouse, doc.company)
    _check_warehouse(doc.target_warehouse, doc.company)
    doc.posting_time = doc.posting_time or nowtime()
    # Desk may include its initial empty grid row in an unsaved document.
    for field in ('items', 'materials'):
        doc.set(field, [r for r in doc.get(field) or [] if r.item_code or (field == 'items' and r.get('main_item'))])
        for index, row in enumerate(doc.get(field), 1):
            row.idx = index
    products = {}
    for row in doc.items:
        row.row_key = row.row_key or frappe.generate_hash(length=12)
        if row.row_key in products:
            frappe.throw(_('Duplicate conversion product row.'))
        _positive(row.qty, _('Quantity to Generate'))
        _positive(row.labour_cost, _('Labour Cost'), allow_zero=True)
        _positive(row.packing_cost, _('Packing Cost'), allow_zero=True)
        row.labour_cost = flt(row.labour_cost, 2)
        row.packing_cost = flt(row.packing_cost, 2)
        item = stock_item(row.item_code)
        row.item_name, row.stock_uom, row.barcode = item.item_name, item.stock_uom, barcode(item)
        row.product_cost = 0
        products[row.row_key] = row
    if not products:
        frappe.throw(_('Add at least one product using From BOM or From Main Item.'))
    sync_main_materials(doc)
    # Match the generated Stock Entry's product order, including after row
    # reordering or replacing one product's consumption in the detail dialog.
    doc.materials.sort(key=lambda r: products[r.row_key].idx if r.row_key in products else len(products) + 1)
    for index, material in enumerate(doc.materials, 1):
        material.idx = index
    required = defaultdict(float)
    counts = defaultdict(int)
    consumed = {}
    for material in doc.materials:
        product = products.get(material.row_key)
        if not product:
            frappe.throw(_('Every consumption item must belong to a product row.'))
        if material.item_code in {r.item_code for r in doc.items}:
            frappe.throw(_('An output item cannot also be consumed in this conversion. Use sequential conversions.'))
        _positive(material.qty_per_unit, _('Consumption per Finished Unit'))
        item = stock_item(material.item_code)
        material.conversion_row = product.idx
        material.item_name, material.stock_uom, material.barcode = item.item_name, item.stock_uom, barcode(item)
        material.qty = flt(flt(material.qty_per_unit) * flt(product.qty), material.precision('qty'))
        _positive(material.qty, _('Quantity to Consume'))
        material.warehouse = material.warehouse or doc.source_warehouse
        _check_warehouse(material.warehouse, doc.company)
        details = get_stock_details(material.item_code, material.warehouse, doc.company)
        material.current_stock, material.stock_cost = details['current_stock'], details['stock_cost']
        from erpnext.stock.utils import get_incoming_rate
        key = (material.item_code, material.warehouse, material.batch_no or '')
        previous_qty, previous_value = consumed.get(key, (0.0, 0.0)) if not material.serial_no else (0.0, 0.0)
        cumulative_qty = previous_qty + material.qty
        rate = flt(get_incoming_rate(frappe._dict(
            item_code=material.item_code, warehouse=material.warehouse,
            posting_date=doc.posting_date, posting_time=doc.posting_time,
            qty=-cumulative_qty, company=doc.company, voucher_type='Stock Entry',
            batch_no=material.batch_no, serial_no=material.serial_no, allow_zero_valuation=1,
        ), raise_error_if_no_rate=False))
        cumulative_value = cumulative_qty * rate
        material.unit_cost = (cumulative_value - previous_value) / material.qty
        material.amount = flt(cumulative_value - previous_value, material.precision('amount'))
        if not material.serial_no:
            consumed[key] = (cumulative_qty, cumulative_value)
        product.product_cost += material.amount
        required[(material.item_code, material.warehouse)] += material.qty
        counts[product.row_key] += 1
        if material.item_code == product.main_item:
            product.main_stock_qty = material.current_stock
            product.main_unit_cost = material.stock_cost
            product.main_stock_uom = material.stock_uom
    for product in doc.items:
        if not counts[product.row_key]:
            frappe.throw(_('Product row {0} needs at least one consumption item.').format(product.idx))
        product.total_cost = flt(product.product_cost + product.labour_cost + product.packing_cost, 2)
        product.unit_cost = product.total_cost / flt(product.qty)
    for field in ('product_cost', 'labour_cost', 'packing_cost', 'total_cost'):
        doc.set(field, sum(flt(r.get(field)) for r in doc.items))
    return required


def sync_main_materials(doc):
    """Direct grid entries and BOM-loaded entries share the same posting data."""
    for product in doc.items:
        related = [r for r in doc.materials if r.row_key == product.row_key]
        if product.source_type == 'BOM':
            product.main_qty_per_unit = sum(flt(r.qty_per_unit) for r in related if r.item_code == product.main_item)
        else:
            product.source_type = 'Main Item'
            if not product.main_item:
                frappe.throw(_('Row {0}: select the Main Item.').format(product.idx))
            main = [r for r in related if r.get('is_main_item') or r.item_code == product.main_item]
            for row in main:
                _positive(row.qty_per_unit, _('Consumption per Finished Unit'))
            existing = sum(flt(r.qty_per_unit) for r in main)
            raw = product.get('main_qty_per_unit')
            legacy = main and not any(r.get('is_main_item') for r in main)
            derive = raw in (None, '') or (not flt(raw) and (legacy or (not main and flt(product.get('main_qty')))))
            desired = (flt(product.get('main_qty')) / flt(product.qty) if flt(product.get('main_qty')) else existing) if derive else flt(raw)
            _positive(desired, _('Row {0}: main quantity per finished unit').format(product.idx))
            if not main:
                main = [doc.append('materials', dict(row_key=product.row_key, item_code=product.main_item,
                    qty_per_unit=desired, warehouse=doc.source_warehouse, is_main_item=1))]
                existing = desired
            for row in main:
                if row.item_code != product.main_item:
                    row.item_code = product.main_item
                    row.batch_no = None
                    row.serial_no = None
                row.is_main_item = 1
                row.qty_per_unit = flt(row.qty_per_unit) * desired / existing
            product.main_qty_per_unit = desired
        product.main_qty = flt(product.main_qty_per_unit) * flt(product.qty)


def check_extra_accounts(doc):
    for field, cost in (('labour_account', doc.labour_cost), ('packing_account', doc.packing_cost)):
        if not flt(cost):
            continue
        account_name = doc.get(field)
        account = frappe.get_doc('Account', account_name) if account_name else None
        if not account or account.company != doc.company or account.is_group or account.disabled or account.root_type != 'Expense' or account.account_currency != doc.currency:
            frappe.throw(_('Select a valid {0} under Expenses in the company currency.').format(doc.meta.get_label(field)))
        account.check_permission('read')


def build_stock_entry(doc):
    """Use the existing Retail group allocator and native stock row builder."""
    entry = frappe.new_doc('Stock Entry')
    entry.update(dict(company=doc.company, purpose='Repack', stock_entry_type='Repack',
                      posting_date=doc.posting_date, posting_time=doc.posting_time, set_posting_time=1,
                      cost_center=doc.cost_center, custom_product_conversion=doc.name,
                      remarks=_('Product Conversion {0}').format(doc.name)))
    configs = []
    for product in doc.items:
        configs.append(dict(idx=product.idx, finished_item=product.item_code, qty=product.qty,
                            bom_no=product.bom_no or None))
        for material in (r for r in doc.materials if r.row_key == product.row_key):
            add_stock_row(entry, material.item_code, material.qty, material.warehouse, None,
                          product, material.batch_no, material.serial_no)
        add_stock_row(entry, product.item_code, product.qty, None, doc.target_warehouse,
                      product, product.batch_no, product.serial_no)
        for field, account in (('labour_cost', doc.labour_account), ('packing_cost', doc.packing_account)):
            if flt(product.get(field)):
                entry.append('additional_costs', dict(expense_account=account, account_currency=doc.currency,
                    exchange_rate=1, amount=product.get(field), base_amount=product.get(field),
                    description=_('{0}: {1} (row {2})').format(_('Labour') if field == 'labour_cost' else _('Packing'), product.item_code, product.idx),
                    **{GROUP: product.idx}))
    entry.custom_conversion_groups = json.dumps(configs)
    return entry


def add_stock_row(entry, code, qty, source, target, product, batch_no, serial_no):
    from erpnext.stock.doctype.item.item import get_item_defaults
    item = get_item_defaults(code, entry.company)
    entry.add_to_stock_entry_detail({code: dict(
        item_code=code, qty=qty, stock_uom=item.stock_uom, uom=item.stock_uom,
        conversion_factor=1, from_warehouse=source or '', to_warehouse=target or '',
        item_name=item.item_name, description=item.description,
        expense_account=item.get('expense_account'), cost_center=entry.cost_center or item.get('buying_cost_center'),
        is_finished_item=int(bool(target)), batch_no=batch_no, serial_no=serial_no,
        use_serial_batch_fields=1,
    )}, bom_no=product.bom_no or None)
    row = entry.items[-1]
    row.set(GROUP, product.idx)
    row.set_basic_rate_manually = int(bool(target))
    row.use_serial_batch_fields = 1


def validate_stock_entry(entry):
    if entry.purpose != 'Repack' or entry.get('custom_multiple_boms'):
        frappe.throw(_('Product Conversion must use its own Repack flow.'))
    if frappe.flags.get('product_conversion_posting') != entry.custom_product_conversion:
        frappe.throw(_('Post or change this Stock Entry through its Product Conversion document.'))


def guard_stock_entry_cancel(entry, method=None):
    if entry.get('custom_product_conversion') and frappe.flags.get('product_conversion_posting') != entry.custom_product_conversion:
        frappe.throw(_('Cancel the Product Conversion document to cancel this Stock Entry.'))


def finalize_stock_entry(entry, method=None):
    if entry.get('custom_product_conversion'):
        # The shared FOC display handler computes amount from a sales rate,
        # which Stock Entry rows do not have. Restore native stock amounts
        # after that hook, without changing its behavior for other documents.
        entry.update_valuation_rate()
        entry.set_total_incoming_outgoing_value()


def allow_own_conversion_backlink(entry, method=None):
    # Core resets its ignore list in on_cancel; extend it after core runs.
    if entry.get('custom_product_conversion') and frappe.flags.get('product_conversion_posting') == entry.custom_product_conversion:
        entry.ignore_linked_doctypes = (*entry.get('ignore_linked_doctypes', ()), 'Product Conversion')


def apply_actual_costs(doc, entry):
    """Read final voucher costs after native ledger posting, never Item prices."""
    for product in doc.items:
        inputs = [r for r in entry.items if cint(r.get(GROUP)) == product.idx and r.s_warehouse]
        outputs = [r for r in entry.items if cint(r.get(GROUP)) == product.idx and r.t_warehouse]
        product.product_cost = sum(flt(r.basic_amount) for r in inputs)
        product.total_cost = sum(flt(r.amount) for r in outputs)
        product.unit_cost = product.total_cost / flt(product.qty)
        for material, stock_row in zip([r for r in doc.materials if r.row_key == product.row_key], inputs):
            material.unit_cost = stock_row.basic_rate
            material.amount = stock_row.basic_amount
    for field in ('product_cost', 'labour_cost', 'packing_cost', 'total_cost'):
        doc.set(field, sum(flt(r.get(field)) for r in doc.items))


def apply_ledger_source_rates(entry):
    # During initial FIFO posting core may defer refreshing the saved outgoing
    # row rates. Incoming group valuation must use the already-posted source
    # SLE values, not each row's independent pre-posting estimate.
    values = frappe.db.sql('''select voucher_detail_no, sum(actual_qty) as qty,
        sum(stock_value_difference) as amount from `tabStock Ledger Entry`
        where voucher_type='Stock Entry' and voucher_no=%s and is_cancelled=0
        and actual_qty < 0 group by voucher_detail_no''', entry.name, as_dict=True)
    by_row = {r.voucher_detail_no: r for r in values}
    for row in entry.items:
        ledger = by_row.get(row.name)
        if row.s_warehouse and ledger and flt(ledger.qty):
            row.basic_rate = abs(flt(ledger.amount) / flt(ledger.qty))


def apply_sequential_source_rates(entry, raise_error_if_no_rate=True):
    from erpnext.stock.utils import get_incoming_rate
    consumed = {}
    for row in entry.items:
        if not row.s_warehouse:
            continue
        # Explicit serial/batch bundles already identify their own allocations.
        if row.serial_and_batch_bundle or row.serial_no:
            continue
        key = (row.item_code, row.s_warehouse, row.batch_no or '')
        qty, value = consumed.get(key, (0.0, 0.0))
        cumulative = qty + flt(row.transfer_qty)
        if qty:
            args = entry.get_args_for_incoming_rate(row)
            args.qty = -cumulative
            rate = flt(get_incoming_rate(args, raise_error_if_no_rate))
            row.basic_rate = (cumulative * rate - value) / flt(row.transfer_qty)
            row.basic_amount = flt(row.basic_rate * flt(row.transfer_qty), row.precision('basic_amount'))
        consumed[key] = (cumulative, value + flt(row.basic_rate) * flt(row.transfer_qty))


def update_master_costs(doc):
    totals = defaultdict(lambda: [0.0, 0.0])
    for product in doc.items:
        if product.update_item_master:
            totals[product.item_code][0] += product.total_cost
            totals[product.item_code][1] += product.qty
    audit = []
    for code, (amount, qty) in sorted(totals.items()):
        item = frappe.get_doc('Item', code, for_update=True)
        item.check_permission('write')
        net = amount / qty
        from retail.domains.item.vat_pricing import get_item_tax_rate
        tax = get_item_tax_rate(item.custom_purchase_tax_template) if item.get('custom_purchase_tax_template') else 0
        entered = net * (1 + tax / 100) if item.get('custom_purchase_rate_includes_vat') else net
        before = {key: item.get(key) for key in ('custom_purchase_rate_entry', 'custom_default_purchase_rate')}
        item.custom_purchase_rate_entry = flt(entered, 2)
        item.save()
        audit.append(dict(item_code=code, before=before, updated_modified=str(item.modified), net_cost=net))
    for product in doc.items:
        product.master_cost_updated = cint(product.update_item_master)
    doc.master_cost_updates = json.dumps(audit, default=str)


def restore_master_costs(doc):
    for change in frappe.parse_json(doc.master_cost_updates or '[]'):
        item = frappe.get_doc('Item', change['item_code'], for_update=True)
        if str(item.modified) != change['updated_modified']:
            frappe.msgprint(_('Item {0} has a later edit; its master cost was retained.').format(item.name))
            continue
        item.check_permission('write')
        item.update(change['before'])
        item.save()


def install():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    for name in ('product_conversion_item', 'product_conversion_material', 'product_conversion'):
        frappe.reload_doc('retail_app', 'doctype', name)
    install_naming()
    create_custom_fields({'Stock Entry': [
        dict(fieldname='custom_product_conversion', label='Product Conversion', fieldtype='Link',
             options='Product Conversion', insert_after='stock_entry_type', read_only=1, no_copy=1),
        dict(fieldname='custom_conversion_groups', fieldtype='Long Text', hidden=1, read_only=1, no_copy=1),
    ]}, ignore_validate=True, update=True)
    install_navigation()
    install_print_format()
    frappe.clear_cache(doctype='Stock Entry')
    frappe.clear_cache(doctype='Product Conversion')


def install_naming():
    from retail.naming import _set_doctype_property
    _set_doctype_property('Product Conversion', 'autoname', 'PC-.#', 'Data')
    frappe.db.sql("INSERT IGNORE INTO tabSeries (name, current) VALUES (%s, 0)",
                  ('retail-product-conversion:PC',))
    frappe.clear_cache(doctype='Product Conversion')


def next_conversion_name():
    from frappe.model.naming import getseries
    while True:
        name = 'PC-' + getseries('retail-product-conversion:PC', 1)
        if not frappe.db.exists('Product Conversion', name):
            return name


def install_navigation():
    # Site-owned workspace saves must not export environment metadata over the
    # reviewed source fixtures when developer mode happens to be enabled.
    developer_mode = frappe.conf.developer_mode
    frappe.conf.developer_mode = 0
    try:
        _install_navigation()
    finally:
        frappe.conf.developer_mode = developer_mode


def _install_navigation():
    path = Path(__file__).parent / 'retail_app/workspace/product_conversion_link/product_conversion_link.json'
    data = json.loads(path.read_text())
    if not frappe.db.exists('Workspace', data['name']):
        frappe.get_doc(data).insert(ignore_permissions=True)
    else:
        frappe.db.set_value('Workspace', data['name'], {'parent_page': 'Stocks', 'sequence_id': 46.1}, update_modified=False)
    # Remove only the empty legacy link produced by the initial label/name
    # mismatch; this is navigation metadata, never a conversion document.
    if frappe.db.exists('Workspace', 'Product Conversion'):
        legacy = frappe.get_doc('Workspace', 'Product Conversion')
        if legacy.title == 'Product Conversion Link' and legacy.parent_page == 'Items' and not frappe.parse_json(legacy.content or '[]') and not legacy.links and not legacy.shortcuts:
            frappe.delete_doc('Workspace', legacy.name, ignore_permissions=True)
    if frappe.db.exists('Workspace', 'Items'):
        workspace = frappe.get_doc('Workspace', 'Items')
        changed = False
        for table in ('links', 'shortcuts'):
            rows = workspace.get(table)
            brand = next((r for r in rows if r.get('link_to') == 'Brand'), None)
            if not brand:
                continue
            existing = next((r for r in rows if r.get('link_to') == 'Product Conversion'), None)
            old_position = rows.index(existing) if existing else -1
            if existing:
                rows.remove(existing)
            else:
                values = dict(label='Product Conversion', link_to='Product Conversion',
                    **({'type': 'Link', 'link_type': 'DocType'} if table == 'links' else {'type': 'DocType', 'color': 'Grey'}))
                workspace.append(table, values)
                existing = rows.pop()
            position = rows.index(brand) + 1
            rows.insert(position, existing)
            changed = changed or old_position != position
            for index, row in enumerate(rows, 1):
                row.idx = index
        content = frappe.parse_json(workspace.content or '[]')
        if not any(r.get('data', {}).get('shortcut_name') == 'Product Conversion' for r in content):
            for index, block in enumerate(content):
                if block.get('data', {}).get('shortcut_name') == 'Brands':
                    content.insert(index + 1, dict(id='sc_product_conversion', type='shortcut', data=dict(shortcut_name='Product Conversion', col=3)))
                    workspace.content = json.dumps(content)
                    changed = True
                    break
        if changed:
            workspace.save(ignore_permissions=True)
    from retail import sidebar_registry
    sidebar_registry.routes.cache_clear()
    sidebar_registry.labels.cache_clear()
    sidebar_registry.registry.cache_clear()
    # Administrator already has full document access. Its saved menu layout
    # should show this newly requested Items entry without resetting that layout.
    field = 'retail_sidebar_permissions'
    marker = 'retail.product_conversion.admin_navigation.v1'
    if not frappe.db.get_default(marker):
        saved = frappe.db.get_value('User', 'Administrator', field)
        if saved:
            selection = frappe.parse_json(saved)
            if selection.get('version') == 1 and isinstance(selection.get('allowed'), list) and 'workspace:items' in selection['allowed'] and 'workspace:product_conversion_link' not in selection['allowed']:
                selection['allowed'].append('workspace:product_conversion_link')
                frappe.db.set_value('User', 'Administrator', field, json.dumps(selection), update_modified=False)
        frappe.db.set_default(marker, 1)
    frappe.clear_cache()


def install_print_format():
    name = 'Product Conversion - A4'
    if not frappe.db.exists('Print Format', name):
        html = (Path(__file__).parent / 'templates/print_formats/product_conversion.html').read_text()
        frappe.get_doc(dict(doctype='Print Format', name=name, doc_type='Product Conversion',
                            custom_format=1, print_format_type='Jinja', html=html, standard='No',
                            disabled=0, default_print_language='en')).insert(ignore_permissions=True)
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter
    make_property_setter('Product Conversion', None, 'default_print_format', name, 'Data', for_doctype=True)


def print_context(doc):
    company = frappe.get_cached_doc('Company', doc.company)
    address = ''
    phone = company.get('phone_no') or ''
    link = frappe.db.get_value('Dynamic Link', dict(link_doctype='Company', link_name=doc.company, parenttype='Address'), 'parent')
    if link:
        address_doc = frappe.get_doc('Address', link)
        address = ', '.join(str(address_doc.get(f)) for f in ('address_line1', 'address_line2', 'city', 'pincode', 'country') if address_doc.get(f))
        phone = address_doc.phone or phone
    return dict(company=company.company_name, address=address, phone=phone, tax_id=company.get('tax_id') or '',
                in_charge=frappe.get_cached_value('User', doc.in_charge, 'full_name') if doc.in_charge else '',
                packed_by=frappe.get_cached_value('User', doc.packed_by, 'full_name') if doc.packed_by else '')
