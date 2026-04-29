#!/usr/bin/env python3
"""
Audit and enrich heritage notes on L's collection item pages.

For each item that already has "Heritage & House Notes":
  1. Extracts the "Design Language" and "This Piece" text from the page blocks.
  2. If the "Craft & Materials" section is missing (item was written by the old heritage.py),
     generates and appends it.
  3. Adds a "Verification & Sources" section with:
       - Fact-check status for specific claims (✓ Confirmed / ~ Approximate / ? Uncertain)
       - Reference URLs for the design language and piece-specific facts.

Skips pages that already have "Verification & Sources".
Run this after heritage.py has written content to pages.
"""

import json
import os
import time
import requests
from dotenv import load_dotenv
from llm_client import LLMClient

load_dotenv()

NOTION_TOKEN     = os.environ["NOTION_TOKEN"]
COLLECTION_DB_ID = "ad079964969043ae9fa85a4f3ca1a9ee"
NOTION_HEADERS   = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

TARGET_DESIGNERS = {
    "Hermès":               "2b9ccd15-cda1-80fe-9888-dabde81bb8b1",
    "Christian Dior":       "33c5aada-5e92-44d7-9dcb-747e770a8acc",
    "Chanel":               "10fccd15-cda1-8031-9e26-c0c3b6bb99d3",
    "Salvatore Ferragamo":  "2b9ccd15-cda1-80f6-a3ed-edb298b97a02",
    "Burberry":             "10fccd15-cda1-808f-b12a-d13411d7b58d",
    "Louis Vuitton":        "10fccd15-cda1-80b7-bd9f-d0abc8bfd469",
}

HERITAGE_MARKER      = "Heritage & House Notes"
CRAFT_MARKER         = "Craft & Materials"
VERIFICATION_MARKER  = "Verification & Sources"

claude = LLMClient()  # Auto-detects provider: Qwen, Anthropic, or MiniMax


# ── Notion helpers ──────────────────────────────────────────────────────────

def get_items_for_designer(designer_id):
    pages, cursor = [], None
    while True:
        body = {
            "page_size": 100,
            "filter": {"property": "Designer", "relation": {"contains": designer_id}},
        }
        if cursor:
            body["start_cursor"] = cursor
        r = requests.post(
            f"https://api.notion.com/v1/databases/{COLLECTION_DB_ID}/query",
            headers=NOTION_HEADERS, json=body,
        )
        r.raise_for_status()
        d = r.json()
        pages.extend(d["results"])
        if not d.get("has_more"):
            break
        cursor = d["next_cursor"]
    return pages


def get_recent_items(n):
    """Fetch the N most recently created items from the collection DB."""
    r = requests.post(
        f"https://api.notion.com/v1/databases/{COLLECTION_DB_ID}/query",
        headers=NOTION_HEADERS,
        json={
            "page_size": n,
            "sorts": [{"timestamp": "created_time", "direction": "descending"}],
        },
    )
    r.raise_for_status()
    return r.json().get("results", [])


def get_brand_for_page(page):
    """Return brand name by matching Designer relation to TARGET_DESIGNERS, else fetch from Notion."""
    designer_rel = page.get("properties", {}).get("Designer", {}).get("relation", [])
    for rel in designer_rel:
        rel_id = rel.get("id", "").replace("-", "")
        for brand, did in TARGET_DESIGNERS.items():
            if rel_id == did.replace("-", ""):
                return brand
    # Not in TARGET_DESIGNERS — fetch the designer page title from Notion
    if designer_rel:
        did = designer_rel[0].get("id", "")
        r = requests.get(f"https://api.notion.com/v1/pages/{did}", headers=NOTION_HEADERS)
        if r.status_code == 200:
            props = r.json().get("properties", {})
            title_prop = next((v for v in props.values() if v.get("type") == "title"), None)
            if title_prop and title_prop.get("title"):
                return title_prop["title"][0].get("plain_text", "Unknown")
    return "Unknown"


