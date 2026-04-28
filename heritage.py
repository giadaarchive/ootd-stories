#!/usr/bin/env python3
"""
Write piece-centric archive documentation to L's collection item pages.

Every section is about THIS SPECIFIC GARMENT — its design, its materials,
its place in the house's output for that category. No generic house history.
No mentions of other product categories.

Usage:
  python3 heritage.py                      — process all target brand items
  python3 heritage.py --force <page_id>    — clear and rewrite one specific page
"""

import requests
import os
import sys
import json
import time
from dotenv import load_dotenv
import anthropic

load_dotenv()

NOTION_TOKEN     = os.environ["NOTION_TOKEN"]
COLLECTION_DB_ID = "ad079964969043ae9fa85a4f3ca1a9ee"
NOTION_HEADERS   = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

TARGET_DESIGNERS = {
    "Hermès":              "2b9ccd15-cda1-80fe-9888-dabde81bb8b1",
    "Christian Dior":      "33c5aada-5e92-44d7-9dcb-747e770a8acc",
    "Chanel":              "10fccd15-cda1-8031-9e26-c0c3b6bb99d3",
    "Salvatore Ferragamo": "2b9ccd15-cda1-80f6-a3ed-edb298b97a02",
    "Burberry":            "10fccd15-cda1-808f-b12a-d13411d7b58d",
    "Louis Vuitton":       "10fccd15-cda1-80b7-bd9f-d0abc8bfd469",
}

# Brief creative-director timeline used only to orient Claude to the correct era.
# This is NOT pasted into the Notion page — it just helps date the piece correctly.
DESIGNER_ERAS = {
    "Hermès": (
        "Women's RTW creative directors: Martin Margiela 1997–2003 (understated, straight "
        "silhouettes, removable elements, no cinched waists, natural drape); Christophe Lemaire "
        "2010–2014; Nadège Vanhée-Cybulski 2014–present. Hermès continues using animal fur and "
        "exotic skins as of 2024 — no fur-free announcement made. Cashmere sourced from specialist "
        "mills; Hermès acquired 15% of Lanificio Colombo (Piedmont, Italy) in 2024."
    ),
    "Christian Dior": (
        "Women's RTW: Dior 1947–57 (New Look, Bar jacket), Yves Saint Laurent 1957–60, Marc Bohan "
        "1960–89, Gianfranco Ferré 1989–96 (architectural), John Galliano 1996–2011 (theatrical), "
        "Raf Simons 2012–15 (minimalist rigour), Maria Grazia Chiuri 2016–present (feminist codes)."
    ),
    "Chanel": (
        "Coco Chanel 1910–1939, reopened 1954–1971. Karl Lagerfeld 1983–2019 (codified house "
        "language: boucle suit, chain bag, camellia, pearl). Virginie Viard 2019–2024. "
        "Matthieu Blazy appointed 2025."
    ),
    "Salvatore Ferragamo": (
        "Founded by Salvatore Ferragamo, Hollywood shoemaker and anatomist, Florence 1927. "
        "Over 350 patents. Daughter Fiamma created the Vara pump 1978. Family-run until "
        "Ferruccio Ferragamo era. Known for hand-lasted construction over wooden lasts."
    ),
    "Burberry": (
        "Thomas Burberry 1856. Gabardine invented 1879. Trench coat designed for WWI 1914. "
        "The Burberry check (beige/black/red/white) registered 1924. Christopher Bailey "
        "2001–2018; Riccardo Tisci 2018–2022; Daniel Lee 2022–present."
    ),
    "Louis Vuitton": (
        "Founded 1854 Paris. LV Monogram canvas 1896. Marc Jacobs women's RTW 1997–2014 "
        "(artist collaborations, ready-to-wear expansion). Nicolas Ghesquière 2013–present "
        "(futurist, archival). Monogram canvas, Damier Ebene, Epi leather are house signatures."
    ),
}

HERITAGE_MARKER = "Heritage & House Notes"
claude          = anthropic.Anthropic()


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
    """Return (brand_name, era_context) by matching Designer relation to TARGET_DESIGNERS."""
    designer_rel = page.get("properties", {}).get("Designer", {}).get("relation", [])
    for rel in designer_rel:
        rel_id = rel.get("id", "").replace("-", "")
        for brand, did in TARGET_DESIGNERS.items():
            if rel_id == did.replace("-", ""):
                return brand, DESIGNER_ERAS.get(brand, "")
    return "Unknown", ""


