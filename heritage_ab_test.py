#!/usr/bin/env python3
"""
A/B test: three-pass pipeline comparison for heritage notes.

  A: Qwen draft only (no research, no audit)
  B: Qwen research + Qwen draft + Claude audit  ← full pipeline

Usage:
  python3 heritage_ab_test.py <notion_page_id>

Does NOT write to Notion. Cost logged to stderr.
"""
import json
import sys

from dotenv import load_dotenv
load_dotenv()

import llm as llm_module
import research_agent
from heritage import (
    SYSTEM_PROMPT, REVIEW_PROMPT, DRAFT_MODEL, REVIEW_MODEL,
    DESIGNER_ERAS, NOTION_HEADERS,
    build_user_prompt, build_research_prompt, _parse_json,
    extract_item_details, read_page_description, get_brand_for_page,
    get_page_image_urls,
)
import requests


def fetch_page(page_id):
    r = requests.get(f"https://api.notion.com/v1/pages/{page_id}", headers=NOTION_HEADERS)
    r.raise_for_status()
    return r.json()


def run_ab(page_id):
    page      = fetch_page(page_id)
    brand, era_ctx = get_brand_for_page(page)
    item      = extract_item_details(page)
    page_desc = read_page_description(page_id)
    image_urls = get_page_image_urls(page_id)

    if brand == "Unknown":
        brand = item["name"].split()[0] if item["name"] else "Unknown"

    print(f"\n{'='*72}")
    print(f"  {brand} — {item['name']}")
    print(f"  category: {item['category']}  material: {item['material']}  year: {item['year']}")
    print(f"  images found: {len(image_urls)}")
    print(f"{'='*72}\n")

    # ── Version A: Qwen draft only (baseline) ────────────────────────────────
    print("── A: Qwen draft only (no research, no audit) ──────────────────────────")
    user_msg_a = build_user_prompt(brand, item, era_ctx, page_desc)
    raw_a = llm_module.call(SYSTEM_PROMPT, user_msg_a, max_tokens=1800, model=DRAFT_MODEL)
    ver_a = _parse_json(raw_a)
    for key, text in ver_a.items():
        print(f"\n[{key.upper()}]")
        print(text)
    cost_a = llm_module.session_cost()["usd"]
    print(f"\n→ Baseline cost: ${cost_a:.4f}")

    # ── Version B: Research + Draft + Audit ──────────────────────────────────
    print("\n\n── B: Qwen-VL vision + Qwen research + Qwen draft + Claude audit ────────")
    notes = research_agent.research(
        brand=brand,
        item_name=item["name"],
        year=item.get("year", ""),
        category=item.get("category", ""),
        material=item.get("material", ""),
        image_urls=image_urls[:6],
    )

    user_msg_b = build_research_prompt(brand, item, notes, era_ctx)
    raw_b = llm_module.call(SYSTEM_PROMPT, user_msg_b, max_tokens=1800, model=DRAFT_MODEL)
    draft_b = _parse_json(raw_b)

    sources_note = ""
    if notes.get("sources"):
        sources_note = f"\nResearch sources: {', '.join(notes['sources'][:5])}"
    review_user = (
        f"Item: {brand} — {item['name']} ({item.get('year','')}){sources_note}\n\n"
        f"Draft to fact-check and validate:\n{json.dumps(draft_b, indent=2)}"
    )
    raw_b2 = llm_module.call(REVIEW_PROMPT, review_user, max_tokens=1800, model=REVIEW_MODEL)
    ver_b = _parse_json(raw_b2)

    for key, text in ver_b.items():
        print(f"\n[{key.upper()}]")
        print(text)

    cost_b = llm_module.session_cost()["usd"]
    print(f"\n→ Full pipeline cost: ${cost_b:.4f}  (research + audit adds: ${cost_b - cost_a:.4f})")
    print(f"\n{'='*72}")
    print("  Compare A vs B. Full pipeline should show: specific CD name, verified")
    print("  dates, visual details from images, sourced historical context.")
    print(f"{'='*72}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 heritage_ab_test.py <notion_page_id>")
        sys.exit(1)
    raw_id = sys.argv[1].strip().split("?")[0]
    # Accept full URL or bare ID
    page_id = raw_id.split("/")[-1].replace("-", "")[-32:]
    run_ab(page_id)
