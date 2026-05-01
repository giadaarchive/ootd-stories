#!/usr/bin/env python3
"""
Generate SEO-optimized, editorial titles for collection items.

Formula: [Brand] [Model/Style] [Item Type] — [Material], [Colour], [Era if notable]

Usage:
  python3 retitle.py --recent 20           # retitle 20 most recently added items
  python3 retitle.py --force <page_id>     # retitle one specific page
  python3 retitle.py --recent 20 --dry-run # preview without writing
  python3 retitle.py --recent 20 --model llama
"""

import os
import json
import time
import requests
from dotenv import load_dotenv
import llm as llm_module

load_dotenv()

NOTION_TOKEN     = os.environ["NOTION_TOKEN"]
COLLECTION_DB_ID = "ad079964969043ae9fa85a4f3ca1a9ee"
NOTION_HEADERS   = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

DEFAULT_MODEL = "qwen/qwen-2.5-72b-instruct"  # structured title generation — Qwen matches Claude quality at fraction of cost
MODEL_ALIASES = llm_module.MODEL_ALIASES

HERITAGE_MARKER = "Heritage & House Notes"


def clean_boilerplate_blocks(page_id):
    """Delete every non-image block before Heritage & House Notes."""
    raw_id = page_id.replace("-", "")
    pid = f"{raw_id[:8]}-{raw_id[8:12]}-{raw_id[12:16]}-{raw_id[16:20]}-{raw_id[20:]}"
    r = requests.get(f"https://api.notion.com/v1/blocks/{pid}/children", headers=NOTION_HEADERS)
    if r.status_code != 200:
        return 0
    blocks = r.json().get("results", [])
    to_delete = []
    for b in blocks:
        btype = b["type"]
        rt = b.get(btype, {}).get("rich_text", [])
        tx = "".join(x.get("plain_text", "") for x in rt)
        if btype == "heading_2" and HERITAGE_MARKER in tx:
            break
        if btype != "image":
            to_delete.append(b["id"])
    for bid in to_delete:
        requests.delete(f"https://api.notion.com/v1/blocks/{bid}", headers=NOTION_HEADERS)
        time.sleep(0.15)
    if to_delete:
        print(f"     Cleaned {len(to_delete)} non-image block(s) before Heritage")
    return len(to_delete)


# ── Prompts ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You write SEO-optimized, editorial product titles for a luxury archive fashion shop.

FORMULA: [Brand] [Model Name] [Item Type] — [Material], [Colour], [Era/CD if notable]

RULES:
- Brand name first, spelled correctly with accents (Hermès, not Hermes)
- Use the official model name if known (Birkin 25, Tuileries Hobo, Cannes MM, Classic Flap)
- Item type only if model name doesn't make it obvious
- Em dash (—) before material/colour details
- Colour: one word, most distinctive colour only
- Era or creative director only if it adds real value (Galliano era, Raf Simons, 1990s archive)
- Max 80 characters total
- Title case throughout

STRIP COMPLETELY:
- Japanese resale boilerplate: "2WAY", "Hand/Shoulder", "[Used]", "Made in Italy", serial numbers
- Condition language: "Excellent condition", "Rank B", "signs of use"
- Listing noise: "[Rare and high-end item]", "Free Shipping", "(xav's)", "(elephant)"
- Duplicate brand names: "VALEXTRA Valextra" → "Valextra"
- ALL CAPS brand names: "HERMES" → "Hermès"
- Measurement specs: width/height/depth, weight in grams

EXAMPLES (input → output):
  "Wool Knit Turtleneck Top Christian Dior Black"
  → "Christian Dior Ribbed Turtleneck — Black Wool"

  "VALEXTRA Valextra Mini Iside 2-Way Bag Hand/Shoulder Black Leather Made in Italy Nº 5053"
  → "Valextra Mini Iside — Black Leather"

  "Hermes Cannes MM Tote Bag Handbag Canvas Red"
  → "Hermès Cannes MM Tote — Red Canvas"

  "90s 00s Oscar de la Renta tailored jacket blazer corduroy navy outer jacket 100% wool vintage"
  → "Oscar de la Renta Blazer — Navy Corduroy, 1990s Archive"

  "HERMES / Hermes Lambskin Piping Corduroy Trousers Vintage Archive Piece Navy Size M"
  → "Hermès Trousers — Navy Lambskin Piping, Vintage Archive"

  "Louis Vuitton Tuileries Hobo bag made from signature Monogram canvas with red leather accents"
  → "Louis Vuitton Tuileries Hobo — Monogram Canvas, Red Leather"