def get_all_blocks(page_id):
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


def block_text(block):
    btype = block.get("type", "")
    return "".join(
        rt.get("plain_text", "")
        for rt in block.get(btype, {}).get("rich_text", [])
    )


def page_has_heritage_content(page_id):
    for b in get_all_blocks(page_id):
        if b.get("type") in ("heading_2", "heading_3") and HERITAGE_MARKER in block_text(b):
            return True
    return False


def delete_heritage_blocks(page_id):
    """Delete all blocks from the Heritage heading onwards."""
    blocks = get_all_blocks(page_id)
    deleting = False
    deleted = 0
    for b in blocks:
        if b.get("type") in ("heading_2",) and HERITAGE_MARKER in block_text(b):
            deleting = True
        if deleting:
            r = requests.delete(
                f"https://api.notion.com/v1/blocks/{b['id']}",
                headers=NOTION_HEADERS,
            )
            if r.status_code == 200:
                deleted += 1
            time.sleep(0.15)
    return deleted


def extract_item_details(page):
    props = page["properties"]
    title_prop = next((v for v in props.values() if v.get("type") == "title"), None)
    name = (
        title_prop["title"][0].get("plain_text")
        if title_prop and title_prop.get("title")
        else "(untitled)"
    )
    sku_rt   = props.get("SKU", {}).get("rich_text", [])
    sku      = sku_rt[0]["plain_text"] if sku_rt else ""
    cat_sel  = props.get("Category", {}).get("select")
    category = cat_sel["name"] if cat_sel else ""
    year_date = props.get("Year It's Made (first hand)", {}).get("date", {})
    year     = year_date.get("start", "")[:4] if year_date else ""
    mat_rt   = props.get("Material", {}).get("rich_text", [])
    material = mat_rt[0]["plain_text"] if mat_rt else ""
    return {"name": name, "sku": sku, "category": category, "year": year, "material": material}


def read_page_description(page_id):
    """Read existing body text (paragraphs/bullets before the Heritage section) as item context."""
    lines = []
    for b in get_all_blocks(page_id):
        btype = b.get("type", "")
        if btype in ("heading_2",) and HERITAGE_MARKER in block_text(b):
            break   # stop before our own section
        if btype in ("paragraph", "bulleted_list_item", "numbered_list_item"):
            t = block_text(b).strip()
            if t and len(t) > 10:   # skip trivial lines
                lines.append(t)
    return "\n".join(lines[:40])   # cap at 40 lines to stay within prompt budget


def append_blocks_to_page(page_id, blocks):
    for i in range(0, len(blocks), 100):
        r = requests.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=NOTION_HEADERS,
            json={"children": blocks[i : i + 100]},
        )
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Block append failed ({r.status_code}): {r.text[:300]}")
        time.sleep(0.3)


# ── Prompt ──────────────────────────────────────────────────────────────────

