#!/usr/bin/env python3
"""
Deinfluence Tagger
Reads your notes from the "L's comments and thoughts" field on a Notion entry,
then uses Claude to generate multi-select tags for "Why i was considering"
and "Why ultimately no".

Usage:
  # Tag a single entry (reads L's comments and thoughts from Notion):
  python3 deinfluence_tag.py <notion_page_url_or_id>

  # Tag with inline notes (skips whatever is in Notion):
  python3 deinfluence_tag.py <notion_page_url_or_id> "I love the patina but the logo is too much"

  # Tag all entries in the database that have notes but no tags yet:
  python3 deinfluence_tag.py --all
"""

import os
import re
import sys
import json
import requests
import anthropic
from dotenv import load_dotenv

load_dotenv("/Users/lisa/lookbook-stories/.env")

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DEINFLUENCE_DB_ID = os.environ.get("DEINFLUENCE_DB_ID", "349ccd15cda18030876add491c9b992c")
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

APPROVED_YES_TAGS = [
    "vintage-provenance", "investment-piece", "natural-patina", "travel-worthy",
    "craftsmanship", "rare-find", "brand-legacy", "versatile", "timeless-silhouette",
    "love-the-designer", "brand-discovery", "pattern-integrity", "colour",
    "sentimental", "gifted",
]

APPROVED_NO_TAGS = [
    "visible-logo", "loud-branding", "logo-fatigue",
    "price", "condition", "size-wrong", "wrong-colour",
    "wrong-fabric-for-use-case", "misleading-material-claim",
    "too-common-silhouette", "derivative-design",
    "doesnt-fit-my-wardrobe", "doesnt-fit-my-style",
    "have-equivalent-in-wardrobe", "have-better-in-wardrobe",
]

SYSTEM_PROMPT = f"""You generate multi-select tags for a personal fashion deinfluence tracker.

STRICT RULES:
- You MUST only use tags from the approved lists below. Do not invent new tags.
- If nothing from the approved list fits, omit that category rather than inventing a tag.
- Max 5 tags per category. Prefer fewer, stronger tags over many.
- Tags reflect WHY (emotional or practical reason), not WHAT (the item feature).

APPROVED why_considering tags (use ONLY these):
{", ".join(APPROVED_YES_TAGS)}

APPROVED why_no tags (use ONLY these):
{", ".join(APPROVED_NO_TAGS)}

Key distinctions:
- have-equivalent-in-wardrobe: already own something doing the same job, similar aesthetic — would be a duplicate
- have-better-in-wardrobe: already own something that outperforms this — this would be a downgrade
- doesnt-fit-my-wardrobe: no natural home for this item, nothing to wear it with
- doesnt-fit-my-style: appealing but not who she is — identity gap, not a logistics gap
- love-the-designer: drawn to the specific creative person and their vision (e.g. Lemaire as designer-owner)
- brand-legacy: drawn to the brand's institutional history, not one specific person"""


def extract_page_id(url_or_id):
    """Extract Notion page ID from a URL or raw ID."""
    # URL pattern: .../<title>-<32-char-hex> or .../p/<32-char-hex>
    match = re.search(r"([a-f0-9]{32})(?:[?#]|$)", url_or_id.replace("-", ""))
    if match:
        raw = match.group(1)
        # Reformat as UUID: 8-4-4-4-12
        return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
    return url_or_id


def get_page(page_id):
    """Fetch a Notion page and return its properties."""
    resp = requests.get(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=NOTION_HEADERS,
    )
    resp.raise_for_status()
    return resp.json()


def get_page_body_text(page_id):
    """Fetch the text content from the page body blocks (description)."""
    resp = requests.get(
        f"https://api.notion.com/v1/blocks/{page_id}/children",
        headers=NOTION_HEADERS,
    )
    resp.raise_for_status()
    blocks = resp.json().get("results", [])
    texts = []
    for b in blocks:
        btype = b.get("type")
        content = b.get(btype, {})
        rich = content.get("rich_text", [])
        for r in rich:
            t = r.get("text", {}).get("content", "")
            if t:
                texts.append(t)
    return " ".join(texts[:500])  # cap to avoid token bloat


