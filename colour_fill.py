#!/usr/bin/env python3
"""
Populate empty Colour fields in the Collection DB.

Strategy:
  1. Extract colour from item name using keyword matching (fast, free)
  2. For uncertain items, use Claude Haiku to infer colour from name
  3. Flag anything still uncertain for manual review
  4. Write confirmed colours back to Notion

Colour vocabulary — matches how Claude Sonnet describes photos:
  White family  : white, ivory, cream, off-white, ecru
  Grey family   : light grey, grey, charcoal, silver
  Black         : black
  Neutral warm  : beige, sand, stone, camel, tan, taupe, khaki
  Brown family  : brown, chocolate, cognac, rust, cognac
  Blue family   : navy, midnight blue, cobalt, royal blue, sky blue, teal, denim
  Green family  : emerald, forest green, olive, sage, mint
  Red family    : red, burgundy, wine, cherry, tomato
  Pink family   : hot pink, pink, blush, salmon, coral, rose, mauve
  Purple family : purple, violet, plum, lavender, lilac
  Yellow/orange : yellow, mustard, golden, amber, orange, apricot
  Metallic      : gold, silver, bronze, rose gold, platinum
  Pattern       : multicolour, floral, print, stripe, check, monogram

Run:
  python3 colour_fill.py --dry-run     # preview without writing
  python3 colour_fill.py               # write to Notion
  python3 colour_fill.py --uncertain   # show only items needing manual review
"""

import os, sys, re, json, time, requests, argparse
import anthropic
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
COLLECTION_DB_ID = "ad079964-9690-43ae-9fa8-5a4f3ca1a9ee"
NOTION_H = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

client = anthropic.Anthropic()

# ── Keyword colour extraction ──────────────────────────────────────────────────

COLOUR_KEYWORDS = {
    # exact multi-word first
    "off-white":     ["off-white", "off white"],
    "midnight blue": ["midnight blue"],
    "forest green":  ["forest green"],
    "royal blue":    ["royal blue"],
    "sky blue":      ["sky blue"],
    "baby blue":     ["baby blue"],
    "rose gold":     ["rose gold"],
    "hot pink":      ["hot pink"],
    "dark green":    ["dark green"],
    "light grey":    ["light grey", "light gray"],
    "dark grey":     ["dark grey", "dark gray", "dark grey"],
    "light blue":    ["light blue"],
    # single-word
    "black":     ["black", "blk", "noir"],
    "white":     ["white", "wht"],
    "ivory":     ["ivory", "ivoire"],
    "cream":     ["cream", "crm"],
    "ecru":      ["ecru"],
    "grey":      ["grey", "gray", "gris"],
    "charcoal":  ["charcoal"],
    "silver":    ["silver", "argent"],
    "beige":     ["beige"],
    "sand":      ["sand"],
    "stone":     ["stone"],
    "camel":     ["camel"],
    "tan":       ["tan"],
    "taupe":     ["taupe"],
    "khaki":     ["khaki"],
    "brown":     ["brown", "brun", "marron"],
    "chocolate": ["chocolate"],
    "cognac":    ["cognac"],
    "rust":      ["rust"],
    "navy":      ["navy"],
    "cobalt":    ["cobalt"],
    "teal":      ["teal"],
    "denim":     ["denim"],
    "blue":      ["blue", "bleu", "blau"],
    "emerald":   ["emerald"],
    "olive":     ["olive"],
    "sage":      ["sage"],
    "mint":      ["mint"],
    "green":     ["green", "vert"],
    "red":       ["red", "rouge", "rosso"],
    "burgundy":  ["burgundy", "bordo"],
    "wine":      ["wine"],
    "cherry":    ["cherry"],
    "tomato":    ["tomato"],
    "pink":      ["pink", "rose", "rosa"],
    "blush":     ["blush"],
    "salmon":    ["salmon"],
    "coral":     ["coral"],
    "mauve":     ["mauve"],
    "magenta":   ["magenta"],
    "purple":    ["purple", "violet"],
    "plum":      ["plum"],
    "lavender":  ["lavender"],
    "lilac":     ["lilac"],
    "yellow":    ["yellow", "jaune"],
    "mustard":   ["mustard"],
    "golden":    ["golden", "gold"],  # 'gold' only as colour, not material
    "amber":     ["amber"],
    "orange":    ["orange"],
    "apricot":   ["apricot"],
    "gold":      ["gold"],
    "bronze":    ["bronze"],
    "platinum":  ["platinum"],
    "multicolour": ["multicolour", "multicolor", "multi", "mix", "mixed", "pattern",
                    "floral", "stripe", "striped", "check", "plaid", "tweed",
                    "print", "printed", "monogram"],
}

