#!/usr/bin/env python3
"""
Step 2 & 3: Generate SKU codes for Category and Material Category databases.
Run this before generate_skus.py.
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

CATEGORY_DB  = "2eaccd15cda18056a4f6c42c62c33851"
MATERIAL_DB  = "d9f03692734141b7b5fa917cd6b37530"

# Suggested codes — edit before confirming if you want different ones
CATEGORY_SUGGESTIONS = {
    "Tops & Shirts":           "TOP",
    "Hat & Gloves":            "HAT",
    "Trousers & Shorts & Skirts": "TRS",
    "Bag":                     "BAG",
    "Outerwear":               "OUT",
    "Jumpsuits & Rompers":     "JMP",
    "Eyewear":                 "EYE",
    "Scarf, Shawl, Stoles":    "SCF",
    "Jewellery & Watches":     "JEW",
    "Lingerie":                "LNG",
    "Dresses":                 "DRS",
    "Shoes":                   "SHO",
}

SKIP_WORDS = {"the", "de", "la", "le", "di", "and", "&", "of", "for"}


def auto_code(name):
    words = [w for w in name.split() if w.lower() not in SKIP_WORDS and w.isalpha()]
    if not words:
        return name[:3].upper()
    if len(words) == 1:
        return words[0][:3].upper()
    initials = "".join(w[0] for w in words[:4]).upper()
    return initials[:3] if len(initials) >= 3 else words[0][:3].upper()


def get_title(props):
    tp = next((v for v in props.values() if v.get("type") == "title"), None)
    return tp["title"][0].get("plain_text", "").strip() if tp and tp.get("title") else ""


def get_rich_text(props, key):
    rt = props.get(key, {}).get("rich_text", [])
    return rt[0]["plain_text"].strip() if rt else ""


def process_database(db_id, db_label, title_key="SKU Code", suggestions=None):
    print(f"\n{'='*60}")
    print(f"  {db_label}")
    print(f"{'='*60}")

    r = requests.post(
        f"https://api.notion.com/v1/databases/{db_id}/query",
        headers=HEADERS,
        json={"page_size": 100},
    )
    if r.status_code == 404:
        print(f"  ERROR: Database not accessible.")
        print(f"  → Share it with the 'OOTD Story' integration in Notion first.")
        return False
    r.raise_for_status()

    pages = r.json().get("results", [])
    print(f"  Found {len(pages)} entries")

    needs_code, has_code = [], []
    used_codes = set()

    for page in pages:
        props = page["properties"]
        name = get_title(props)
        existing = get_rich_text(props, title_key)
        if existing:
            has_code.append(name)
            used_codes.add(existing.upper())
        else:
            needs_code.append({"page_id": page["id"], "name": name})

    if not needs_code:
        print(f"  All entries already have codes.")
        return True

    # Generate codes
    for item in needs_code:
        code = (suggestions or {}).get(item["name"]) or auto_code(item["name"])
        original = code
        suffix = 2
        while code in used_codes:
            code = original[:2] + str(suffix)
            suffix += 1
        used_codes.add(code)
        item["generated"] = code

    print(f"\n  {'Name':<40} {'Code'}")
    print(f"  {'-'*50}")
    for item in needs_code:
        print(f"  {item['name']:<40} {item['generated']}")

    confirm = input(f"\n  Write these {len(needs_code)} codes to Notion? (yes/no): ")
    if confirm.strip().lower() != "yes":
        print("  Skipped.")
        return True

    for item in needs_code:
        r2 = requests.patch(
            f"https://api.notion.com/v1/pages/{item['page_id']}",
            headers=HEADERS,
            json={"properties": {title_key: {"rich_text": [{"type": "text", "text": {"content": item["generated"]}}]}}},
        )
        status = "✓" if r2.status_code == 200 else "✗"
        print(f"  {status} {item['name']} → {item['generated']}")
        time.sleep(0.15)

    return True


def main():
    print("Setting up SKU codes for Category and Material databases.\n")

    process_database(CATEGORY_DB, "STEP 2: Category Database", suggestions=CATEGORY_SUGGESTIONS)
    process_database(MATERIAL_DB, "STEP 3: Material Category Database")

    print("\nDone. Run generate_skus.py next to write item SKUs.")


if __name__ == "__main__":
    main()
