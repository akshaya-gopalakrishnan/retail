"""Retail-owned promotional card batches. Existing earned vouchers stay unchanged."""
from decimal import Decimal, InvalidOperation
import secrets

import frappe
from frappe.utils import cint, flt, getdate, nowdate


def card_money(value):
    try:
        amount = Decimal(str(value))
        valid = amount.is_finite() and amount > 0 and amount == amount.quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError, TypeError):
        valid = False
    if not valid:
        frappe.throw('Value must be positive with at most two decimal places.')
    # Currency fields use Frappe float values; reject precision loss instead of silently rounding.
    result = float(amount)
    if any(Decimal(str(float(amount + step))) != amount + step
           for step in (Decimal('0'), Decimal('0.01'), Decimal('-0.01'))):
        frappe.throw('This amount exceeds the exact currency precision supported by the system.')
    return result


def batch_for(voucher):
    name = voucher.get('voucher_card_batch')
    return frappe.get_cached_doc('Voucher Card Batch', name) if name else None


def record(voucher, event, amount=0, reference=None):
    """One mutable status document per card; POS operation receipts retain debits."""
    if not voucher.get('voucher_card_batch'):
        return
    current = frappe.db.get_value('Gift Voucher Ledger', voucher.name,
        ['status', 'balance_amount', 'card_archived', 'card_blocked'], as_dict=True)
    status = 'Archived' if current.card_archived else 'Blocked' if current.card_blocked else {
        'Unused': 'Active', 'Redeemed': 'Fully Used'}.get(current.status, current.status)
    values = dict(voucher=voucher.name, batch=voucher.voucher_card_batch,
        company=voucher.company, currency=voucher.currency, event=event, status=status,
        amount=amount, balance_after=current.balance_amount, reference=reference,
        actor=frappe.session.user)
    existing = frappe.db.get_value('Voucher Card Transaction', {'voucher': voucher.name},
        'name', order_by='creation asc', for_update=True)
    if existing:
        # Update in place without a Version or another event document.
        frappe.db.set_value('Voucher Card Transaction', existing, values)
    else:
        entry = frappe.get_doc(dict(doctype='Voucher Card Transaction', **values))
        entry.flags.card_service = True
        entry.insert(ignore_permissions=True)


def authorize_batch(name):
    from retail.sidebar_permissions import require_target
    require_target('doctype', 'Voucher Card Batch')
    doc = frappe.get_doc('Voucher Card Batch', name, for_update=True)
    doc.check_permission('write')
    return doc


@frappe.whitelist(methods=['POST'])
def generate_cards(batch):
    doc = authorize_batch(batch)
    if doc.generation_status == 'Complete':
        frappe.throw('This batch is already complete.')
    doc.db_set({'generation_status': 'Queued', 'generation_error': ''})
    frappe.enqueue('retail.voucher_cards.generate_worker', queue='long', timeout=7200,
        enqueue_after_commit=True, batch=batch, user=frappe.session.user)
    return {'status': 'Queued'}


def make_card_code():
    # Avoid easily confused characters; five characters leave 33 million codes.
    return ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(5))


def insert_card(voucher):
    values = voucher.as_dict()
    for attempt in range(50):
        code = values['voucher_code'] if attempt == 0 else make_card_code()
        frappe.db.savepoint('voucher_card_short_code')
        candidate = frappe.get_doc({**values, 'voucher_code': code})
        candidate.flags.card_service = True
        try:
            candidate.insert(ignore_permissions=True)
            return candidate
        except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
            frappe.db.rollback(save_point='voucher_card_short_code')
            # Retry only code collisions, not a duplicate issuance key or other failure.
            if not frappe.db.exists('Gift Voucher Ledger', code):
                raise
    frappe.throw('Could not allocate a unique short voucher code. Retry generation.')