def build_prompt(brand, item, era_context, page_description=""):
    details = []
    if item["year"]:
        details.append(f"year made: {item['year']}")
    if item["material"]:
        details.append(f"material noted: {item['material']}")
    if item["category"]:
        details.append(f"archive category: {item['category']}")
    details_str = " | ".join(details) if details else "details not recorded"

    desc_block = ""
    if page_description.strip():
        desc_block = f"""
Existing description already recorded in the archive — use as ground truth for this piece's
specific details (materials, construction, condition, style name, label, sizing, acquisition context):
---
{page_description}
---
"""

    return f"""You are writing a six-layer provenance and archive document for a single luxury fashion piece in a personal wardrobe collection.

CRITICAL RULE: Every word must be about THIS SPECIFIC PIECE — this garment, this bag, this shoe.
Do NOT describe the house's general output or other product categories. Stay within the world of this object.
Be honest about what is confirmed versus approximate versus unknown — do not invent specifics.
BANNED PHRASES: never write "quiet luxury" or any variation of it. Describe what the piece actually is.

Brand: {brand}
Item: {item["name"]}
{details_str}
{desc_block}
Designer-era context (use only to date and contextualise — do not paste into output):
{era_context}

---

Return JSON with exactly seven keys. Each value is a plain string; separate paragraphs with \\n\\n.
No bullet points inside values. No sub-headers inside values. Present tense where appropriate.

"object_identity"
  2–3 paragraphs. The piece itself, unambiguously identified:
  — Maker, line/model name, colorway, size
  — Specific materials: fabric composition or leather type, hardware finish, lining material,
    date code (location and what it reads — if unknown or unread, say so explicitly)
  — Production era: year or year range, country of manufacture
  — Distinguishing physical details: stitching count per cm on main seams, hardware weight
    and finish (palladium, gold, brass — and whether a magnet test has been done),
    interior stamp placement, label typography. Flag anything unverified.

"maker_context"
  2 paragraphs. Why this piece matters relative to others from the same house:
  — Who was creative director at time of production and what defined that era's output
    for THIS garment/object category specifically
  — What made this era's version different from earlier and later production
  — What changed after — why the older version differs from what's sold today

"authentication"
  2–3 paragraphs. Proof the object is what it claims to be — model-specific, not brand-generic:
  — How to authenticate THIS SPECIFIC MODEL: date code format and location for this line,
    hardware tells unique to this model, stitching count, material characteristics
  — Known fakes for this model — what they get wrong (wrong zipper pull weight, incorrect
    stamp placement, hardware that doesn't hold a magnet, wrong fabric hand, shallow embossing)
  — Condition assessment: honest grading of this specific piece — what is worn, what is
    pristine, what shows age, what needs attention
  — Authentication gaps: what can only be confirmed by physical inspection or trade document

"ownership_history"
  1–2 paragraphs. Where the piece has been. Be explicit about what is unknown:
  — Original retail context: store type, approximate year of first sale, original retail
    price range if known or estimable
  — Subsequent ownership: what is known or can be inferred from condition, provenance
    details, or acquisition context (estate, collector, first-generation owner, number of owners)
  — Geographic and climate history if determinable from condition evidence
  — Care and storage history based on what the current condition suggests
  Incomplete is fine — say "unknown" rather than guessing.

"market_context"
  2 paragraphs. Where this piece sits in the current secondary market — specific, not vague:
  — Current resale price range for THIS model and colorway specifically, not the brand in
    general (cite approximate current range on Vestiaire, 1stDibs, or comparable platforms)
  — Price trajectory: appreciating, stable, or declining — and why
  — Rarity: how frequently this specific model and colorway surfaces on secondary market
  — Comparable pieces: what else exists at this price and quality level, and why this is
    or is not the better choice for a serious collector

"wearability"
  2 paragraphs. How this piece actually functions for a real woman — the layer no authentication
  service or resale platform provides:
  — Who it suits: body proportion this flatters, lifestyle and wardrobe profile it belongs in
  — How it wears: weight, drape or structure, strap or closure handling, interior organisation
  — What it resolves: 2–3 specific outfit contexts where this piece is the right answer
  — What it fights with: wardrobe contexts where it doesn't work
  — CPW potential: realistic estimate of how often a woman with the right wardrobe profile
    would reach for it, and what determines that frequency

"research_notes"
  2 paragraphs. Research process summary:
  — What was investigated, what is confirmed vs approximate vs uncertain
  — What physical inspection or trade documentation would resolve the remaining gaps

Total across all seven keys: 900–1400 words.
Return only valid JSON, nothing else."""


# ── Content generation ──────────────────────────────────────────────────────

