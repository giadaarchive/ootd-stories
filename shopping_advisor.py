#!/usr/bin/env python3
"""
shopping_advisor.py — Wardrobe-aware purchase advisor

Usage:
  python shopping_advisor.py <url>                              # single: should I buy this?
  python shopping_advisor.py <url1> <url2>                     # compare two, pick one
  python shopping_advisor.py <url1> <url2> --notion <page_id>  # also post to Notion
  ... --context "I bought it because..."                        # tag "Why I own it" on the page

Supported sources: jp.mercari.com, item.fril.jp
"""

import os
import re
import sys
import requests
import anthropic
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN      = os.environ["NOTION_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ITEMS_DB          = "ad079964-9690-43ae-9fa8-5a4f3ca1a9ee"
WEAR_THRESHOLD    = 30

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# Load tag vocabulary — maps slug → Notion page ID (same DB for wardrobe + deinfluence)
_TAG_MAP_PATH = os.path.join(os.path.dirname(__file__), "tag_id_map.json")
try:
    import json as _json
    with open(_TAG_MAP_PATH) as _f:
        TAG_IDS: dict = _json.load(_f)
except FileNotFoundError:
    TAG_IDS = {}


# ── Scrapers ──────────────────────────────────────────────────────────────────

def _scrape_mercari(page, url):
    page.goto(url, wait_until="networkidle", timeout=30000)
    try:
        page.wait_for_selector('[data-testid="description"]', timeout=8000)
        desc = page.inner_text('[data-testid="description"]')
    except Exception:
        desc = ""

    html = page.content()
    m = re.search(r'"og:title".*?content="(.*?)"', html)
    title = m.group(1).replace(" by メルカリ", "").strip() if m else url

    item_id_m = re.search(r'/item/(m\w+)', url)
    item_id = item_id_m.group(1) if item_id_m else ""

    imgs = list(dict.fromkeys(
        re.findall(r'https://static\.mercdn\.net/item/detail/orig/photos/[^\s"\'\\]+', html)
    ))

    # Probe for additional numbered images when HTML only surfaces one
    if len(imgs) <= 1 and item_id:
        ts_m = re.search(rf'photos/{item_id}_1\.jpg\?(\d+)', html)
        ts = ts_m.group(1) if ts_m else ""
        imgs = []
        for i in range(1, 25):
            img_url = f"https://static.mercdn.net/item/detail/orig/photos/{item_id}_{i}.jpg?{ts}"
            if requests.head(img_url, timeout=5).status_code == 200:
                imgs.append(img_url)
            else:
                break

    return {"title": title, "description": desc, "images": imgs, "url": url}


def _scrape_fril(page, url):
    page.goto(url, wait_until="networkidle", timeout=30000)
    text = page.inner_text("body")
    html = page.content()

    start = text.find("商品説明")
    end   = text.find("商品情報", start)
    desc  = text[start + 4:end].strip() if start >= 0 else ""

    m = re.search(r"<title>(.*?)</title>", html)
    title = m.group(1).strip() if m else url

    folder_m = re.search(r"/img/(\d+)/", html)
    if folder_m:
        fid = folder_m.group(1)
        imgs = list(dict.fromkeys(
            re.findall(rf"https://img\.fril\.jp/img/{fid}/l/[^\s\"'\\]+", html)
        ))
    else:
        imgs = []

    return {"title": title, "description": desc, "images": imgs, "url": url}


def scrape(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page    = browser.new_page()
        if "mercari.com" in url:
            result = _scrape_mercari(page, url)
        elif "fril.jp" in url:
            result = _scrape_fril(page, url)
        else:
            result = {"title": url, "description": "", "images": [], "url": url}
        browser.close()
    return result


# ── Wardrobe loader ───────────────────────────────────────────────────────────

# Non-fashion SKU prefixes to exclude from the outfit analysis
_SKIP_SKUS = {"UNB-OTH-WOD", "UNB-OTH-BCE", "UNB-OTH-CRY", "UNB-OTH-SIN",
              "UNB-OTH-ELE", "UNB-OTH-PAP", "UNB-OTH-BAM", "HDM-OTH-FIN"}

def load_wardrobe():
    items, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        data = requests.post(
            f"https://api.notion.com/v1/databases/{ITEMS_DB}/query",
            headers=NOTION_HEADERS, json=body
        ).json()
        items.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    rows = []
    for item in items:
        p    = item["properties"]
        name = "".join(t["plain_text"] for t in p.get("Second best", {}).get("title", []))
        old  = "".join(t["plain_text"] for t in p.get("Old Title",   {}).get("rich_text", []))
        cat  = (p.get("Category", {}).get("select") or {}).get("name", "")
        sku  = "".join(t["plain_text"] for t in p.get("SKU",         {}).get("rich_text", []))
        label = name or old
        prefix = "-".join(sku.split("-")[:3])
        if label and prefix not in _SKIP_SKUS:
            rows.append(f"{label} | {cat} | {sku}")

    return rows


# ── Claude analysis ───────────────────────────────────────────────────────────

_SYSTEM = """You are a personal stylist and wardrobe analyst for a sophisticated collector.
Her archive spans Italian luxury (Valextra, Ferragamo, Hermès), Japanese designers (Issey Miyake, Mardi Mercredi),
classic European houses (Chanel, Dior, Loewe), and a strong foundation of quality basics.
She is based in Singapore: warm, humid, no seasons — outfits must work in 30°C heat.
She cares deeply about cost-per-wear. Every purchase must realistically reach {threshold} wears.
Be direct, specific, and honest about duplicates or gaps.""".format(threshold=WEAR_THRESHOLD)

def _product_block(product, label=""):
    prefix = f"[{label}] " if label else ""
    return (
        f"{prefix}TITLE: {product['title']}\n"
        f"URL: {product['url']}\n"
        f"DESCRIPTION:\n{product['description'] or '(no description scraped)'}"
    )

def analyse(products, wardrobe_rows):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    wardrobe_text = "\n".join(wardrobe_rows)

    if len(products) == 2:
        product_section = (
            _product_block(products[0], "PRODUCT A") + "\n\n" +
            _product_block(products[1], "PRODUCT B")
        )
        task = f"""TASK — COMPARE AND CHOOSE ONE

For EACH product (A and B):
1. Extract: colour, material, silhouette/style, approximate size
2. List 5 specific outfit ideas using NAMED pieces from the wardrobe above
3. Score versatility 1–10 and estimate realistic wears per year
4. State what gap it fills or what it duplicates

Then write a FINAL RECOMMENDATION: which to buy and why.
Be explicit about the {WEAR_THRESHOLD}-wear threshold. Name the deciding factor."""
    else:
        product_section = _product_block(products[0])
        task = f"""TASK — BUY OR SKIP?

1. Extract: colour, material, silhouette/style, approximate size
2. List 5 specific outfit ideas using NAMED pieces from the wardrobe above
3. Score versatility 1–10 and estimate realistic wears per year
4. Identify any duplicate already in the wardrobe (same function, similar colour/style)
5. VERDICT: Buy / Skip / Maybe — one sentence, tied directly to the {WEAR_THRESHOLD}-wear threshold"""

    messages = [
        {
            "role": "user",
            "content": [
                # Cache the large wardrobe block — it never changes within a session
                {
                    "type": "text",
                    "text": f"WARDROBE (name | category | SKU — {len(wardrobe_rows)} items):\n{wardrobe_text}\n\n---\n\n",
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "type": "text",
                    "text": product_section + "\n\n" + task,
                },
            ],
        }
    ]

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4000,
        system=_SYSTEM,
        messages=messages,
        extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
    )
    return response.content[0].text


# ── Tag inference ─────────────────────────────────────────────────────────────

_TAG_DESCRIPTIONS = {
    "wears-30-plus": (
        "Apply when the buyer explicitly has confidence they will wear this item at least 30 times. "
        "This is distinct from 'versatile' (which is about styling flexibility) — wears-30-plus is "
        "specifically about commitment to the cost-per-wear threshold. Apply when the context shows "
        "the buyer has thought through occasions and is convinced of repeated, long-term use."
    ),
}

def infer_why_i_own_it(context: str) -> list[str]:
    """Use Claude to map free-text purchase context to tag slugs from the tag vocabulary.
    Returns a list of Notion page IDs for matched tags (max 6)."""
    if not TAG_IDS or not context.strip():
        return []

    # Build tag list with descriptions for tags that need disambiguation
    tag_lines = []
    for slug in TAG_IDS.keys():
        desc = _TAG_DESCRIPTIONS.get(slug, "")
        tag_lines.append(f"- {slug}" + (f": {desc}" if desc else ""))
    tag_list = "\n".join(tag_lines)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": (
            f"Purchase context:\n{context}\n\n"
            f"Available tags:\n{tag_list}\n\n"
            "Return ONLY a JSON array of the most relevant 'Why I own it' tag slugs (max 6). "
            "Only include tags that genuinely apply. No explanation, just the JSON array."
        )}]
    )
    raw = resp.content[0].text.strip()
    m = re.search(r'\[.*?\]', raw, re.DOTALL)
    if not m:
        return []
    slugs = _json.loads(m.group(0))
    return [TAG_IDS[s] for s in slugs if s in TAG_IDS]