Return ONLY valid JSON: {"title": "..."}
Nothing else.\
"""


def build_prompt(current_title, brand, material, year, description):
    parts = [f"Current title: {current_title}"]
    if brand and brand != "Unknown":
        parts.append(f"Brand: {brand}")
    if material:
        parts.append(f"Material: {material}")
    if year:
        parts.append(f"Year made: {year}")
    if description:
        parts.append(f"Description: {description[:500]}")
    return "\n".join(parts)


# ── Notion helpers ────────────────────────────────────────────────────────────

def get_recent_items(n):
    r = requests.post(
        f"https://api.notion.com/v1/databases/{COLLECTION_DB_ID}/query",
        headers=NOTION_HEADERS,
        json={
            "page_size": min(n, 100),
            "sorts": [{"timestamp": "created_time", "direction": "descending"}],
        },
    )
    r.raise_for_status()
    return r.json().get("results", [])


def get_page(page_id):
    raw_id = page_id.replace("-", "")
    pid = f"{raw_id[:8]}-{raw_id[8:12]}-{raw_id[12:16]}-{raw_id[16:20]}-{raw_id[20:]}"
    r = requests.get(f"https://api.notion.com/v1/pages/{pid}", headers=NOTION_HEADERS)
    r.raise_for_status()
    return r.json()


def extract_details(page):
    props = page["properties"]
    title_prop = next((v for v in props.values() if v.get("type") == "title"), None)
    current_title = (
        title_prop["title"][0].get("plain_text", "")
        if title_prop and title_prop.get("title")
        else ""
    )
    year_date = props.get("Year It's Made (first hand)", {}).get("date", {})
    year = year_date.get("start", "")[:4] if year_date else ""
    material_rt = props.get("Material", {}).get("rich_text", [])
    material = material_rt[0]["plain_text"] if material_rt else ""
    return {"title": current_title, "year": year, "material": material}


def get_brand(page):
    from heritage import get_brand_for_page
    brand, _ = get_brand_for_page(page)
    return brand


def read_description(page_id):
    raw_id = page_id.replace("-", "")
    pid = f"{raw_id[:8]}-{raw_id[8:12]}-{raw_id[12:16]}-{raw_id[16:20]}-{raw_id[20:]}"
    r = requests.get(f"https://api.notion.com/v1/blocks/{pid}/children", headers=NOTION_HEADERS)
    if r.status_code != 200:
        return ""
    lines = []
    for b in r.json().get("results", []):
        if b.get("type") == "paragraph":
            rt = b["paragraph"].get("rich_text", [])
            text = "".join(x.get("plain_text", "") for x in rt).strip()
            if text and len(text) > 5:
                lines.append(text)
        if len(lines) >= 8:
            break
    return "\n".join(lines)


def update_title(page_id, new_title):
    raw_id = page_id.replace("-", "")
    pid = f"{raw_id[:8]}-{raw_id[8:12]}-{raw_id[12:16]}-{raw_id[16:20]}-{raw_id[20:]}"
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{pid}",
        headers=NOTION_HEADERS,
        json={
            "properties": {
                "Shop Title": {
                    "rich_text": [{"type": "text", "text": {"content": new_title}}]
                }
            }
        },
    )
    r.raise_for_status()


# ── Core ──────────────────────────────────────────────────────────────────────

def retitle(page, model=DEFAULT_MODEL, dry_run=False):
    details = extract_details(page)
    current = details["title"]
    if not current:
        print("     No title — skipping")
        return "skipped"

    if not dry_run:
        clean_boilerplate_blocks(page["id"])

    desc = read_description(page["id"])

    # Get brand name
    designer_rel = page.get("properties", {}).get("Designer", {}).get("relation", [])
    brand = "Unknown"
    if designer_rel:
        did = designer_rel[0].get("id", "")
        r = requests.get(f"https://api.notion.com/v1/pages/{did}", headers=NOTION_HEADERS)
        if r.status_code == 200:
            props = r.json().get("properties", {})
            t = next((v for v in props.values() if v.get("type") == "title"), None)
            if t and t.get("title"):
                brand = t["title"][0].get("plain_text", "Unknown")

    user_msg = build_prompt(current, brand, details["material"], details["year"], desc)
    raw = llm_module.call(SYSTEM_PROMPT, user_msg, max_tokens=100, model=model)

    # Parse JSON
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    result = json.loads(raw)
    new_title = result["title"].strip()

    print(f"     OLD: {current}")
    print(f"     NEW: {new_title}")

    if not dry_run:
        update_title(page["id"], new_title)
        print("     ✓ Updated")
    else:
        print("     (dry-run — not written)")

    return "done"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate SEO-optimized titles for collection items")
    parser.add_argument("--force",   metavar="PAGE_ID", help="Retitle one specific page")
    parser.add_argument("--recent",  metavar="N", type=int, help="Retitle N most recently added items")
    parser.add_argument("--dry-run", action="store_true", help="Preview titles without writing to Notion")
    parser.add_argument("--model",   metavar="MODEL", default=DEFAULT_MODEL,
                        help=f"Model alias or full ID. Default: {DEFAULT_MODEL}")
    args = parser.parse_args()

    model = MODEL_ALIASES.get(args.model, args.model)
    dry_label = " [DRY RUN]" if args.dry_run else ""
    print(f"Model: {model}{dry_label}\n")

    done = skipped = errors = 0

    if args.force:
        page = get_page(args.force)
        details = extract_details(page)
        print(f"  → {details['title']!r}")
        try:
            retitle(page, model=model, dry_run=args.dry_run)
            done += 1
        except Exception as e:
            print(f"     ERROR: {e}")
            errors += 1
        return

    if args.recent:
        pages = get_recent_items(args.recent)
        print(f"{len(pages)} items\n")
        for page in pages:
            details = extract_details(page)
            print(f"  → {details['title'][:70]!r}")
            try:
                result = retitle(page, model=model, dry_run=args.dry_run)
                if result == "done":
                    done += 1
                else:
                    skipped += 1
                time.sleep(0.5)
            except Exception as e:
                print(f"     ERROR: {e}")
                errors += 1
                time.sleep(1)
        print(f"\nDone. {done} retitled, {skipped} skipped, {errors} errors.")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
