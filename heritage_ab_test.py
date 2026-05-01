#!/usr/bin/env python3
"""
A/B test: compare Qwen-draft-only vs Qwen-draft+Claude-review for heritage notes.

Usage:
  python3 heritage_ab_test.py <notion_page_id>

Outputs two versions side-by-side to stdout. Does NOT write to Notion.
"""
import json
import os
import sys

from dotenv import load_dotenv
load_dotenv()

import llm as llm_module
from heritage import (
    SYSTEM_PROMPT, REVIEW_PROMPT, DRAFT_MODEL, REVIEW_MODEL,
    build_user_prompt, _parse_json, DESIGNER_ERAS,
)
from heritage import get_brand_and_item  # noqa: we'll call fetch helpers directly

import requests

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}
COLLECTION_DB_ID = "ad079964969043ae9fa85a4f3ca1a9ee"


def fetch_page_data(page_id):
    r = requests.get(f"https://api.notion.com/v1/pages/{page_id}", headers=NOTION_HEADERS)
    r.raise_for_status()
    return r.json()


def extract_brand_item(page):
    props = page.get("properties", {})
    def txt(key):
        p = props.get(key, {})
        if p.get("type") == "title":
            return "".join(x["plain_text"] for x in p.get("title", []))
        if p.get("type") == "rich_text":
            return "".join(x["plain_text"] for x in p.get("rich_text", []))
        if p.get("type") == "select":
            s = p.get("select")
            return s["name"] if s else ""
        return ""

    brand = txt("Designer") or txt("Brand") or "Unknown"
    name  = txt("Name") or txt("Title") or txt("Item")
    return brand, name


def run_ab(page_id):
    page = fetch_page_data(page_id)
    brand, item = extract_brand_item(page)
    era_ctx = DESIGNER_ERAS.get(brand, "")
    user_msg = build_user_prompt(brand, item, era_ctx, "")

    print(f"\n{'='*70}")
    print(f"Item: {brand} — {item}")
    print(f"{'='*70}\n")

    # Version A: Qwen only
    print("── VERSION A: Qwen draft only ──────────────────────────────────────")
    raw_a = llm_module.call(SYSTEM_PROMPT, user_msg, max_tokens=1800, model=DRAFT_MODEL)
    version_a = _parse_json(raw_a)
    for key, text in version_a.items():
        print(f"\n[{key}]\n{text}")

    cost_after_a = llm_module.session_cost()
    print(f"\n→ Cost after A: ${cost_after_a['usd']:.4f}")

    # Version B: Qwen draft + Claude review
    print("\n\n── VERSION B: Qwen draft + Claude review ───────────────────────────")
    raw_b = llm_module.call(SYSTEM_PROMPT, user_msg, max_tokens=1800, model=DRAFT_MODEL)
    draft_b = _parse_json(raw_b)
    review_user = (
        f"Original item context:\n{user_msg}\n\n"
        f"Draft to review:\n{json.dumps(draft_b, indent=2)}"
    )
    raw_b2 = llm_module.call(REVIEW_PROMPT, review_user, max_tokens=1800, model=REVIEW_MODEL)
    version_b = _parse_json(raw_b2)
    for key, text in version_b.items():
        print(f"\n[{key}]\n{text}")

    cost_after_b = llm_module.session_cost()
    print(f"\n→ Cost after B: ${cost_after_b['usd']:.4f}  (delta for B: ${cost_after_b['usd'] - cost_after_a['usd']:.4f})")

    print(f"\n{'='*70}")
    print("Compare the two versions above and decide which pipeline to keep.")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 heritage_ab_test.py <notion_page_id>")
        sys.exit(1)
    run_ab(sys.argv[1])
