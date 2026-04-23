#!/usr/bin/env python3
"""
Deinfluence Collector
Takes a URL of a shop listing and adds it to the Notion Deinfluence database.
Usage: python deinfluence_collector.py <URL>
"""

import os
import sys
import re
import json
import requests
import anthropic
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DEINFLUENCE_DB_ID = os.environ.get("DEINFLUENCE_DB_ID", "349ccd15cda18030876add491c9b992c")
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def scrape_listing(url):
    """Scrape a shop listing with Playwright. Returns raw dict with title, page_text, images."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
            locale="ja-JP",
        )
        page = ctx.new_page()
        wait_event = "domcontentloaded" if "fril.jp" in url else "load"
        page.goto(url, wait_until=wait_event, timeout=60000)
        page.wait_for_timeout(8000)

        html = page.content()

        # Collect meta tags
        metas = page.query_selector_all("meta")
        meta = {}
        for m in metas:
            name = m.get_attribute("property") or m.get_attribute("name") or ""
            content = m.get_attribute("content") or ""
            if content:
                meta[name] = content

        title = meta.get("og:title", meta.get("twitter:title", "")).strip()
        # Strip trailing " by <Platform>" from OG titles
        title = re.sub(r"\s+by\s+\S+$", "", title).strip()

        og_image = meta.get("og:image", "")
        og_description = meta.get("og:description", meta.get("description", ""))
        price_raw = meta.get("product:price:amount", "")
        currency = meta.get("product:price:currency", "")
        price = f"{currency} {price_raw}".strip() if price_raw else None

        page_text = page.inner_text("body")

        # For Yahoo Auctions the item description only loads behind login.
        # Prepend the meta description so Claude has it even when body text is sparse.
        if "auctions.yahoo" in url and og_description:
            page_text = f"[Listing description from meta]:\n{og_description}\n\n[Page body]:\n{page_text}"

        # Extract images by platform, fall back to OG image
        images = []
        if "mercari" in url:
            found = re.findall(
                r"https://static\.mercdn\.net/item/detail/orig/photos/[^\"'>\s\\]+",
                html,
            )
            seen = set()
            for img in found:
                img = img.rstrip("\\")
                if img not in seen:
                    seen.add(img)
                    images.append(img)
            images.sort(
                key=lambda x: int(m.group(1)) if (m := re.search(r"_(\d+)\.jpg", x)) else 99
            )
        elif "yahoo" in url or "auctions.yahoo" in url:
            found = re.findall(r"https://auctions\.c\.yimg\.jp/images\.auctions\.yahoo\.co\.jp/image/[^\"'>\s]+", html)
            seen = set()
            for img in found:
                if img not in seen:
                    seen.add(img)
                    images.append(img)

        if not images and og_image:
            images = [og_image]

        browser.close()

    return {
        "title": title,
        "page_text": page_text,
        "images": images,
        "price": price,
        "url": url,
    }


def translate_and_extract(data):
    """Use Claude to translate and clean up the listing into English."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=[
            {
                "type": "text",
                "text": "You extract and translate fashion/item listing details into clean English for a personal archive database.",
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": f"""Process this shop listing and return a JSON object.

URL: {data['url']}
Raw title: {data['title']}
Price found: {data['price']}

Page text:
{data['page_text'][:5000]}

Return JSON with exactly these keys:
- "title": concise English item title (brand + item type + key detail, e.g. "Louis Vuitton Vintage Keepall 45 Monogram 1987")
- "description": full English translation of the listing description. Do NOT summarise — preserve every detail from the original: brand story, item features, all measurements (waist, length, hip, shoulder etc.), size label, colour, material, era/year, condition notes, included accessories. Use plain text with clear section breaks (Item / Size / Colour / Condition). If the listing has a measurements table, include every figure.
- "price": price string (e.g. "¥67,980") or null
- "source": domain name only (e.g. "jp.mercari.com")

Return only the JSON object, no other text.""",
            }
        ],
    )

    text = response.content[0].text.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # Extract first complete JSON object
    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object in response: {text[:200]}")
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError(f"Unterminated JSON in response: {text[:200]}")


def create_notion_entry(title, description, images, price, source_url, source, reason=""):
    """Create a new page in the Deinfluence Notion database."""
    children = []

    # Images (Notion supports up to 10 external image blocks)
    for img_url in images[:10]:
        children.append({
            "object": "block",
            "type": "image",
            "image": {"type": "external", "external": {"url": img_url}},
        })

    # Decision reason (why not bought)
    if reason:
        children.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": "Why I didn't buy it"}}]},
        })
        for para in reason.split("\n\n"):
            para = para.strip()
            if para:
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": para}}]},
                })

    # Description
    if description:
        children.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": "Description"}}]},
        })
        for para in description.split("\n\n"):
            para = para.strip()
            if para:
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": para}}]},
                })

    properties = {
        "Item - Third Best": {
            "title": [{"type": "text", "text": {"content": title}}]
        },
        "URL": {"url": source_url},
    }
    if price:
        properties["Price"] = {
            "rich_text": [{"type": "text", "text": {"content": price}}]
        }

    payload = {
        "parent": {"database_id": DEINFLUENCE_DB_ID},
        "properties": properties,
        "children": children,
    }

    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers=NOTION_HEADERS,
        json=payload,
    )
    resp.raise_for_status()
    page = resp.json()

    # Set page icon to first image
    if images:
        requests.patch(
            f"https://api.notion.com/v1/pages/{page['id']}",
            headers=NOTION_HEADERS,
            json={"icon": {"type": "external", "external": {"url": images[0]}}},
        )

    return page


def main():
    if len(sys.argv) < 2:
        print("Usage: python deinfluence_collector.py <URL> [--reason 'why I skipped']")
        sys.exit(1)

    args = sys.argv[1:]
    url, reason = None, ""
    i = 0
    while i < len(args):
        if args[i] == "--reason" and i + 1 < len(args):
            reason = args[i + 1]
            i += 2
        elif not args[i].startswith("--"):
            url = args[i]
            i += 1
        else:
            i += 1

    if not url:
        print("Error: provide a product URL.")
        sys.exit(1)

    print(f"Scraping: {url}")

    raw = scrape_listing(url)
    print(f"  Title:  {raw['title']}")
    print(f"  Images: {len(raw['images'])} found")

    print("Translating with Claude...")
    formatted = translate_and_extract(raw)

    title = formatted.get("title") or raw["title"]
    description = formatted.get("description", "")
    price = formatted.get("price") or raw.get("price")
    source = formatted.get("source", "")

    print(f"  → {title}")
    print(f"  → {price}")

    print("Creating Notion entry...")
    result = create_notion_entry(title, description, raw["images"], price, url, source, reason=reason)

    notion_url = result.get("url", "")
    print(f"Done! {notion_url}")


if __name__ == "__main__":
    main()