def generate_worker(batch, user=None):
    if user:
        frappe.set_user(user)
    try:
        while True:
            # Commit a bounded chunk with its progress, then allow other requests to run.
            doc = authorize_batch(batch)
            if doc.generation_status == 'Complete':
                return
            if doc.generation_status not in ('Queued', 'Generating', 'Failed'):
                frappe.throw('Batch has not been queued.')
            start = cint(doc.generated_count) + 1
            end = min(cint(doc.card_count), start + 199)
            for number in range(start, end + 1):
                voucher = frappe.get_doc(dict(doctype='Gift Voucher Ledger',
                    voucher_code=make_card_code(),
                    voucher_card_batch=batch, card_number=number,
                    issuance_key=f'card:{batch}:{number}', company=doc.company, currency=doc.currency,
                    voucher_amount=doc.voucher_amount, balance_amount=doc.voucher_amount,
                    valid_from=doc.valid_from, expiry_date=doc.expiry_date, issued_date=nowdate(),
                    use_redemption_hours=doc.get("use_redemption_hours"), active_from_time=doc.get("active_from_time"), active_to_time=doc.get("active_to_time"),
                    status='Unused' if doc.activate_all_cards else 'Draft'))
                voucher = insert_card(voucher)
                record(voucher, 'Issued', doc.voucher_amount)
                if doc.activate_all_cards:
                    record(voucher, 'Activated')
            complete = end >= cint(doc.card_count)
            doc.db_set({'generated_count': end, 'generation_status': 'Complete' if complete else 'Generating'})
            frappe.db.commit()
            frappe.publish_realtime('voucher_card_progress', {'batch': batch, 'count': end}, user=user)
            if complete:
                return
    except Exception:
        frappe.db.rollback()
        frappe.db.set_value('Voucher Card Batch', batch, {
            'generation_status': 'Failed', 'generation_error': 'Generation stopped. Review Error Log, then retry; completed cards are retained.'})
        frappe.log_error(title='Voucher card generation failed')
        frappe.db.commit()
        raise


def activate_batch(name):
    doc = authorize_batch(name)
    if getdate(doc.expiry_date) < getdate(nowdate()):
        frappe.throw('Cannot activate an expired batch.')
    # Chunks avoid one huge synchronous activation request.
    frappe.enqueue('retail.voucher_cards.activate_worker', queue='long', timeout=7200,
        enqueue_after_commit=True, batch=name, user=frappe.session.user)


def activate_worker(batch, user):
    frappe.set_user(user)
    while True:
        names = frappe.get_all('Gift Voucher Ledger', filters={
            'voucher_card_batch': batch, 'status': 'Draft', 'card_blocked': 0, 'card_archived': 0},
            pluck='name', limit_page_length=200, order_by='card_number')
        if not names:
            return
        manage_cards(batch, names, 'Activate')
        frappe.db.commit()


@frappe.whitelist(methods=['POST'])
def manage_cards(batch, cards, action):
    doc = authorize_batch(batch)
    names = frappe.parse_json(cards) if isinstance(cards, str) else cards
    if not isinstance(names, list) or not names or len(names) > 500 or not all(isinstance(n, str) for n in names):
        frappe.throw('Select between 1 and 500 cards.')
    if action not in ('Activate', 'Block', 'Archive'):
        frappe.throw('Invalid card action.')
    for name in sorted(set(names)):
        voucher = frappe.get_doc('Gift Voucher Ledger', name, for_update=True)
        if voucher.get('voucher_card_batch') != doc.name:
            frappe.throw('Selected card belongs to another batch.', frappe.PermissionError)
        if action == 'Activate':
            if voucher.status != 'Draft' or voucher.card_blocked or voucher.card_archived:
                continue
            if getdate(voucher.expiry_date) < getdate(nowdate()):
                frappe.throw('Cannot activate expired cards.')
            voucher.db_set('status', 'Unused')
            record(voucher, 'Activated')
        elif action == 'Block':
            if not voucher.card_blocked:
                voucher.db_set('card_blocked', 1)
                record(voucher, 'Blocked')
        else:
            if flt(voucher.balance_amount) > 0 and getdate(voucher.expiry_date) >= getdate(nowdate()):
                frappe.throw('Only expired or fully used cards can be archived.')
            if not voucher.card_archived:
                voucher.db_set('card_archived', 1)
                record(voucher, 'Archived')
    return {'status': 'Success'}


