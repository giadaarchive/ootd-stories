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
Existing description already recorded in the archive (use this as ground truth for the piece's
specific details — materials, construction, condition, style name, label details, sizing):
---
{page_description}
---
"""

    return f"""You are writing archive documentation for a single luxury fashion piece in a personal wardrobe collection.

CRITICAL RULE: Every word must be about THIS SPECIFIC PIECE — this garment, this bag, this shoe, this scarf.
Do NOT mention other product categories. If this is a coat, write about coats and outerwear only.
If this is a scarf, write about scarves only. Do not name-drop Birkin bags when writing about a coat.
Do not reference silk carrés when writing about shoes. Stay entirely within the world of this object.

Brand: {brand}
Item: {item["name"]}
{details_str}
{desc_block}
Designer-era context (use only to date and contextualise THIS piece — do not paste this into the output):
{era_context}

Return JSON with exactly five keys. Each value is a plain string; separate paragraphs with \\n\\n.
No bullet points. No headers inside the text. Write in present tense where appropriate.

"about_this_piece"
  1–2 paragraphs. What is this specific object — its garment category, the creative director
  who designed it, the season/era it belongs to, and what makes it notable within the house's
  output for THIS category. Ground every sentence in this specific piece.

"design_language"
  1–2 paragraphs. The design language expressed IN THIS PIECE: its silhouette, cut, and
  proportion; its collar, closure, sleeve, hem, or handle treatment (whatever applies);
  the structural choices that define how it looks and moves. For a coat: how long is it,
  how does the shoulder sit, where does it fall at the waist, how does it close, what does
  the collar do. For a shoe: the heel geometry, the vamp line, the toe shape. This is NOT
  the house's general aesthetic — it is the aesthetic of this specific object.

"craft_and_materials"
  2–3 paragraphs. Precise materials and construction for THIS piece. Include all that apply:
  — Textiles: fabric name and composition, weave type, weight (g/m² or momme), finish
  — Animal materials: fur type (species, part of animal, treatment method), leather name,
    tannery if known, tanning method (vegetable, chrome-free, combination), how the material
    is used on this piece specifically
  — Construction: stitching method (saddle stitch / hand-sewn / machine), stitch count,
    thread material, seam type, edge treatment, interfacing, canvassing, lining material
  — Closures and hardware: button material (horn, shell, metal), clasp type, hardware plating
  — Size context: what the size label means in this house's sizing
  If a specific detail is not confirmed, note it as typical for the house/era.

"historical_context"
  1–2 paragraphs. Timeline and decisions SPECIFIC to this type of piece and these materials:
  — When did this house/designer work with this silhouette, this material, this construction?
  — If fur: when did the house start using it, when (if ever) did they stop?
  — If a specific fabric: what is the house's relationship with that material?
  — What was the collector or resale significance of this garment type from this era?
  — What was happening in fashion at the time this piece was made, specifically relevant
    to this category of garment?

"research_notes"
  2–3 paragraphs summarising the research process for this specific piece:
  — What questions were investigated (e.g. "when did Hermès use weasel fur collar on coats")
  — What is confirmed vs what is approximate or uncertain
  — What would need physical inspection or trade documentation to verify
  — Any notable gaps in the public record for this specific piece type

Total across all five keys: 600–900 words.
Return only valid JSON, nothing else."""


# ── Content generation ──────────────────────────────────────────────────────

def generate_content(brand, item, page_description=""):
    era_ctx = DESIGNER_ERAS.get(brand, "")
    prompt  = build_prompt(brand, item, era_ctx, page_description)
    msg     = claude.messages.create(
        model="claude-opus-4-7",
        max_tokens=3200,
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
        ("about_this_piece", "About This Piece"),
        ("design_language",  "Design Language"),
        ("craft_and_materials", "Craft & Materials"),
        ("historical_context",  "Historical Context"),
    ]:
        blocks.append(h3(label))
        for p in content.get(key, "").split("\n\n"):
            p = p.strip()
            if p:
                blocks.append(para(p))

    # Research notes go in a collapsible toggle
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
    force_page_id = None
    if "--force" in sys.argv:
        idx = sys.argv.index("--force")
        if idx + 1 < len(sys.argv):
            raw_id = sys.argv[idx + 1].replace("-", "")
            # normalise to hyphenated UUID
            force_page_id = f"{raw_id[:8]}-{raw_id[8:12]}-{raw_id[12:16]}-{raw_id[16:20]}-{raw_id[20:]}"

    written = skipped = errors = 0

    for brand, designer_id in TARGET_DESIGNERS.items():
        print(f"\n{'='*60}")
        print(f"  {brand}")
        print(f"{'='*60}")

        items = get_items_for_designer(designer_id)
        print(f"  {len(items)} items")

        for page in items:
            item    = extract_item_details(page)
            page_id = page["id"]
            force   = (force_page_id is not None and page_id == force_page_id)
            print(f"\n  → {item['name']!r}")

            try:
                result = process_page(page_id, brand, item, force=force)
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