def extract_item_details(page):
    props = page["properties"]
    title_prop = next((v for v in props.values() if v.get("type") == "title"), None)
    name = (
        title_prop["title"][0].get("plain_text")
        if title_prop and title_prop.get("title")
        else "(untitled)"
    )
    sku_rt = props.get("SKU", {}).get("rich_text", [])
    sku = sku_rt[0]["plain_text"] if sku_rt else ""
    year_date = props.get("Year It's Made (first hand)", {}).get("date", {})
    year = year_date.get("start", "")[:4] if year_date else ""
    material_rt = props.get("Material", {}).get("rich_text", [])
    material = material_rt[0]["plain_text"] if material_rt else ""
    return {"name": name, "sku": sku, "year": year, "material": material}


def get_page_blocks(page_id):
    blocks, cursor = [], None
    while True:
        url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        if cursor:
            url += f"?start_cursor={cursor}"
        r = requests.get(url, headers=NOTION_HEADERS)
        r.raise_for_status()
        d = r.json()
        blocks.extend(d.get("results", []))
        if not d.get("has_more"):
            break
        cursor = d["next_cursor"]
    return blocks


def block_plain_text(block):
    btype = block.get("type", "")
    rt = block.get(btype, {}).get("rich_text", [])
    return "".join(x.get("plain_text", "") for x in rt)


def page_has_section(blocks, marker):
    for b in blocks:
        if b.get("type") in ("heading_2", "heading_3"):
            if marker in block_plain_text(b):
                return True
    return False


def extract_section_text(blocks, section_marker, stop_markers):
    """Extract all paragraph text under a heading_3 matching section_marker."""
    collecting = False
    paragraphs = []
    for b in blocks:
        btype = b.get("type", "")
        text = block_plain_text(b)
        if btype == "heading_3":
            if section_marker in text:
                collecting = True
                continue
            elif collecting and any(m in text for m in stop_markers):
                break
        if collecting and btype == "paragraph" and text.strip():
            paragraphs.append(text.strip())
    return "\n\n".join(paragraphs)


def append_blocks(page_id, blocks):
    for i in range(0, len(blocks), 100):
        r = requests.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=NOTION_HEADERS,
            json={"children": blocks[i : i + 100]},
        )
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Block append failed ({r.status_code}): {r.text[:300]}")
        time.sleep(0.3)


# ── Block builders ──────────────────────────────────────────────────────────

