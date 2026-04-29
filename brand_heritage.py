#!/usr/bin/env python3
"""
brand_heritage.py — Write brand/house history to designer pages in Notion.

Queries the Designer database, generates a comprehensive brand history for each house,
and writes it directly to the brand's Notion page. This is house-level documentation —
the story of the brand itself, not of any individual item.

Usage:
    python3 brand_heritage.py                     — write all brands missing brand heritage
    python3 brand_heritage.py --force "Valextra"  — clear and rewrite one specific brand
    python3 brand_heritage.py --list              — list all brands in the designer database
"""

import os
import sys
import json
import time
import requests
import argparse
from dotenv import load_dotenv
import anthropic

load_dotenv()

NOTION_TOKEN    = os.environ["NOTION_TOKEN"]
DESIGNER_DB_ID  = "079fa275-238c-4427-94b5-2c0b0f485bf9"
NOTION_HEADERS  = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

BRAND_HERITAGE_MARKER = "Brand Heritage"
claude = anthropic.Anthropic()


# ── Notion helpers ──────────────────────────────────────────────────────────

def get_all_brands():
    """Return all pages from the Designer database."""
    pages, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        r = requests.post(
            f"https://api.notion.com/v1/databases/{DESIGNER_DB_ID}/query",
            headers=NOTION_HEADERS, json=body,
        )
        r.raise_for_status()
        d = r.json()
        pages.extend(d["results"])
        if not d.get("has_more"):
            break
        cursor = d["next_cursor"]
    return pages


def get_brand_name(page):
    props = page.get("properties", {})
    title_prop = next((v for v in props.values() if v.get("type") == "title"), None)
    if title_prop and title_prop.get("title"):
        return title_prop["title"][0].get("plain_text", "").strip()
    return ""


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


def page_has_brand_heritage(page_id):
    for b in get_all_blocks(page_id):
        if b.get("type") in ("heading_2", "heading_3") and BRAND_HERITAGE_MARKER in block_text(b):
            return True
    return False


def delete_brand_heritage_blocks(page_id):
    blocks = get_all_blocks(page_id)
    deleting = False
    deleted = 0
    for b in blocks:
        if b.get("type") == "heading_2" and BRAND_HERITAGE_MARKER in block_text(b):
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


def read_existing_page_content(page_id):
    """Read any existing body text above the Brand Heritage section."""
    lines = []
    for b in get_all_blocks(page_id):
        btype = b.get("type", "")
        if btype == "heading_2" and BRAND_HERITAGE_MARKER in block_text(b):
            break
        if btype in ("paragraph", "bulleted_list_item", "numbered_list_item"):
            t = block_text(b).strip()
            if t and len(t) > 10:
                lines.append(t)
    return "\n".join(lines[:30])


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

BRAND_HERITAGE_PROMPT = """You are writing comprehensive house documentation for a luxury fashion archive. This is the definitive reference entry for this brand — covering its full history, the people behind it, and what makes it distinctive.

BANNED PHRASES: never write "quiet luxury" or any variation. Never use "heritage brand" as a filler phrase. Describe what the house actually is and does.

Brand: {brand_name}
{existing_content_block}

Research and write the full brand history across seven sections. Every claim should be as specific as possible. Where something is approximate or uncertain, say so. Do not invent specifics.

For brands with industrial, craft, or non-fashion origins (aircraft manufacturers, textile mills, family workshops), give extra weight to that origin story — it is what distinguishes these houses from generic luxury labels.

Return JSON with exactly seven keys. Each value is a plain string; separate paragraphs with \\n\\n. No bullet points inside values. No sub-headers inside values.

"founding_story"
  2 paragraphs. When and where was this house founded, by whom, and why. What was the specific context — what gap were they filling, what skill were they bringing, what opportunity did they see? Include the city, the year, the founder's background. Be precise.

"family_and_founders"
  2 paragraphs. Who were the people behind this brand — not just names but backgrounds, skills, other careers, family involvement across generations. If the founder came from another industry (aircraft, textiles, shoemaking, engineering), describe that industry and what it contributed. Generational transfers, marriages into the business, family conflicts, key non-family figures who shaped the house.

"historical_moments"
  2–3 paragraphs. The events that shaped the brand — wars (WWI, WWII, Korean War), economic crises, ownership changes, pivotal commissions or clients, near-collapses and recoveries, licensing decisions, conglomerate acquisitions. For each event: what happened to the brand specifically, not just what happened to fashion generally.

"design_philosophy"
  1–2 paragraphs. What this house stands for in craft and aesthetic terms — not marketing language, but specific observable things. What does a piece from this house do that a piece from a different house does not? What constraints or values guide every design decision?

"creative_direction"
  1–2 paragraphs. The key creative directors or designers who shaped the house's output — in chronological order, with approximate dates and a sentence on what each one changed or cemented. If the house has always been designer-led by a family member, say so and describe the continuity.

"craft_signature"
  1–2 paragraphs. The specific techniques, materials, or construction methods that define this house's work. What did they originate, refine, or become known for? Include material sourcing if relevant (specific tanneries, specific mills, specific regions). If they hold patents, what for?

"current_status"
  1 paragraph. Current ownership (independent, LVMH, Kering, Richemont, family-held, other), current creative direction, market positioning today, and whether the house is growing, stable, or contracting. Be specific about what changed most recently.

Total: 900–1300 words.
Return only valid JSON, nothing else."""


