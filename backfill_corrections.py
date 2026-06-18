#!/usr/bin/env python3
"""
Backfill corrections DB from existing OOTD lookbook entries.

For each OOTD entry that has Items linked:
  - Gets each linked item's name, SKU, colour, designer
  - Derives clothing type from SKU category code
  - Saves to corrections_db as a prior decision (no image hash)

This gives the AI prior knowledge of what items Lisa actually wears,
so type+colour matching immediately favours her real wardrobe.
"""

import os, requests, json, time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

import corrections_db
import collection_cache

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
OOTD_DB_ID = os.environ["NOTION_DATABASE_ID"]
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# SKU category code → human type label for matching
SKU_TYPE_MAP = {
    "TOP": "top",
    "SHR": "shirt",
    "KNT": "sweater",
    "TRS": "trousers",
    "SKT": "skirt",
    "DRS": "dress",
    "OTW": "jacket",
    "SHO": "shoes",
    "BAG": "bag",
    "SCF": "scarf",
    "JMP": "jumpsuit",
    "JWL": "jewelry",
    "ACC": "accessory",
    "BAS": "basics",
}


def fetch_all_ootd():
    pages, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        r = requests.post(
            f"https://api.notion.com/v1/databases/{OOTD_DB_ID}/query",
            headers=HEADERS,
            json=body,
        )
        r.raise_for_status()
        data = r.json()
        pages.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
        time.sleep(0.35)
    return pages


def main():
    corrections_db.init()

    print("Loading collection cache...")
    catalog = collection_cache.load()
    catalog_by_id = {item["id"]: item for item in catalog}
    print(f"  {len(catalog)} items in cache")

    print("\nFetching OOTD entries...")
    pages = fetch_all_ootd()
    with_items = [
        p for p in pages
        if p["properties"].get("Items", {}).get("relation")
    ]
    print(f"  {len(pages)} total entries, {len(with_items)} with items linked")

    total_saved = 0
    skipped_no_cache = 0

    for page in with_items:
        props = page["properties"]
        worn_date = (props.get("Worn", {}).get("date") or {}).get("start", "")
        item_ids = [r["id"] for r in props["Items"]["relation"]]

        records = []
        for item_id in item_ids:
            collection_item = catalog_by_id.get(item_id)
            if not collection_item:
                skipped_no_cache += 1
                continue

            sku_cat = collection_item.get("sku_cat", "")
            item_type = SKU_TYPE_MAP.get(sku_cat, sku_cat.lower() if sku_cat else "item")
            colour = collection_item.get("colour", "")

            records.append({
                "item_type": item_type,
                "item_colour": colour,
                "visual_description": "",
                "ai_top_id": None,
                "ai_top_name": None,
                "correct_id": item_id,
                "correct_name": collection_item["name"],
            })

        if records:
            # Use empty image hash — these are historical entries without photos in our system
            corrections_db.save_decisions("", worn_date, records)
            total_saved += len(records)

    print(f"\nBackfill complete:")
    print(f"  {total_saved} item-wear records saved")
    print(f"  {skipped_no_cache} item IDs not in collection cache (archived/deleted items)")
    print(f"\nDB stats: {corrections_db.stats()}")


if __name__ == "__main__":
    main()
