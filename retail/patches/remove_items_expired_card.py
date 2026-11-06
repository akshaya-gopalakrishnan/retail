"""Remove the expiry number card from Items while retaining its report."""

import json

import frappe


def remove_card(data):
	cards = data.get("number_cards", [])
	data["number_cards"] = [row for row in cards if row.get("number_card_name") != "Expired Items"]
	blocks = json.loads(data.get("content") or "[]")
	remaining = [block for block in blocks if not (
		block.get("type") == "number_card"
		and block.get("data", {}).get("number_card_name") == "Expired Items"
	)]
	stock_cards = [block for block in remaining if block.get("type") == "number_card"]
	if len(remaining) != len(blocks) and len(stock_cards) == 3 and {
		block.get("data", {}).get("number_card_name") for block in stock_cards
	} == {"Total Active Items", "Low Stock Items", "Out of Stock Items"} and all(
		block["data"].get("col") == 3 for block in stock_cards
	):
		# Restore the three-card layout that preceded the expiry card.
		for block in stock_cards:
			block["data"]["col"] = 4
	data["content"] = json.dumps(remaining, separators=(",", ":"))


def execute():
	if not frappe.db.exists("Workspace", "Items"):
		return
	doc = frappe.get_doc("Workspace", "Items")
	data = {"content": doc.content, "number_cards": [row.as_dict() for row in doc.number_cards]}
	remove_card(data)
	if data["content"] != doc.content or len(data["number_cards"]) != len(doc.number_cards):
		doc.content = data["content"]
		doc.set("number_cards", data["number_cards"])
		doc.db_update()
		doc.update_children()
	doc.clear_cache()
