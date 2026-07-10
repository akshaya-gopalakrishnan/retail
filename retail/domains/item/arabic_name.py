"""Arabic item-name helpers for Item master."""

from __future__ import annotations

import json

import frappe
import requests
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils import cint, flt


ARABIC_ITEM_NAME_FIELD = "custom_arabic_item_name"
GOOGLE_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"


def ensure_item_arabic_name_field():
	"""Add the Arabic item name under Item Name and keep field order stable."""
	create_custom_fields(
		{
			"Item": [
				{
					"fieldname": ARABIC_ITEM_NAME_FIELD,
					"label": "Arabic Item Name",
					"fieldtype": "Data",
					"insert_after": "item_name",
					"translatable": 1,
					"in_global_search": 1,
				},
			],
		},
		update=True,
	)
	_set_item_arabic_name_field_order()


@frappe.whitelist()
def translate_item_name_to_arabic(text: str | None = None):
	"""Translate an English item name into Arabic using the configured provider."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	text = (text or "").strip()
	if not text:
		return {"translated_text": "", "configured": True}

	url = (frappe.conf.get("retail_translation_url") or "").strip()
	provider = (frappe.conf.get("retail_translation_provider") or "libretranslate").lower()
	timeout = flt(frappe.conf.get("retail_translation_timeout") or 8) or 8

	if provider == "google":
		return _translate_with_google(text, timeout)

	if not url:
		return {"translated_text": "", "configured": False}

	payload = {
		"q": text,
		"source": frappe.conf.get("retail_translation_source_language") or "en",
		"target": frappe.conf.get("retail_translation_target_language") or "ar",
		"format": "text",
	}
	if api_key := frappe.conf.get("retail_translation_api_key"):
		payload["api_key"] = api_key

	try:
		response = requests.post(url, json=payload, timeout=timeout)
		response.raise_for_status()
		data = response.json()
	except Exception:
		frappe.log_error(title="Arabic Item Name Translation Failed")
		return {"translated_text": "", "configured": True, "error": True}

	translated_text = _extract_translated_text(data)
	return {"translated_text": translated_text, "configured": True}


def _translate_with_google(text, timeout):
	params = {
		"client": "gtx",
		"sl": frappe.conf.get("retail_translation_source_language") or "en",
		"tl": frappe.conf.get("retail_translation_target_language") or "ar",
		"dt": "t",
		"q": text,
	}
	try:
		response = requests.get(GOOGLE_TRANSLATE_URL, params=params, timeout=timeout)
		response.raise_for_status()
		data = response.json()
	except Exception:
		frappe.log_error(title="Arabic Item Name Translation Failed")
		return {"translated_text": "", "configured": True, "error": True}

	return {"translated_text": _extract_google_translation(data), "configured": True}


def _extract_google_translation(data):
	if not isinstance(data, list) or not data:
		return ""

	parts = []
	for segment in data[0] or []:
		if isinstance(segment, list) and segment:
			parts.append(segment[0] or "")
	return "".join(parts)


def _extract_translated_text(data):
	if isinstance(data, dict):
		for key in ("translatedText", "translated_text", "translation"):
			if data.get(key):
				return data.get(key)
		if isinstance(data.get("data"), dict):
			return _extract_translated_text(data.get("data"))
	if isinstance(data, list) and data:
		return _extract_translated_text(data[0])
	return ""


def _set_item_arabic_name_field_order():
	property_setter = "Item-main-field_order"
	field_order = _get_item_field_order(property_setter)
	field_order = [field for field in field_order if field != ARABIC_ITEM_NAME_FIELD]

	try:
		item_name_index = field_order.index("item_name")
	except ValueError:
		field_order.insert(0, ARABIC_ITEM_NAME_FIELD)
	else:
		field_order.insert(item_name_index + 1, ARABIC_ITEM_NAME_FIELD)

	value = json.dumps(field_order)
	if frappe.db.exists("Property Setter", property_setter):
		frappe.db.set_value("Property Setter", property_setter, "value", value, update_modified=False)
	else:
		make_property_setter("Item", "main", "field_order", value, "Data", validate_fields_for_doctype=False)

	if frappe.db.exists("Custom Field", f"Item-{ARABIC_ITEM_NAME_FIELD}"):
		frappe.db.set_value(
			"Custom Field",
			f"Item-{ARABIC_ITEM_NAME_FIELD}",
			{
				"insert_after": "item_name",
				"translatable": cint(1),
				"in_global_search": cint(1),
			},
			update_modified=False,
		)
	frappe.clear_cache(doctype="Item")


def _get_item_field_order(property_setter):
	value = frappe.db.get_value("Property Setter", property_setter, "value")
	if value:
		try:
			return json.loads(value)
		except (TypeError, ValueError):
			pass
	return [field.fieldname for field in frappe.get_meta("Item").fields]
