"""Short-lived, user-scoped Desk caches; invalidation follows committed writes."""
from functools import wraps
from hashlib import sha256
from uuid import uuid4

import frappe
from frappe.utils import nowdate

WORKSPACES = frozenset(("Business Home", "Items", "Sales", "Purchases", "Stocks",
                       "Accounts", "POS", "Reports", "Promotions", "Settings"))


def cached(group, seconds):
    def decorate(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            # Unit tests exercise the computation without leaking fixtures to Redis.
            if frappe.flags.in_test or kwargs.get("no_cache") or kwargs.get("refresh"):
                return function(*args, **kwargs)
            epoch = frappe.cache.get_value(f"retail:desk-speed:epoch:{group}") or "0"
            identity = [frappe.session.user, (frappe.defaults.get_user_default("Company") or frappe.defaults.get_user_default("company")),
                        frappe.local.lang, nowdate(), epoch, args, kwargs,
                        {key: frappe.form_dict.get(key) for key in
                         ("company", "from_date", "to_date", "branch", "counter")}]
            digest = sha256(frappe.as_json(identity).encode()).hexdigest()
            key = f"retail:desk-speed:{group}:{digest}"
            value = frappe.cache.get_value(key)
            if value is not None:
                return frappe.parse_json(value)
            result = function(*args, **kwargs)
            frappe.cache.set_value(key, frappe.as_json(result), expires_in_sec=seconds)
            return result
        return wrapper
    return decorate


def _invalidate(groups):
    for group in groups:
        # In-flight old requests can only populate their obsolete epoch.
        frappe.cache.set_value(f"retail:desk-speed:epoch:{group}", str(uuid4()))


def _schedule(groups):
    pending = frappe.flags.get("retail_desk_speed_invalidations")
    if pending is None:
        pending = set()
        frappe.flags.retail_desk_speed_invalidations = pending
        def finish():
            _invalidate(tuple(pending))
            frappe.flags.pop("retail_desk_speed_invalidations", None)
        frappe.db.after_commit.add(finish)
        frappe.db.after_rollback.add(lambda: frappe.flags.pop("retail_desk_speed_invalidations", None))
    pending.update(groups)


def invalidate_values(doc=None, method=None):
    _schedule(("cards", "trend", "credit"))


def invalidate_permissions(doc=None, method=None):
    _schedule(("cards", "trend", "credit", "desktop"))


def invalidate_desktop(doc=None, method=None):
    _schedule(("desktop",))


def warmup_meta():
    # Build server metadata only; getdoctype also evaluates user-specific scripts.
    from frappe.desk.form.meta import get_meta
    for doctype in ("Item", "POS Invoice", "Purchase Invoice", "Sales Invoice", "Payment Entry"):
        get_meta(doctype)


def clear_caches():
    _invalidate(("cards", "trend", "credit", "desktop"))
