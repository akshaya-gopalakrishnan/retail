"""Admin and scheduled refreshes; login authorization never calls the network."""
import time
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib.parse import urlsplit

import frappe
import requests
from frappe.utils import convert_utc_to_system_timezone

from retail.access_control import is_super_admin, require_super_admin
from retail.licensing.signature import RULE_FIELDS
from retail.licensing.state import verify_protected, transition_context

DOCTYPE = "Celesta License Settings"
DISPLAY_FIELDS = (*RULE_FIELDS[:-1], "customer_name", "last_verified", "offline_valid_until", "verified_issued_at", "verified_token")


class LicenseRefreshError(frappe.ValidationError):
    """Contains only a fixed, credential-free diagnostic."""


def _refresh_failed(reason):
    frappe.throw(f"License verification failed. {reason} Previous verified data was retained.",
                 exc=LicenseRefreshError)


def _alert_refresh_failure():
    """Notify repair administrators daily when signed access is near its deadline."""
    from retail.licensing.signature import verify_response
    doc = frappe.get_doc(DOCTYPE)
    try:
        claims = verify_response(doc.verified_token, frappe.conf.get("celesta_license_public_keys", []),
                                 doc.installation_id, time.time(), authenticate_only=True)
    except Exception:
        return  # Never treat unsigned display fields as a license deadline.
    remaining = claims["exp"] - time.time()
    if remaining > 6 * 3600:
        return
    state = "expired" if remaining <= 0 else "expires within six hours"
    subject = f"Celesta license {state}; refresh failed"
    roles = frappe.get_all("Has Role", filters={"role": "Super Admin", "parenttype": "User"}, pluck="parent")
    users = frappe.get_all("User", filters={"enabled": 1, "name": ["in", list(set(roles + ["Administrator"]))]}, pluck="name")
    from frappe.utils import today
    for user in users:
        if frappe.db.exists("Notification Log", {"for_user": user, "subject": subject,
                "document_type": DOCTYPE, "document_name": DOCTYPE, "creation": [">=", today()]}):
            continue
        frappe.get_doc({"doctype": "Notification Log", "type": "Alert", "for_user": user,
                       "subject": subject, "document_type": DOCTYPE, "document_name": DOCTYPE,
                       "email_content": "Open Celesta License Settings and use Sync/Verify. Check the license server endpoint and refresh logs. New logins require a valid signed token; the subscription expiry date alone does not authorize login."}).insert(ignore_permissions=True)


def has_permission(doc, ptype=None, user=None, **kwargs):
    return is_super_admin(user)


@contextmanager
def settings_lock():
    # The existing DocType row also serializes first-save UUID creation.
    # Held until the request transaction commits or rolls back.
    frappe.db.sql("select name from tabDocType where name=%s for update", DOCTYPE)
    yield


def used_users():
    from retail.licensing.enforcement import assigned_users
    return len(assigned_users())


def _local_time(timestamp):
    return convert_utc_to_system_timezone(datetime.fromtimestamp(timestamp, timezone.utc).replace(tzinfo=None))


@frappe.whitelist(methods=["POST"])
def activate():
    require_super_admin()
    return _sync("activate")


@frappe.whitelist(methods=["POST"])
def verify():
    require_super_admin()
    return _sync("verify")


def scheduled_sync():
    """Hourly best-effort refresh. Failure never extends or erases signed validity."""
    if not frappe.db.get_single_value(DOCTYPE, "installation_id"):
        return
    try:
        return _sync("verify")
    except Exception as error:
        # Exclude exception details, credentials and response contents.
        frappe.logger("retail.licensing").warning(
            "Scheduled license refresh failed; retained the previous signed license. %s",
            str(error) if isinstance(error, LicenseRefreshError) else "Unexpected refresh failure.",
        )
        try:
            _alert_refresh_failure()
        except Exception:
            frappe.logger("retail.licensing").warning("Could not create the license expiry alert.")
        return {"status": "unavailable"}


def _sync(action):
    # Serialize saves and network checks to avoid older results replacing newer data.
    with settings_lock():
        doc = frappe.get_doc(DOCTYPE)
        key = doc.get_password("license_key", raise_exception=False)
        if not key or not doc.installation_id:
            frappe.throw("Save a license key first to generate the installation ID.")
        base = frappe.conf.get("celesta_license_server_url", "")
        keys = frappe.conf.get("celesta_license_public_keys", [])
        url = urlsplit(base)
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.path not in ("", "/")
                or not isinstance(keys, list) or not keys):
            frappe.throw("Configure the central HTTPS origin and trusted license public keys before activation.")
        reason = None
        try:
            current = transition_context(doc.installation_id)
        except Exception:
            reason = "Check the protected state path, permissions and installation binding."
        if reason:
            _refresh_failed(reason)
        try:
            nonce = secrets.token_hex(32)
            response = requests.post(
                base.rstrip("/") + "/api/method/celesta_license.api." + action,
                json={"license_key": key, "installation_id": doc.installation_id,
                      "current_license_id": current, "transition_nonce": nonce},
                timeout=(5, 15), allow_redirects=False,
            )
        except requests.Timeout:
            reason = "The license server timed out. Check its availability."
        except requests.ConnectionError:
            reason = "Cannot connect securely to the license server. Check HTTPS, DNS and tunnel availability."
        except Exception:
            reason = "The license server request failed. Check its availability."
        if reason:
            _refresh_failed(reason)
        if len(response.content) > 65536:
            _refresh_failed("The license server returned an oversized response.")
        if response.status_code != 200:
            # Inspect only a bounded response to select fixed text; never relay it.
            try:
                wrong_site = "App celesta_license is not installed" in response.json().get("exception", "")
            except Exception:
                wrong_site = False
            if wrong_site:
                _refresh_failed("The URL points to a site without celesta_license. Route the licensing URL to the license authority site, separately from the Retail/POS URL.")
            if response.status_code in (401, 403):
                _refresh_failed("The license server refused the request. Check credentials, installation binding and HTTPS routing.")
            if response.status_code == 429:
                _refresh_failed("The license server rate limit was reached. Retry later.")
            _refresh_failed("The license server returned an unsuccessful HTTP response. Check endpoint routing and server health.")
        try:
            token = response.json()["message"]["token"]
        except Exception:
            reason = "The endpoint did not return a signed license token. Check that the URL routes to the license API."
        if reason:
            _refresh_failed(reason)
        try:
            claims = verify_protected(token, keys,
                                     doc.installation_id, time.time(), int(doc.verified_issued_at or 0),
                                     transition_nonce=nonce)
        except Exception:
            reason = "The signed token failed validation. Check trusted public keys, installation identity, license version and server time."
        if reason:
            _refresh_failed(reason)
        values = {field: claims["rules"][field] for field in RULE_FIELDS[:-1]}
        values.update(customer_name=claims["rules"].get("customer_name", ""),
                      last_verified=_local_time(claims["iat"]),
                      offline_valid_until=_local_time(claims["exp"]),
                      verified_issued_at=str(claims["iat"]), verified_token=token)
        frappe.db.set_single_value(DOCTYPE, values)
        return {"status": values["status"]}
