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
from llm_client import LLMClient

load_dotenv()

NOTION_TOKEN     = os.environ["NOTION_TOKEN"]
COLLECTION_DB_ID = "ad079964969043ae9fa85a4f3ca1a9ee"
NOTION_HEADERS   = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

claude = LLMClient()  # Auto-detects provider: Qwen, Anthropic, or MiniMax

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

HERITAGE_MARKER  = "Heritage & House Notes"
CHECKPOINT_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "heritage_checkpoint.json")
claude           = anthropic.Anthropic()

SYSTEM_PROMPT = """\
You are writing a heritage document for a single luxury fashion piece in a personal archive collection.

CRITICAL RULE: Every word must be about THIS SPECIFIC PIECE — this exact garment or object.
Write for someone who already knows the brand. They want to understand this piece specifically.
Do NOT mention: retail prices, retailers, where to buy, resale value, market context,
authentication, ownership history, purchase details, or previous owners.
BANNED: never write "quiet luxury" or any variation. Describe what the piece actually is.

Return JSON with exactly four keys. Each value is a plain string; separate paragraphs with \\n\\n.
No bullet points or sub-headers inside values.

"about_this_piece"
  2 paragraphs. What this piece is:
  Exact type, silhouette, colour, size. Key details that make it immediately identifiable —
  proportions, closure, hardware, label, date code or production markings if visible.
  Honest condition description.

"design_language"
  2 paragraphs. The aesthetic and creative decisions in this piece:
  Silhouette, line, proportion, detail, finish. How these choices reflect the house's design
  vocabulary at the time. What this piece communicates visually and why those choices matter
  for this specific category and era.

"craft_and_materials"
  2 paragraphs. How this piece is made and what it is made of:
  Specific materials — fibre composition, leather type, hardware material and finish, lining.
  Construction — seaming, hand-finishing, hardware mechanics, stitching. What the quality of
  craft reveals about the production standard and era.

"historical_context"
  2 paragraphs. Where this piece sits in the history of the house and its period:
  Creative director at time of production and what defined that era for this specific category.
  What was happening in fashion at the time and how this piece reflects it. Why this era's
  production differs from earlier and later output.

Total across all four keys: 500–700 words.
Return only valid JSON, nothing else.\
"""


# ── Checkpoint helpers ───────────────────────────────────────────────────────

def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {}


def save_checkpoint(before_time):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({"before_time": before_time}, f, indent=2)


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


def iter_items_from_checkpoint(before_time=None):
    """Yield items in descending created_time order, starting before before_time if given."""
    cursor = None
    while True:
        body = {
            "page_size": 100,
            "sorts": [{"timestamp": "created_time", "direction": "descending"}],
        }
        if before_time:
            body["filter"] = {
                "timestamp": "created_time",
                "created_time": {"before": before_time},
            }
        if cursor:
            body["start_cursor"] = cursor
        r = requests.post(
            f"https://api.notion.com/v1/databases/{COLLECTION_DB_ID}/query",
            headers=NOTION_HEADERS, json=body,
        )
        r.raise_for_status()
        d = r.json()
        yield from d["results"]
        if not d.get("has_more"):
            break
        cursor = d["next_cursor"]


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

def build_user_prompt(brand, item, era_context, page_description=""):
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
        desc_block = (
            "\nExisting description already recorded in the archive — use as ground truth for this piece's"
            "\nspecific details (materials, construction, condition, style name, label, sizing, acquisition context):\n"
            f"---\n{page_description}\n---\n"
        )

    return (
        f"Brand: {brand}\n"
        f"Item: {item['name']}\n"
        f"{details_str}\n"
        f"{desc_block}"
        f"Designer-era context (use only to date and contextualise — do not paste into output):\n"
        f"{era_context}"
    )


# ── Content generation ──────────────────────────────────────────────────────

def generate_content(brand, item, page_description=""):
    era_ctx  = DESIGNER_ERAS.get(brand, "")
    user_msg = build_user_prompt(brand, item, era_ctx, page_description)
    raw = claude.generate(SYSTEM_PROMPT, user_msg, max_tokens=1800)
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
        ("about_this_piece",    "About This Piece"),
        ("design_language",     "Design Language"),
        ("craft_and_materials", "Craft & Materials"),
        ("historical_context",  "Historical Context"),
    ]:
        blocks.append(h3(label))
        for p in content.get(key, "").split("\n\n"):
            p = p.strip()
            if p:
                blocks.append(para(p))
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
    parser.add_argument("--limit", metavar="N", type=int,
                        help="Write up to N items in descending order, resuming from last checkpoint")
    args = parser.parse_args()

    written = skipped = errors = 0

    if args.force:
        raw_id = args.force.replace("-", "")
        force_page_id = f"{raw_id[:8]}-{raw_id[8:12]}-{raw_id[12:16]}-{raw_id[16:20]}-{raw_id[20:]}"
        r = requests.get(
            f"https://api.notion.com/v1/pages/{force_page_id}",
            headers=NOTION_HEADERS,
        )
        r.raise_for_status()
        page = r.json()
        brand, _ = get_brand_for_page(page)
        item = extract_item_details(page)
        print(f"\n  → {item['name']!r}  ({brand})")
        process_page(force_page_id, brand, item, force=True)
        return

    if args.limit:
        checkpoint  = load_checkpoint()
        before_time = checkpoint.get("before_time")
        print(f"\nLimit mode: writing up to {args.limit} items (newest → oldest)")
        if before_time:
            print(f"  Resuming from checkpoint: items created before {before_time}")
        else:
            print("  No checkpoint found — starting from newest items")

        last_time = before_time
        for page in iter_items_from_checkpoint(before_time):
            item_time = page.get("created_time")
            # Advance checkpoint past this item before processing
            if item_time:
                last_time = item_time
                save_checkpoint(item_time)

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

            if written >= args.limit:
                break

        print(f"\n{'='*60}")
        print(f"Done. {written} written, {skipped} skipped, {errors} errors.")
        if last_time:
            print(f"Checkpoint: next run continues from before {last_time}")
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
