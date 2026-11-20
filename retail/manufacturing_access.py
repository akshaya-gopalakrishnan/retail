"""Translate explicit Manufacturing access setup into a native functional role."""

import json


def prepare_user(doc, method=None):
    # Do not turn ordinary profile saves or implicit legacy sidebar defaults
    # into role assignments. Existing access-control validation still checks
    # the resulting roles against the assigning administrator's ceiling.
    from retail.access_control import is_super_admin
    from retail.delegated_access import manages

    if doc.get("user_type") != "System User":
        return
    if not is_super_admin() and not manages(doc):
        return
    previous = doc.get_doc_before_save()
    fields = ("retail_sidebar_permissions", "module_profile", "role_profile_name")
    if previous and all(doc.get(key) == previous.get(key) for key in fields) and all(
        {row.get(key) for row in doc.get(field, [])}
        == {row.get(key) for row in previous.get(field, [])}
        for field, key in (("roles", "role"), ("block_modules", "module"))
    ):
        return
    if "Manufacturing" in doc.get_blocked_modules():
        return
    try:
        selected = json.loads(doc.get("retail_sidebar_permissions") or "{}")
    except (ValueError, TypeError):
        return  # Sidebar validation reports malformed selections.
    if not isinstance(selected, dict) or selected.get("version") != 1:
        return
    from retail.sidebar_registry import registry
    group = next(group for group in registry() if group["workspace"] == "Manufacturing")
    chosen = selected.get("allowed")
    if not isinstance(chosen, list) or not any(child["id"] in chosen for child in group["children"]):
        return
    doc.append_roles("Manufacturing User")