# ── Notion poster ─────────────────────────────────────────────────────────────

def _make_text_block(line):
    if line.startswith("## "):
        return {"type": "heading_2", "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": line[3:]}}]}}
    if line.startswith("### "):
        return {"type": "heading_3", "heading_3": {
            "rich_text": [{"type": "text", "text": {"content": line[4:]}}]}}
    stripped = line.strip("*").strip()
    bold = line.startswith("**") and line.rstrip().endswith("**")
    return {"type": "paragraph", "paragraph": {
        "rich_text": ([{
            "type": "text",
            "text": {"content": stripped},
            "annotations": {"bold": bold},
        }] if line.strip() else [])
    }}


def post_to_notion(page_id, analysis_text, products, purchase_context: str = ""):
    # Set page icon to first image of first product with images
    first_image = next(
        (img for p in products for img in p["images"] if img),
        None
    )
    patch_props: dict = {}
    if first_image:
        requests.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=NOTION_HEADERS,
            json={"icon": {"type": "external", "external": {"url": first_image}}},
        )

    # If purchase context provided, infer and apply "Why I own it" tags
    if purchase_context and TAG_IDS:
        print("  Inferring 'Why I own it' tags...")
        tag_ids = infer_why_i_own_it(purchase_context)
        if tag_ids:
            patch_props["Why I own it (Tags)"] = {"relation": [{"id": tid} for tid in tag_ids]}
            print(f"  Tags applied: {len(tag_ids)}")

    if patch_props:
        requests.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=NOTION_HEADERS,
            json={"properties": patch_props},
        )

    blocks = []

    # Images first (before any table), grouped by product
    for product in products:
        if product["images"]:
            blocks.append({"type": "heading_2", "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": product["title"][:100]}}]
            }})
            for url in product["images"][:12]:
                blocks.append({"type": "image",
                                "image": {"type": "external", "external": {"url": url}}})

    blocks.append({"type": "divider", "divider": {}})

    for line in analysis_text.split("\n"):
        blocks.append(_make_text_block(line))

    for i in range(0, len(blocks), 100):
        requests.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=NOTION_HEADERS,
            json={"children": blocks[i:i + 100]},
        )


