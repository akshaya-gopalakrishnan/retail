import uuid

import frappe
from frappe.model.document import Document

from retail.access_control import require_super_admin
from retail.licensing.client import DISPLAY_FIELDS, DOCTYPE, settings_lock, used_users


class CelestaLicenseSettings(Document):
    def onload(self):
        require_super_admin()
        self.used_licensed_users = used_users()

    def validate(self):
        require_super_admin()
        from retail.licensing.enforcement import validate_assignments
        validate_assignments(self)
        previous = frappe.db.get_singles_dict(DOCTYPE)
        self.installation_id = previous.get("installation_id") or str(uuid.uuid4())
        # Read-only metadata cannot be supplied through REST or ordinary form saves.
        for field in DISPLAY_FIELDS:
            self.set(field, previous.get(field))
        if self.license_key and not self.is_dummy_password(self.license_key):
            from frappe.utils.password import get_decrypted_password
            old_key = get_decrypted_password(DOCTYPE, DOCTYPE, "license_key", raise_exception=False)
            if old_key != self.license_key:
                for field in DISPLAY_FIELDS:
                    self.set(field, None)
        self.used_licensed_users = len(self.get("licensed_users", []))

    def save(self, *args, **kwargs):
        require_super_admin()
        with settings_lock():
            return super().save(*args, **kwargs)