def para(text):
    return {
        "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


def h3(text):
    return {
        "type": "heading_3",
        "heading_3": {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


def divider():
    return {"type": "divider", "divider": {}}


def bullet(text):
    return {
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


# ── Claude prompts ──────────────────────────────────────────────────────────

CRAFT_PROMPT = """You are writing craft and material notes for a luxury fashion archive.

Brand: {brand}
Item: {item_name}
Year made: {year}
Material noted: {material}

Write a "Craft & Materials" section for this specific piece — 2-3 paragraphs of precise
technical and construction detail. Cover all that apply:

Leather goods / bags / shoes:
  Exact leather name (Togo, Clemence, Box calf, Barenia, Epsom, Swift, Veau Naturelle, etc.),
  tannery if known (e.g. Hermès's own Cuir Précieux tannery, Haas Mégisserie, Weinheimer),
  tanning method (full vegetable-tan, chrome-free, semi-vegetable),
  stitching technique (saddle stitch — two needles, waxed linen thread, ~5 stitches per cm —
  vs machine stitch), thread material and colour, edge treatment (hand-painted in multiple
  lacquer coats, burnished raw edge, wax finish), hardware metal and plating (palladium over
  brass, 24k gold over brass), lining material (chevre goatskin, lambskin, toile H, cotton
  canvas), overall construction approach (hand-built by a single artisan, bench-made, etc.).

Shoes specifically:
  Construction method (Blake stitch, Goodyear welt, hand-welted, cemented/glued),
  heel height and material, last name if known, sole material (full leather, rubber,
  combination), any signature Ferragamo/Hermès/LV/Chanel/Dior/Burberry construction notes.

Scarves / silk accessories:
  Silk weight in momme, fibre source (Maison Lesage, Lyonnais mills, etc.), weave type,
  printing method (hand screen-printed in Lyon, number of colour screens typical for this
  house), hem finish (hand-rolled and whip-stitched vs machine-rolled), dimensions.

Clothing:
  Fabric composition and weave, any canvassing or interlining, construction quality markers
  (hand-sewn seams, pick-stitching, horn buttons, floating canvas, brioche fabric, etc.).

If a specific detail is not confirmed for this exact piece, note it as "typical for the
house/era" rather than stating it as absolute fact.

Return only a JSON object with one key: "craft_details" (string, paragraphs joined by \\n\\n).
No bullet points. No markdown. Plain paragraphs only. 200-300 words."""


AUDIT_PROMPT = """You are a luxury fashion fact-checker and archival researcher.

Brand: {brand}
Item: {item_name}
Year: {year}

--- DESIGN LANGUAGE ---
{design_language}

--- THIS PIECE ---
{this_piece}

--- CRAFT & MATERIALS (if available) ---
{craft_details}

Your task — focus ONLY on Design Language, This Piece, and Craft & Materials. Do NOT audit
or reference the House history section.

1. Identify 5–10 specific, verifiable factual claims across these three sections (dates,
   people, model names, material names, technique names, measurements).

2. For each claim, provide:
   - The exact claim (short quote or paraphrase)
   - Verification status: "confirmed", "approximate", or "uncertain"
   - A specific, real reference URL that supports or contextualises the claim.
     Prefer: official brand website, Wikipedia, Vogue archive, BoF (Business of Fashion),
     museum collection pages (V&A, Met, Palais Galliera), tannery or craft body pages.
   - A one-line note explaining what the source confirms.

3. Also list 2–3 craft details that could be researched further — gaps where the archive
   notes are vague and a physical inspection or trade document would be needed to confirm.

Return ONLY valid JSON:
{{
  "references": [
    {{
      "claim": "...",
      "status": "confirmed" | "approximate" | "uncertain",
      "url": "https://...",
      "note": "..."
    }}
  ],
  "further_research": ["...", "...", "..."]
}}"""


# ── Generation functions ────────────────────────────────────────────────────

def generate_craft_details(brand, item):
    prompt = CRAFT_PROMPT.format(
        brand=brand,
        item_name=item["name"],
        year=item["year"] or "unknown",
        material=item["material"] or "unknown",
    )
    raw = claude.generate("You are writing craft and material notes for a luxury fashion archive.", prompt, max_tokens=800)
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    return json.loads(raw)["craft_details"]


def generate_audit(brand, item, design_language, this_piece, craft_details):
    prompt = AUDIT_PROMPT.format(
        brand=brand,
        item_name=item["name"],
        year=item["year"] or "unknown",
        design_language=design_language or "(not available)",
        this_piece=this_piece or "(not available)",
        craft_details=craft_details or "(not available)",
    )
    raw = claude.generate("You are a luxury fashion fact-checker and archival researcher. Return ONLY valid JSON.", prompt, max_tokens=1800)
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    return json.loads(raw)


STATUS_ICONS = {"confirmed": "✓", "approximate": "~", "uncertain": "?"}


def build_craft_blocks(craft_text):
    blocks = [divider(), h3(CRAFT_MARKER)]
    for p in craft_text.split("\n\n"):
        p = p.strip()
        if p:
            blocks.append(para(p))
    return blocks


def build_verification_blocks(audit):
    blocks = [divider(), h3(VERIFICATION_MARKER)]

    refs = audit.get("references", [])
    if refs:
        blocks.append(para("Fact-check · Design Language & This Piece"))
        for ref in refs:
            icon = STATUS_ICONS.get(ref.get("status", "uncertain"), "?")
            claim = ref.get("claim", "")
            note  = ref.get("note", "")
            url   = ref.get("url", "")
            line  = f'{icon} {claim}'
            if note:
                line += f" — {note}"
            blocks.append(bullet(line))
            if url:
                blocks.append(bullet(f"  → {url}"))

    further = audit.get("further_research", [])
    if further:
        blocks.append(para("Further research needed"))
        for item in further:
            blocks.append(bullet(item))

    return blocks


# ── Main ────────────────────────────────────────────────────────────────────

ALL_SECTION_MARKERS = [
    "The House", "Design Language", "This Piece",
    CRAFT_MARKER, VERIFICATION_MARKER,
]


def process_item(brand, page):
    item     = extract_item_details(page)
    page_id  = page["id"]
    blocks   = get_page_blocks(page_id)

    if not page_has_section(blocks, HERITAGE_MARKER):
        print("     No heritage content — skipping (run heritage.py first)")
        return "no_heritage"

    if page_has_section(blocks, VERIFICATION_MARKER):
        print("     Already audited — skipping")
        return "already_done"

    # Extract existing sections
    design_language = extract_section_text(blocks, "Design Language", ALL_SECTION_MARKERS)
    this_piece      = extract_section_text(blocks, "This Piece",       ALL_SECTION_MARKERS)
    craft_existing  = extract_section_text(blocks, CRAFT_MARKER,       ALL_SECTION_MARKERS)

    new_blocks = []

    # Add Craft & Materials if missing (old heritage.py didn't include it)
    if not page_has_section(blocks, CRAFT_MARKER):
        print("     Generating Craft & Materials...")
        craft_text = generate_craft_details(brand, item)
        new_blocks += build_craft_blocks(craft_text)
        craft_existing = craft_text
        time.sleep(0.5)
    else:
        print("     Craft & Materials already present")

    # Always add Verification & Sources
    print("     Generating Verification & Sources...")
    audit = generate_audit(brand, item, design_language, this_piece, craft_existing)
    new_blocks += build_verification_blocks(audit)

    if new_blocks:
        append_blocks(page_id, new_blocks)
        print(f"     Written ({len(new_blocks)} blocks)")

    return "done"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Audit and fact-check heritage notes on collection item pages")
    parser.add_argument("--recent", metavar="N", type=int, help="Audit the N most recently added items (all brands)")
    args = parser.parse_args()

    total_done = total_skipped = total_errors = 0

    if args.recent:
        print(f"\nFetching {args.recent} most recently added items...")
        pages = get_recent_items(args.recent)
        print(f"  {len(pages)} items retrieved\n")
        for page in pages:
            brand = get_brand_for_page(page)
            item = extract_item_details(page)
            print(f"\n  → {item['name']!r}  ({brand})")
            try:
                result = process_item(brand, page)
                if result == "done":
                    total_done += 1
                else:
                    total_skipped += 1
                time.sleep(1)
            except Exception as e:
                print(f"     ERROR: {e}")
                total_errors += 1
                time.sleep(2)
        print(f"\n{'='*60}")
        print(f"Done. {total_done} audited, {total_skipped} skipped, {total_errors} errors.")
        return

    # Default: process all TARGET_DESIGNERS
    for brand, designer_id in TARGET_DESIGNERS.items():
        print(f"\n{'='*60}")
        print(f"  {brand}")
        print(f"{'='*60}")

        items = get_items_for_designer(designer_id)
        print(f"  {len(items)} items found")

        for page in items:
            item = extract_item_details(page)
            print(f"\n  → {item['name']!r}")
            try:
                result = process_item(brand, page)
                if result == "done":
                    total_done += 1
                else:
                    total_skipped += 1
                time.sleep(1)
            except Exception as e:
                print(f"     ERROR: {e}")
                total_errors += 1
                time.sleep(2)

    print(f"\n{'='*60}")
    print(f"Done. {total_done} audited, {total_skipped} skipped, {total_errors} errors.")


if __name__ == "__main__":
    main()