def extract_prop_text(prop):
    """Pull text from a Notion property (title, rich_text, or multi_select)."""
    if not prop:
        return ""
    ptype = prop.get("type")
    if ptype == "title":
        return " ".join(r.get("plain_text", "") for r in prop.get("title", []))
    if ptype == "rich_text":
        return " ".join(r.get("plain_text", "") for r in prop.get("rich_text", []))
    if ptype == "multi_select":
        return ", ".join(o.get("name", "") for o in prop.get("multi_select", []))
    if ptype == "url":
        return prop.get("url", "") or ""
    return ""


def already_tagged(page):
    """Return True if both tag properties already have values."""
    props = page.get("properties", {})
    yes_tags = props.get("Why i was considering", {}).get("multi_select", [])
    no_tags = props.get("Why ultimately no", {}).get("multi_select", [])
    return bool(yes_tags) and bool(no_tags)


def generate_tags(title, description, notes):
    """Call Claude to generate why_considering and why_no tags."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt_parts = [f"Item: {title}"]
    if description:
        prompt_parts.append(f"Item details: {description[:1500]}")
    if notes:
        prompt_parts.append(f"Owner's notes: {notes}")

    prompt_parts.append('\nReturn JSON only:\n{"why_considering": ["tag", ...], "why_no": ["tag", ...]}')

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": "\n".join(prompt_parts)}],
    )

    text = response.content[0].text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # Extract first complete JSON object
    start = text.find("{")
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start: i + 1])
    raise ValueError(f"Could not parse tags from: {text[:200]}")


def update_tags(page_id, why_considering, why_no):
    """Patch the two multi_select properties on a Notion page."""
    payload = {"properties": {}}
    if why_considering:
        payload["properties"]["Why i was considering"] = {
            "multi_select": [{"name": t} for t in why_considering]
        }
    if why_no:
        payload["properties"]["Why ultimately no"] = {
            "multi_select": [{"name": t} for t in why_no]
        }
    resp = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=NOTION_HEADERS,
        json=payload,
    )
    resp.raise_for_status()


def process_page(page_id, inline_notes=None):
    """Tag a single page. Returns the tags applied."""
    page = get_page(page_id)
    props = page.get("properties", {})

    title = extract_prop_text(props.get("Item - Third Best", {}))
    notes = inline_notes or extract_prop_text(props.get("L's comments and thoughts", {}))

    if not notes:
        print(f"  ⚠ No notes found for: {title or page_id} — skipping (add notes to 'L's comments and thoughts' first)")
        return None

    description = get_page_body_text(page_id)

    print(f"  Tagging: {title}")
    tags = generate_tags(title, description, notes)

    why_yes = tags.get("why_considering", [])
    why_no = tags.get("why_no", [])

    update_tags(page_id, why_yes, why_no)

    print(f"    considering : {', '.join(why_yes)}")
    print(f"    no because  : {', '.join(why_no)}")
    return tags


def get_all_database_pages():
    """Fetch all pages from the Deinfluence database."""
    pages = []
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        resp = requests.post(
            f"https://api.notion.com/v1/databases/{DEINFLUENCE_DB_ID}/query",
            headers=NOTION_HEADERS,
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
        pages.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return pages


def main():
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        sys.exit(1)

    if args[0] == "--all":
        print("Fetching all entries...")
        pages = get_all_database_pages()
        skipped = 0
        tagged = 0
        for page in pages:
            page_id = page["id"]
            if already_tagged(page):
                skipped += 1
                continue
            result = process_page(page_id)
            if result:
                tagged += 1
        print(f"\nDone. Tagged: {tagged}, skipped (already tagged): {skipped}")
        return

    page_id = extract_page_id(args[0])
    inline_notes = args[1] if len(args) > 1 else None
    process_page(page_id, inline_notes)


if __name__ == "__main__":
    main()