# ── Generation ──────────────────────────────────────────────────────────────

def generate_brand_content(brand_name, existing_content=""):
    existing_block = ""
    if existing_content.strip():
        existing_block = f"\nExisting page content (use as supplementary context):\n---\n{existing_content}\n---\n"

    prompt = BRAND_HERITAGE_PROMPT.format(
        brand_name=brand_name,
        existing_content_block=existing_block,
    )
    msg = claude.messages.create(
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


def build_blocks(content):
    blocks = [
        {"type": "divider", "divider": {}},
        h2(BRAND_HERITAGE_MARKER),
    ]
    for key, label in [
        ("founding_story",    "Founding Story"),
        ("family_and_founders", "Family & Founders"),
        ("historical_moments",  "Historical Moments"),
        ("design_philosophy",   "Design Philosophy"),
        ("creative_direction",  "Creative Direction"),
        ("craft_signature",     "Craft Signature"),
        ("current_status",      "Current Status"),
    ]:
        blocks.append(h3(label))
        for p in content.get(key, "").split("\n\n"):
            p = p.strip()
            if p:
                blocks.append(para(p))
    return blocks


# ── Main ────────────────────────────────────────────────────────────────────

def process_brand(page, force=False):
    brand_name = get_brand_name(page)
    if not brand_name:
        print("     (no name — skipping)")
        return "skipped"

    page_id = page["id"]

    if not force and page_has_brand_heritage(page_id):
        print("     Already has brand heritage — skipping")
        return "skipped"

    existing = read_existing_page_content(page_id)
    if existing:
        print(f"     Found {len(existing.splitlines())} lines of existing content")

    if force:
        deleted = delete_brand_heritage_blocks(page_id)
        print(f"     Cleared {deleted} existing blocks")

    print("     Generating brand heritage...")
    content = generate_brand_content(brand_name, existing)
    blocks = build_blocks(content)
    append_blocks_to_page(page_id, blocks)
    print(f"     Written ({len(blocks)} blocks)")
    return "done"


def main():
    parser = argparse.ArgumentParser(description="Write brand heritage to Notion designer pages")
    parser.add_argument("--force", metavar="BRAND_NAME", help="Clear and rewrite one specific brand (exact name)")
    parser.add_argument("--list", action="store_true", help="List all brands in the designer database")
    args = parser.parse_args()

    print("\nFetching brands from designer database...")
    brands = get_all_brands()
    print(f"  {len(brands)} brands found\n")

    if args.list:
        for page in brands:
            name = get_brand_name(page)
            has = page_has_brand_heritage(page["id"])
            status = "✓ has heritage" if has else "  missing"
            print(f"  {status}  {name}")
        return

    written = skipped = errors = 0

    if args.force:
        target = args.force.strip().lower()
        matched = [p for p in brands if get_brand_name(p).lower() == target]
        if not matched:
            print(f"Brand '{args.force}' not found. Use --list to see all brand names.")
            sys.exit(1)
        page = matched[0]
        brand_name = get_brand_name(page)
        print(f"\n  → {brand_name!r}")
        try:
            process_brand(page, force=True)
        except Exception as e:
            print(f"     ERROR: {e}")
        return

    for page in brands:
        brand_name = get_brand_name(page)
        if not brand_name:
            continue
        print(f"\n  → {brand_name!r}")
        try:
            result = process_brand(page, force=False)
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
