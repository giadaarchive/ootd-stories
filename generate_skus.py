#!/usr/bin/env python3
"""
Generate full item SKUs: [BRAND_CODE]-[CATEGORY_CODE]-[MATERIAL_CODE]-[YY]-[###]
- BRAND_CODE    from Designer page → SKU Code
- CATEGORY_CODE from Category relation → SKU Code
- MATERIAL_CODE from Material Category relation → SKU Code
- YY            from "Year It's Made (first hand)" date on item
- ###           sequential per brand+category+material+year combo

Skips items that already have a valid SKU (unless it starts with UNB — those get redone).
Run setup_codes.py first to populate Category and Material codes.
"""

import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

_cache = {}

def fetch_page(page_id):
    if page_id in _cache:
        return _cache[page_id]
    r = requests.get(f"https://api.notion.com/v1/pages/{page_id}", headers=HEADERS)
    result = r.json() if r.status_code == 200 else None
    _cache[page_id] = result
    return result


def get_title(props):
    tp = next((v for v in props.values() if v.get("type") == "title"), None)
    return tp["title"][0].get("plain_text", "").strip() if tp and tp.get("title") else ""


def get_rich_text(props, key):
    rt = props.get(key, {}).get("rich_text", [])
    return rt[0]["plain_text"].strip() if rt else ""


def get_relation_code(props, rel_key, code_field="SKU Code"):
    """Follow a relation and return the SKU Code from the related page."""
    relations = props.get(rel_key, {}).get("relation", [])
    if not relations:
        return None
    page = fetch_page(relations[0]["id"])
    if not page:
        return None
    return get_rich_text(page.get("properties", {}), code_field) or None


def get_year(props):
    """Return 2-digit year from 'Year It's Made (first hand)' date property, or None."""
    for key in props:
        if "year" in key.lower() and "made" in key.lower():
            date_val = props[key].get("date")
            if date_val and date_val.get("start"):
                return date_val["start"][:4][2:]  # e.g. "1998" → "98"
    return "00"


def fetch_all_wardrobe_items():
    items, cursor = [], None
    while True:
        payload = {"filter": {"property": "object", "value": "page"}, "page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        r = requests.post("https://api.notion.com/v1/search", headers=HEADERS, json=payload)
        r.raise_for_status()
        data = r.json()
        for page in data["results"]:
            props = page.get("properties", {})
            if "SKU" in props and "Category" in props and "Designer" in props:
                items.append(page)
        if not data.get("has_more"):
            break
        cursor = data["next_cursor"]
    return items


# ── SKU builder ───────────────────────────────────────────────────────────────

def build_sku(page, counters):
    props = page.get("properties", {})
    title = get_title(props)
    existing = get_rich_text(props, "SKU")

    # Skip items that already have a non-UNB SKU
    if existing and not existing.upper().startswith("UNB"):
        return {"page_id": page["id"], "title": title, "existing": existing, "generated": None, "skip": True}

    # BRAND CODE — from Designer relation → SKU Code
    brand_code = "UNB"
    designers = props.get("Designer", {}).get("relation", [])
    if designers:
        dp = fetch_page(designers[0]["id"])
        if dp:
            code = get_rich_text(dp.get("properties", {}), "SKU Code")
            if code:
                brand_code = code

    # MTM override
    sku_rt = props.get("SKU", {}).get("rich_text", [])
    raw = sku_rt[0]["plain_text"].strip() if sku_rt else ""
    if raw.upper().startswith("MTM"):
        brand_code = "MTM"

    # CATEGORY CODE — from "Category (relation)" or "Material Category" or select
    cat_code = get_relation_code(props, "Category (relation)") or \
               get_relation_code(props, "Category relation") or \
               "OTH"

    # Try Category select as fallback
    if cat_code == "OTH":
        cat_sel = props.get("Category", {}).get("select")
        if cat_sel:
            # Map select name to a code via Category DB pages (already cached after first run)
            cat_code = cat_sel["name"][:3].upper()

    # MATERIAL CODE — from Material Category relation → SKU Code
    mat_code = get_relation_code(props, "Material Category") or "MIX"

    # YEAR
    yy = get_year(props)

    # Sequential counter per brand+cat+mat+year
    key = f"{brand_code}-{cat_code}-{mat_code}-{yy}"
    counters[key] = counters.get(key, 0) + 1
    num = str(counters[key]).zfill(3)

    generated = f"{brand_code}-{cat_code}-{mat_code}-{yy}-{num}"
    return {"page_id": page["id"], "title": title, "existing": existing or "", "generated": generated, "skip": False}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Fetching wardrobe items...")
    items = fetch_all_wardrobe_items()
    print(f"  Found {len(items)} items\n")

    print("Building SKUs...")
    counters = {}
    sku_list = [build_sku(page, counters) for page in items]

    needs_sku  = [x for x in sku_list if not x["skip"]]
    has_sku    = [x for x in sku_list if x["skip"]]
    redo_unb   = [x for x in needs_sku if x["existing"].upper().startswith("UNB")]
    new_items  = [x for x in needs_sku if not x["existing"]]

    print(f"{'='*80}")
    print("SKU PREVIEW")
    print(f"{'='*80}")
    print(f"  {'Title':<43} {'Old SKU':<20} {'New SKU'}")
    print(f"  {'-'*78}")
    for item in needs_sku[:50]:
        old = item["existing"] or "<empty>"
        print(f"  {item['title'][:41]:<43} {old:<20} {item['generated']}")
    if len(needs_sku) > 50:
        print(f"  ... and {len(needs_sku) - 50} more")

    print(f"\n  Items to update:        {len(needs_sku)}")
    print(f"    — New (no SKU):       {len(new_items)}")
    print(f"    — Redo (UNB):         {len(redo_unb)}")
    print(f"  Items already OK:       {len(has_sku)}")

    if not needs_sku:
        print("\nAll items are up to date.")
        return

    confirm = input(f"\nWrite {len(needs_sku)} SKUs to Notion? (yes/no): ")
    if confirm.strip().lower() != "yes":
        print("Skipped.")
        return

    print("\nUpdating Notion...")
    updated = 0
    for item in needs_sku:
        r = requests.patch(
            f"https://api.notion.com/v1/pages/{item['page_id']}",
            headers=HEADERS,
            json={"properties": {"SKU": {"rich_text": [{"type": "text", "text": {"content": item["generated"]}}]}}},
        )
        if r.status_code == 200:
            print(f"  ✓ {item['title'][:40]:<42} → {item['generated']}")
            updated += 1
        else:
            print(f"  ✗ Failed: {item['title'][:40]} ({r.status_code})")
        time.sleep(0.15)

    print(f"\nDone. {updated}/{len(needs_sku)} items updated.")


if __name__ == "__main__":
    main()