# Phrases that are NOT colours even though they contain colour words
EXCLUSIONS = ["golden ratio", "golden gate", "rose hip", "green tea", "pink elephant"]


SKU_COLOUR_CODES = {
    "BLK": "black", "WHT": "white", "IVR": "ivory", "CRM": "cream",
    "GRY": "grey", "SLV": "silver", "BEG": "beige", "CML": "camel",
    "TAN": "tan", "BRN": "brown", "CHC": "chocolate", "RST": "rust",
    "NVY": "navy", "BLU": "blue", "MNB": "midnight blue", "TL": "teal",
    "EMR": "emerald", "OLV": "olive", "GRN": "green", "RED": "red",
    "BRG": "burgundy", "WIN": "wine", "PNK": "pink", "CRL": "coral",
    "MVE": "mauve", "PRP": "purple", "PPL": "purple", "LVN": "lavender",
    "YLW": "yellow", "MST": "mustard", "GLD": "gold", "ORG": "orange",
    "MUL": "multicolour", "MIX": "multicolour", "STR": "natural",
    "WIC": "natural", "LIN": "natural", "ORN": "orange", "ORAN": "orange",
    "FLR": "multicolour", "CRY": "crystal",
}

def sku_colour(sku: str) -> str | None:
    """Extract colour from SKU code segments."""
    parts = sku.upper().split("-")
    for part in parts[2:]:  # skip brand and category
        if part in SKU_COLOUR_CODES:
            return SKU_COLOUR_CODES[part]
    return None


def keyword_colour(name: str) -> str | None:
    name_lower = name.lower()
    for phrase in EXCLUSIONS:
        if phrase in name_lower:
            return None
    # Try multi-word first (longer matches win)
    for colour, keywords in COLOUR_KEYWORDS.items():
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', name_lower):
                return colour
    return None


# ── Haiku fallback for uncertain items ────────────────────────────────────────

