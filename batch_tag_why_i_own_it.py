#!/usr/bin/env python3
"""
batch_tag_why_i_own_it.py — Mass-infer and apply "Why I own it" tags to wardrobe items.

Usage:
  python3 batch_tag_why_i_own_it.py              # dry run
  python3 batch_tag_why_i_own_it.py --apply      # write to Notion
  python3 batch_tag_why_i_own_it.py --apply --limit 50
"""

import os, re, sys, json, time, requests, anthropic
from dotenv import load_dotenv
load_dotenv()

NOTION_TOKEN      = os.environ["NOTION_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ITEMS_DB          = "ad079964-9690-43ae-9fa8-5a4f3ca1a9ee"

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

with open(os.path.join(os.path.dirname(__file__), "tag_id_map.json")) as f:
    TAG_IDS: dict = json.load(f)

# Only positive "why I own it" tags — exclude deinfluence/negative tags
POSITIVE_TAGS = {
    "30-plus-wears", "brand-discovery", "brand-legacy", "colour", "condition",
    "craftsmanship", "gifted", "investment-piece", "love-the-designer",
    "natural-patina", "pattern-integrity", "price", "rare-find", "sentimental",
    "timeless-silhouette", "travel-worthy", "versatile", "vintage-provenance",
}

_TAG_DESCRIPTIONS = {
    "30-plus-wears":      "Item is a versatile daily-use piece with strong evidence of 30+ wears — basics, everyday shoes, frequently worn bags.",
    "brand-discovery":    "First piece from this brand — bought to explore or research the designer.",
    "brand-legacy":       "Bought for the brand's heritage, history, or prestige (e.g. Hermès, Chanel, Ferragamo).",
    "colour":             "The colour itself was the primary reason — a specific, striking, or hard-to-find shade.",
    "condition":          "Exceptional pre-owned condition was a deciding factor.",
    "craftsmanship":      "Bought for the quality of construction — stitching, material, hardware, structure.",
    "gifted":             "Received as a gift (price paid = SGD 0).",
    "investment-piece":   "Bought as a long-term value hold — classic or appreciating piece.",
    "love-the-designer":  "Personal affinity for the specific designer or creative director.",
    "natural-patina":     "Bought specifically for the leather/material's ageing quality — patina, character.",
    "pattern-integrity":  "The print, pattern, or motif was the primary draw.",
    "price":              "Acquired at a significant discount to retail — excellent value purchase.",
    "rare-find":          "Hard to find, limited edition, or one-of-a-kind piece.",
    "sentimental":        "Emotional or heritage connection — family, cultural identity, memory.",
    "timeless-silhouette":"Classic, enduring cut or shape — not trend-dependent.",
    "travel-worthy":      "Compact, packable, or particularly suited for travel.",
    "versatile":          "Styles across multiple occasions, dress codes, or outfit combinations.",
    "vintage-provenance": "Pre-owned or vintage piece valued for its history or era.",
}

# Non-fashion item patterns — skip these entirely
_NON_FASHION_NAMES = re.compile(
    r'whisky|whiskey|scotch|bourbon|laphroaig|lagavulin|macallan|wine|spirits|decanter|'
    r'dinner plate|bread.*plate|china plate|flatware|cutlery|silverware|crystal.*glass|'
    r'wine glass|claret|vase|paperweight|figurine|'
    r'pressure cooker|food processor|appliance|kettle|'
    r'bamboo.*sheet|bedding|pillow|'
    r'loose.*diamond|diamond.*loose|fancy.*diamond|diamond.*fancy',
    re.IGNORECASE
)
_NON_FASHION_SKU_CATS = {'WOD', 'DIA'}  # wood furniture, loose diamonds

# Items where SGD=0 always means gifted (confirmed rule)
GIFTED_ALWAYS_IF_ZERO_SGD = True


def is_fashion_item(name: str, sku_cat: str) -> bool:
    if sku_cat in _NON_FASHION_SKU_CATS:
        return False
    if _NON_FASHION_NAMES.search(name):
        return False
    return True


def build_tag_list():
    lines = []
    for slug in POSITIVE_TAGS:
        if slug not in TAG_IDS:
            continue
        desc = _TAG_DESCRIPTIONS.get(slug, "")
        lines.append(f"- {slug}: {desc}")
    return "\n".join(lines)


TAG_LIST = build_tag_list()


def infer_tags(name: str, brand: str, category: str, sgd: float, retail_usd: float) -> list[str]:
    forced = []
    if GIFTED_ALWAYS_IF_ZERO_SGD and sgd == 0:
        forced.append("gifted")

    savings_note = ""
    if retail_usd > 0 and sgd > 0:
        retail_sgd = retail_usd * 1.35
        if sgd < retail_sgd * 0.4:
            savings_note = f" Paid SGD {sgd:.0f} vs retail ~SGD {retail_sgd:.0f} — significant discount."

    prompt = (
        f"Fashion item: {name}\n"
        f"Brand code: {brand}  |  Category tier: {category}\n"
        f"Price paid: SGD {sgd:.0f}{savings_note}\n\n"
        f"Available 'Why I own it' tags:\n{TAG_LIST}\n\n"
        "Return a JSON array of the most relevant tag slugs (max 4). "
        "Only include tags that clearly apply from the metadata. "
        f"Do NOT include 'gifted' (handled separately). "
        "No explanation, just the JSON array."
    )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    m = re.search(r'\[.*?\]', raw, re.DOTALL)
    inferred = []
    if m:
        slugs = json.loads(m.group(0))
        inferred = [s for s in slugs if s in TAG_IDS and s in POSITIVE_TAGS and s != "gifted"]

    all_slugs = list(dict.fromkeys(forced + inferred))  # dedupe, forced first
    return [TAG_IDS[s] for s in all_slugs if s in TAG_IDS]


def get_text(prop):
    return "".join(t["plain_text"] for t in prop) if prop else ""


def fetch_items():
    items, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        data = requests.post(
            f"https://api.notion.com/v1/databases/{ITEMS_DB}/query",
            headers=NOTION_HEADERS, json=body,
        ).json()
        items.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return items


def main():
    apply = "--apply" in sys.argv
    limit_idx = next((i for i, a in enumerate(sys.argv) if a == "--limit"), None)
    limit = int(sys.argv[limit_idx + 1]) if limit_idx and limit_idx + 1 < len(sys.argv) else None

    print("Fetching wardrobe items...")
    all_items = fetch_items()

    to_tag = []
    skipped_non_fashion = 0
    for item in all_items:
        p = item["properties"]
        if p.get("with/for mum", {}).get("checkbox"):
            continue
        existing = p.get("Why I own it (Tags)", {}).get("relation", [])
        if existing:
            continue
        name = get_text(p.get("Second best", {}).get("title", [])) or \
               get_text(p.get("Old Title", {}).get("rich_text", []))
        if not name:
            continue
        sku     = get_text(p.get("SKU", {}).get("rich_text", []))
        parts   = sku.split("-")
        brand   = parts[0] if parts else "UNK"
        sku_cat = parts[1] if len(parts) >= 2 else "UNK"
        cat     = (p.get("Category", {}).get("select") or {}).get("name", "")
        sgd     = p.get("SGD", {}).get("number") or 0
        retail  = p.get("Retail Price (USD)", {}).get("number") or 0

        if not is_fashion_item(name, sku_cat):
            skipped_non_fashion += 1
            continue

        to_tag.append({"id": item["id"], "name": name, "brand": brand, "sku_cat": sku_cat,
                        "cat": cat, "sgd": sgd, "retail": retail})

    if limit:
        to_tag = to_tag[:limit]

    print(f"Items to tag: {len(to_tag)}  (skipped {skipped_non_fashion} non-fashion items)")
    print(f"Mode: {'APPLY (writing to Notion)' if apply else 'DRY RUN (no writes)'}\n")

    applied = 0
    for i, item in enumerate(to_tag):
        print(f"[{i+1}/{len(to_tag)}] {item['name'][:60]}")
        try:
            tag_ids = infer_tags(item["name"], item["brand"], item["cat"],
                                 item["sgd"], item["retail"])
            if not tag_ids:
                print(f"         → no tags inferred, skipping")
                continue

            slugs = [s for s, tid in TAG_IDS.items() if tid in tag_ids]
            print(f"         → {slugs}")

            if apply:
                requests.patch(
                    f"https://api.notion.com/v1/pages/{item['id']}",
                    headers=NOTION_HEADERS,
                    json={"properties": {
                        "Why I own it (Tags)": {"relation": [{"id": tid} for tid in tag_ids]}
                    }},
                    timeout=15,
                ).raise_for_status()
                applied += 1
                time.sleep(0.35)

        except Exception as e:
            print(f"         → ERROR: {e}")

    print(f"\nDone. {'Applied' if apply else 'Would apply'} tags to {applied if apply else len(to_tag)} items.")
    if not apply:
        print("Run with --apply to write to Notion.")


if __name__ == "__main__":
    main()
