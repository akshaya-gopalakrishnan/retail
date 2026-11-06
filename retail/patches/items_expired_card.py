"""Add the expiry card after Out of Stock without resetting the Items workspace."""

import json

import frappe


def add_card(data):
	cards = data.setdefault("number_cards", [])
	if not any(row.get("number_card_name") == "Expired Items" for row in cards):
		index = next((i + 1 for i, row in enumerate(cards)
			if row.get("number_card_name") == "Out of Stock Items"), len(cards))
		cards.insert(index, {"label": "Expired Items", "number_card_name": "Expired Items"})
	blocks = json.loads(data.get("content") or "[]")
	if not any(row.get("data", {}).get("number_card_name") == "Expired Items" for row in blocks):
		index = next((i + 1 for i, row in enumerate(blocks)
			if row.get("data", {}).get("number_card_name") == "Out of Stock Items"), 1)
		blocks.insert(index, {"id": "nc_expired_items", "type": "number_card",
			"data": {"number_card_name": "Expired Items", "col": 3}})
		# Fit the four stock cards on one row for the standard Items layout.
		for row in blocks:
			if row.get("type") == "number_card" and row.get("data", {}).get("number_card_name") in (
				"Total Active Items", "Low Stock Items", "Out of Stock Items",
			) and row["data"].get("col") == 4:
				row["data"]["col"] = 3
	data["content"] = json.dumps(blocks, separators=(",", ":"))


def execute():
	frappe.reload_doc("retail_app", "report", "expired_items")
	frappe.reload_doc("retail_app", "number_card", "expired_items")
	if not frappe.db.exists("Workspace", "Items"):
		return
	doc = frappe.get_doc("Workspace", "Items")
	data = {"content": doc.content, "number_cards": [row.as_dict() for row in doc.number_cards]}
	add_card(data)
	if data["content"] != doc.content or len(data["number_cards"]) != len(doc.number_cards):
		doc.content = data["content"]
		doc.set("number_cards", data["number_cards"])
		doc.db_update()
		doc.update_children()
	# Workspace content is also embedded in cached Desk bootinfo.
	doc.clear_cache()