def _extract_page_id(s):
    cleaned = s.replace("-", "")
    m = re.search(r"([a-f0-9]{32})", cleaned)
    return m.group(1) if m else None


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    urls, notion_page, purchase_context = [], None, ""
    i = 0
    while i < len(args):
        if args[i] == "--notion" and i + 1 < len(args):
            notion_page = _extract_page_id(args[i + 1])
            i += 2
        elif args[i] == "--context" and i + 1 < len(args):
            purchase_context = args[i + 1]
            i += 2
        elif not args[i].startswith("--"):
            urls.append(args[i])
            i += 1
        else:
            i += 1

    urls = urls[:2]
    if not urls:
        print("Error: provide at least one product URL.")
        sys.exit(1)

    print("Scraping product(s)...")
    products = []
    for url in urls:
        print(f"  {url}")
        p = scrape(url)
        products.append(p)
        print(f"  → {p['title']}  ({len(p['images'])} photos)")

    print(f"\nLoading wardrobe from Notion...")
    wardrobe = load_wardrobe()
    print(f"  {len(wardrobe)} items")

    print("\nAnalysing with Claude...\n")
    result = analyse(products, wardrobe)

    print("=" * 70)
    print(result)
    print("=" * 70)

    if notion_page:
        print(f"\nPosting to Notion {notion_page}...")
        post_to_notion(notion_page, result, products, purchase_context=purchase_context)
        print("Done.")

    return result


if __name__ == "__main__":
    main()