def haiku_colour(items_batch: list[dict]) -> dict[str, str]:
    """
    Ask Haiku to identify primary colour for a batch of items.
    Returns {item_id: colour_string or "UNCERTAIN"}.
    """
    lines = [f'{i}. [{it["id"]}] {it["name"]}' for i, it in enumerate(items_batch)]
    prompt = (
        "For each clothing/accessory item below, identify the PRIMARY colour. "
        "Use only these terms: black, white, ivory, cream, off-white, grey, charcoal, "
        "silver, beige, stone, camel, tan, taupe, brown, chocolate, cognac, rust, "
        "navy, midnight blue, cobalt, royal blue, sky blue, teal, blue, emerald, "
        "forest green, olive, sage, green, red, burgundy, wine, pink, blush, coral, "
        "mauve, purple, plum, lavender, lilac, yellow, mustard, golden, orange, "
        "gold, bronze, multicolour.\n"
        "If the colour cannot be determined from the name alone, write UNCERTAIN.\n"
        "Reply ONLY with a JSON object: {\"0\": \"colour\", \"1\": \"colour\", ...}\n\n"
        + "\n".join(lines)
    )
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```\s*$', '', raw)
    try:
        result = json.loads(raw)
        return {items_batch[int(k)]["id"]: v for k, v in result.items()}
    except Exception as e:
        print(f"  [warn] Haiku parse failed: {e} — {raw[:200]}")
        return {}


# ── Notion fetch + write ───────────────────────────────────────────────────────

def fetch_all_items() -> list[dict]:
    items, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        r = requests.post(
            f"https://api.notion.com/v1/databases/{COLLECTION_DB_ID}/query",
            headers=NOTION_H, json=body, timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        for page in data["results"]:
            p = page["properties"]
            name = "".join(t.get("plain_text", "") for t in p.get("Second best", {}).get("title", []))
            if not name:
                name = "".join(t.get("plain_text", "") for t in p.get("Old Title", {}).get("rich_text", []))
            colour = "".join(t.get("plain_text", "") for t in p.get("Primary Colour", {}).get("rich_text", []))
            if not colour:
                colour = "".join(t.get("plain_text", "") for t in p.get("Colour Detail", {}).get("rich_text", []))
            sku = "".join(t.get("plain_text", "") for t in p.get("SKU", {}).get("rich_text", []))
            items.append({"id": page["id"], "name": name, "colour": colour, "sku": sku})
        if not data.get("has_more"):
            break
        cursor = data["next_cursor"]
        time.sleep(0.35)
    return items


def write_colour(page_id: str, colour: str, dry_run: bool = False) -> bool:
    if dry_run:
        return True
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=NOTION_H,
        json={"properties": {"Primary Colour": {"rich_text": [{"type": "text", "text": {"content": colour}}]}}},
        timeout=15,
    )
    time.sleep(0.35)
    return r.status_code == 200


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to Notion")
    parser.add_argument("--uncertain", action="store_true", help="Show only items needing manual review")
    args = parser.parse_args()

    print("Fetching collection items...")
    all_items = fetch_all_items()
    missing = [i for i in all_items if not i["colour"].strip()]
    print(f"  {len(all_items)} total items, {len(missing)} missing colour\n")

    # Non-clothing items to skip (furniture, luggage, tech)
    skip_skus = {"OTH", "LNG"}  # OTH = other/furniture, LNG = lingerie (often skip)
    # Actually let's include LNG since lingerie has colour
    skip_skus = {"OTH"}

    results = {
        "keyword": [],    # confident from name keywords
        "haiku": [],      # confident from Haiku
        "uncertain": [],  # needs manual review
        "skipped": [],    # non-clothing
    }

    # ── Pass 1: keyword extraction ──
    haiku_queue = []
    for item in missing:
        sku_cat = item["sku"].split("-")[1] if len(item["sku"].split("-")) >= 2 else ""
        if sku_cat in skip_skus or not item["name"].strip():
            results["skipped"].append(item)
            continue
        colour = keyword_colour(item["name"]) or sku_colour(item["sku"])
        if colour:
            results["keyword"].append({**item, "inferred_colour": colour})
        else:
            haiku_queue.append(item)

    # ── Pass 2: Haiku for remainder ──
    if haiku_queue:
        print(f"  Running Haiku on {len(haiku_queue)} uncertain items...")
        batch_size = 20
        haiku_map = {}
        for i in range(0, len(haiku_queue), batch_size):
            batch = haiku_queue[i:i + batch_size]
            haiku_map.update(haiku_colour(batch))
            time.sleep(0.5)

        for item in haiku_queue:
            colour = haiku_map.get(item["id"], "UNCERTAIN")
            if colour and colour != "UNCERTAIN":
                results["haiku"].append({**item, "inferred_colour": colour})
            else:
                results["uncertain"].append(item)

    # ── Report ──
    if args.uncertain:
        print(f"\n{'─'*70}")
        print(f"NEEDS MANUAL REVIEW ({len(results['uncertain'])} items):")
        print(f"{'─'*70}")
        for item in results["uncertain"]:
            print(f"  {item['sku']:30s} {item['name'][:60]}")
        return

    print(f"\nSummary:")
    print(f"  Keyword match : {len(results['keyword'])}")
    print(f"  Haiku match   : {len(results['haiku'])}")
    print(f"  Uncertain     : {len(results['uncertain'])}")
    print(f"  Skipped       : {len(results['skipped'])}")
    if args.dry_run:
        print(f"\n[DRY RUN — no changes written]\n")

    confident = results["keyword"] + results["haiku"]
    print(f"\nWriting {len(confident)} colours to Notion...")
    written, failed = 0, 0
    for item in confident:
        colour = item["inferred_colour"]
        ok = write_colour(item["id"], colour, dry_run=args.dry_run)
        status = "✓" if ok else "✗"
        if not args.dry_run:
            print(f"  {status} {colour:20s} ← {item['name'][:50]}")
        else:
            print(f"  → {colour:20s} ← {item['name'][:50]}")
        if ok:
            written += 1
        else:
            failed += 1

    print(f"\nDone. {written} written, {failed} failed.")

    if results["uncertain"]:
        print(f"\n{'─'*70}")
        print(f"NEEDS YOUR REVIEW ({len(results['uncertain'])} items) — run with --uncertain to list:")
        for item in results["uncertain"][:10]:
            print(f"  {item['sku']:30s} {item['name'][:55]}")
        if len(results["uncertain"]) > 10:
            print(f"  ... and {len(results['uncertain']) - 10} more")


if __name__ == "__main__":
    main()