def generate_content(brand, item, page_description=""):
    era_ctx = DESIGNER_ERAS.get(brand, "")
    prompt  = build_prompt(brand, item, era_ctx, page_description)
    msg     = claude.messages.create(
        model="claude-opus-4-7",
        max_tokens=4500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    return json.loads(raw)


# ── Block builders ──────────────────────────────────────────────────────────

def para(text):
    return {
        "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


def h2(text):
    return {
        "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


def h3(text):
    return {
        "type": "heading_3",
        "heading_3": {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


def toggle(title, children_paras):
    return {
        "type": "toggle",
        "toggle": {
            "rich_text": [{"type": "text", "text": {"content": title}}],
            "children": [para(p) for p in children_paras if p.strip()],
        },
    }


def build_blocks(content):
    blocks = [
        {"type": "divider", "divider": {}},
        h2(HERITAGE_MARKER),
    ]

    for key, label in [
        ("object_identity",  "Layer 1 — Object Identity"),
        ("maker_context",    "Layer 2 — Maker Context"),
        ("authentication",   "Layer 3 — Authentication"),
        ("ownership_history","Layer 4 — Ownership History"),
        ("market_context",   "Layer 5 — Market Context"),
        ("wearability",      "Layer 6 — Wearability"),
    ]:
        blocks.append(h3(label))
        for p in content.get(key, "").split("\n\n"):
            p = p.strip()
            if p:
                blocks.append(para(p))

    research_paras = [
        p.strip()
        for p in content.get("research_notes", "").split("\n\n")
        if p.strip()
    ]
    if research_paras:
        blocks.append(toggle("Research Notes", research_paras))

    return blocks


# ── Main ────────────────────────────────────────────────────────────────────

def process_page(page_id, brand, item, force=False):
    if not force and page_has_heritage_content(page_id):
        print("     Already has archive notes — skipping")
        return "skipped"

    # Read body description before clearing (so we can pass it to the prompt)
    page_description = read_page_description(page_id)
    if page_description:
        print(f"     Found {len(page_description.splitlines())} lines of existing description")

    if force:
        deleted = delete_heritage_blocks(page_id)
        print(f"     Cleared {deleted} existing blocks")

    print("     Generating archive notes...")
    content = generate_content(brand, item, page_description)
    blocks  = build_blocks(content)
    append_blocks_to_page(page_id, blocks)
    print(f"     Written ({len(blocks)} blocks)")
    return "done"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Write heritage notes to Notion collection pages")
    parser.add_argument("--force", metavar="PAGE_ID", help="Clear and rewrite one specific page")
    parser.add_argument("--recent", metavar="N", type=int, help="Process the N most recently added items")
    args = parser.parse_args()

    written = skipped = errors = 0

    if args.force:
        raw_id = args.force.replace("-", "")
        force_page_id = f"{raw_id[:8]}-{raw_id[8:12]}-{raw_id[12:16]}-{raw_id[16:20]}-{raw_id[20:]}"
        # Find the page across all designers
        found = False
        for brand, designer_id in TARGET_DESIGNERS.items():
            for page in get_items_for_designer(designer_id):
                if page["id"] == force_page_id:
                    item = extract_item_details(page)
                    print(f"\n  → {item['name']!r}  ({brand})")
                    process_page(force_page_id, brand, item, force=True)
                    found = True
                    break
            if found:
                break
        if not found:
            print(f"Page {force_page_id} not found in any TARGET_DESIGNER — cannot proceed")
        return

    if args.recent:
        print(f"\nFetching {args.recent} most recently added items...")
        pages = get_recent_items(args.recent)
        print(f"  {len(pages)} items retrieved\n")
        for page in pages:
            brand, _ = get_brand_for_page(page)
            item = extract_item_details(page)
            print(f"\n  → {item['name']!r}  ({brand})")
            try:
                result = process_page(page["id"], brand, item, force=False)
                if result == "done":
                    written += 1
                else:
                    skipped += 1
                time.sleep(1)
            except Exception as e:
                print(f"     ERROR: {e}")
                errors += 1
                time.sleep(2)
        print(f"\n{'='*60}")
        print(f"Done. {written} written, {skipped} skipped, {errors} errors.")
        return

    # Default: process all TARGET_DESIGNERS
    for brand, designer_id in TARGET_DESIGNERS.items():
        print(f"\n{'='*60}")
        print(f"  {brand}")
        print(f"{'='*60}")

        items = get_items_for_designer(designer_id)
        print(f"  {len(items)} items")

        for page in items:
            item    = extract_item_details(page)
            page_id = page["id"]
            print(f"\n  → {item['name']!r}")

            try:
                result = process_page(page_id, brand, item, force=False)
                if result == "done":
                    written += 1
                else:
                    skipped += 1
                time.sleep(1)
            except Exception as e:
                print(f"     ERROR: {e}")
                errors += 1
                time.sleep(2)

    print(f"\n{'='*60}")
    print(f"Done. {written} written, {skipped} skipped, {errors} errors.")


if __name__ == "__main__":
    main()