def eligible_amount(voucher, items, bill_total):
    """Use saved Item identity; never trust a terminal-supplied brand or category."""
    batch = batch_for(voucher)
    if not batch or batch.all_products:
        return max(0, flt(bill_total))
    if not items:
        frappe.throw('Restricted voucher cards require bill items for eligibility validation.')
    if isinstance(items, str):
        items = frappe.parse_json(items)
    if isinstance(items, list):
        items = [row.as_dict() if hasattr(row, 'as_dict') else row for row in items]
    if not isinstance(items, list) or not all(isinstance(row, dict) for row in items):
        frappe.throw('Bill items must be a list of item rows.')
    total = 0
    for row in items:
        if not row.get('item_code') or row.get('is_free_item'):
            continue
        identity = frappe.get_cached_value('Item', row['item_code'], ['brand', 'item_group'], as_dict=True)
        if not identity:
            frappe.throw('Voucher bill contains an unknown item.')
        groups = set()
        group = identity.item_group
        while group and group not in groups:
            groups.add(group)
            group = frappe.get_cached_value('Item Group', group, 'parent_item_group')
        if any((r.item_code and r.item_code == row['item_code']) or
               (r.brand and r.brand == identity.brand) or
               (r.item_group and r.item_group in groups) for r in batch.restrictions):
            # Explicit zero must remain zero. POS passes the final amount before voucher discount.
            value = row.get('amount_including_vat')
            if value is None:
                value = row.get('net_amount')
            if value is None:
                value = row.get('amount')
            if value is None:
                frappe.throw('Each eligible bill item requires its amount before voucher redemption.')
            total += max(0, flt(value))
    return min(max(0, flt(bill_total)), flt(total, 2))


def print_cards(doc):
    """Called by Jinja. Check access rather than expose arbitrary batch records."""
    doc.check_permission('print')
    if doc.doctype != 'Voucher Card Batch':
        frappe.throw('A voucher card batch is required.')
    if doc.print_from < 1 or doc.print_to < doc.print_from or doc.print_to - doc.print_from >= 500:
        frappe.throw('Print up to 500 cards at a time.')
    cards = frappe.get_all('Gift Voucher Ledger', filters=[['voucher_card_batch', '=', doc.name],
        ['card_number', '>=', doc.print_from], ['card_number', '<=', doc.print_to]],
        fields=['name', 'card_number', 'voucher_amount', 'status', 'valid_from', 'expiry_date'],
        order_by='card_number', limit_page_length=500)
    return with_qr(cards)


def install():
    ensure_card_status_records()
    ensure_voucher_types()
    ensure_print_formats()
    frappe.db.add_unique('Gift Voucher Ledger', ['voucher_card_batch', 'card_number'],
        constraint_name='unique_voucher_batch_card')
    if frappe.db.exists('Workspace', 'Promotions'):
        workspace = frappe.get_doc('Workspace', 'Promotions')
        if not any(r.link_to == 'Voucher Card Batch' for r in workspace.shortcuts):
            workspace.append('shortcuts', dict(type='DocType', link_to='Voucher Card Batch',
                label='Voucher Cards', color='Blue', icon='gift'))
            content = frappe.parse_json(workspace.content or '[]')
            content.insert(1, dict(id='sc_voucher_cards', type='shortcut', data=dict(shortcut_name='Voucher Cards', col=3)))
            workspace.content = frappe.as_json(content)
        if not any(r.link_to == 'Voucher Card Batch' for r in workspace.links):
            workspace.append('links', dict(type='Card Break', label='Voucher Cards', link_count=2))
            for doctype in ('Voucher Card Batch', 'Voucher Card Transaction'):
                workspace.append('links', dict(type='Link', label=doctype, link_type='DocType', link_to=doctype))
        content = frappe.parse_json(workspace.content or '[]')
        if not any(row.get('data', {}).get('card_name') == 'Voucher Cards' for row in content):
            content.append(dict(id='card_voucher_cards', type='card', data=dict(card_name='Voucher Cards', col=4)))
            workspace.content = frappe.as_json(content)
        workspace.save(ignore_permissions=True)


def with_qr(cards):
    import base64
    from io import BytesIO
    import pyqrcode
    for card in cards:
        stream = BytesIO()
        pyqrcode.create(card.name, error='M').svg(stream, scale=3)
        card.barcode = 'data:image/svg+xml;base64,' + base64.b64encode(stream.getvalue()).decode()
    return cards


def voucher_card_print_data(doc):
    if doc.doctype == 'Voucher Card Batch':
        return {'batch': doc, 'cards': print_cards(doc)}
    if doc.doctype != 'Gift Voucher Ledger' or not doc.get('voucher_card_batch'):
        frappe.throw('This print format requires a voucher card.')
    doc.check_permission('print')
    batch = frappe.get_doc('Voucher Card Batch', doc.voucher_card_batch)
    batch.check_permission('read')
    return {'batch': batch, 'cards': with_qr([frappe._dict(name=doc.name,
        voucher_amount=doc.voucher_amount, status=doc.status,
        valid_from=doc.valid_from, expiry_date=doc.expiry_date)])}


def ensure_print_formats():
    # Install missing user-editable copies only. Never replace customer HTML/CSS.
    for name in ('Voucher Cards - A4', 'Voucher Cards - Labels', 'Voucher Card - Card', 'Voucher Card - Label'):
        source = name + ' - Retail'
        if not frappe.db.exists('Print Format', source):
            continue
        if not frappe.db.exists('Print Format', name):
            target = frappe.copy_doc(frappe.get_doc('Print Format', source))
            target.name = name
            target.custom_document_code = None
            target.standard = 'No'
            target.custom_format = 1
            target.insert(ignore_permissions=True)
        elif frappe.db.get_value('Print Format', name, 'standard') == 'Yes':
            frappe.db.set_value('Print Format', name, {'standard': 'No', 'custom_format': 1})


def ensure_voucher_types():
    # Derived display metadata only: preserve amounts, status and modified dates.
    frappe.db.sql("""UPDATE `tabGift Voucher Ledger`
        SET voucher_kind = CASE WHEN COALESCE(voucher_card_batch, '') != ''
            THEN 'Voucher Card' ELSE 'Promotion Voucher' END
        WHERE COALESCE(voucher_kind, '') != CASE WHEN COALESCE(voucher_card_batch, '') != ''
            THEN 'Voucher Card' ELSE 'Promotion Voucher' END""")
    name = 'Gift Voucher Ledger'
    settings = frappe.get_doc('List View Settings', name) if frappe.db.exists('List View Settings', name) else None
    if settings is None:
        settings = frappe.new_doc('List View Settings')
        settings.name = name
        fields = [{'fieldname': field} for field in
            ('voucher_code', 'voucher_kind', 'voucher_amount', 'balance_amount', 'status_field')]
        settings.fields = frappe.as_json(fields)
        settings.total_fields = str(len(fields) + 3)
        settings.save(ignore_permissions=True)
    elif settings.fields:
        fields = frappe.parse_json(settings.fields)
        if not any(row.get('fieldname') == 'voucher_kind' for row in fields):
            fields.insert(0, {'fieldname': 'voucher_kind'})
            settings.fields = frappe.as_json(fields)
            settings.total_fields = str(max(cint(settings.total_fields) + 1, len(fields) + 3))
            settings.save(ignore_permissions=True)
    frappe.clear_cache(doctype=name)


def ensure_card_status_records():
    """Consolidate prior event rows, then enforce one status document per card."""
    vouchers = frappe.db.sql("""SELECT voucher FROM `tabVoucher Card Transaction`
        GROUP BY voucher HAVING COUNT(*) > 1 OR
        SUM(CASE WHEN COALESCE(status, '') = '' THEN 1 ELSE 0 END) > 0""", as_dict=True)
    for row in vouchers:
        if not row.voucher or not frappe.db.exists('Gift Voucher Ledger', row.voucher):
            continue
        voucher = frappe.get_doc('Gift Voucher Ledger', row.voucher, for_update=True)
        latest = frappe.get_all('Voucher Card Transaction', filters={'voucher': row.voucher},
            fields=['event', 'amount', 'reference'], order_by='creation desc, name desc', limit_page_length=1)[0]
        record(voucher, latest.event, latest.amount, latest.reference)
        keep = frappe.db.get_value('Voucher Card Transaction', {'voucher': row.voucher},
            'name', order_by='creation asc')
        # Only redundant custom history rows are removed; original POS receipts stay.
        frappe.db.delete('Voucher Card Transaction', {'voucher': row.voucher, 'name': ['!=', keep]})
    frappe.db.add_unique('Voucher Card Transaction', ['voucher'], constraint_name='unique_card_status_voucher')
