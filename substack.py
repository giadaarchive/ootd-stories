#!/usr/bin/env python3
"""
Post one OOTD entry (Substack status = "Post to Substack") to giadaarchive.substack.com.
Scheduled Mon/Thu via launchd. Marks entry as "Posted" in Notion when done.
"""

import base64
import io
import json
import os
import re
import time
from datetime import datetime, timezone, timedelta
import requests
from PIL import Image
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

NOTION_TOKEN    = os.environ["NOTION_TOKEN"]
DATABASE_ID     = os.environ["NOTION_DATABASE_ID"]
GITHUB_TOKEN    = os.environ["GITHUB_TOKEN"]
GITHUB_REPO     = os.environ["GITHUB_REPO"]

PUB_NAME       = "giadaarchive"
PUB_BASE       = f"https://{PUB_NAME}.substack.com"
STATUS_PENDING = "Post to Substack"
STATUS_DONE    = "Posted"
MAX_IMAGES     = 3
MAX_IMG_BYTES  = 4 * 1024 * 1024
COOKIE_FILE    = os.path.join(os.path.dirname(__file__), ".substack_cookies.json")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


# ── Auth (Playwright context) ─────────────────────────────────────────────────

def load_cookies_into_context(context):
    if not os.path.exists(COOKIE_FILE):
        raise RuntimeError(
            f"No cookie file found at {COOKIE_FILE}.\n"
            "Run: python3 setup_cookies.py"
        )
    with open(COOKIE_FILE) as f:
        data = json.load(f)

    if isinstance(data, list):
        # New format: list of {name, value, domain, path}
        pw_cookies = []
        for c in data:
            pw_cookies.append({
                "name": c["name"],
                "value": c["value"],
                "domain": c.get("domain", ".substack.com"),
                "path": c.get("path", "/"),
            })
        context.add_cookies(pw_cookies)
    else:
        # Old format: plain dict — apply to both substack domains
        pw_cookies = []
        for name, value in data.items():
            for domain in [".substack.com", PUB_NAME + ".substack.com"]:
                pw_cookies.append({"name": name, "value": value, "domain": domain, "path": "/"})
        context.add_cookies(pw_cookies)


def verify_session(api):
    r = api.post(f"{PUB_BASE}/api/v1/drafts", data=json.dumps({
        "draft_title": "__auth_check__",
        "draft_subtitle": "",
        "draft_body": json.dumps({"type": "doc", "content": []}),
        "audience": "everyone",
        "draft_bylines": [{"id": 2603511, "is_guest": False}],
        "section_chosen": False,
    }), headers={"Content-Type": "application/json"})
    if r.status in (200, 201):
        post_id = r.json().get("id")
        if post_id:
            api.delete(f"{PUB_BASE}/api/v1/drafts/{post_id}")
        return True
    return False


# ── Notion ────────────────────────────────────────────────────────────────────

def fetch_pending():
    pages, cursor = [], None
    while True:
        body = {
            "filter": {"property": "Substack", "status": {"equals": STATUS_PENDING}},
            "sorts": [{"property": "Worn", "direction": "ascending"}],
            "page_size": 100,
        }
        if cursor:
            body["start_cursor"] = cursor
        r = requests.post(
            f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
            headers=NOTION_HEADERS, json=body,
        )
        r.raise_for_status()
        data = r.json()
        pages.extend(data["results"])
        if not data.get("has_more"):
            break
        cursor = data["next_cursor"]
    return pages


def get_page_images(page_id):
    urls, cursor = [], None
    while True:
        url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        if cursor:
            url += f"?start_cursor={cursor}"
        r = requests.get(url, headers=NOTION_HEADERS)
        r.raise_for_status()
        data = r.json()
        for block in data.get("results", []):
            if block.get("type") == "image":
                img = block["image"]
                src = img["file"]["url"] if img.get("type") == "file" else img["external"]["url"]
                urls.append(src)
        if not data.get("has_more"):
            break
        cursor = data["next_cursor"]
    return urls


_page_title_cache = {}

def _fetch_page_title(page_id):
    if page_id in _page_title_cache:
        return _page_title_cache[page_id]
    r = requests.get(f"https://api.notion.com/v1/pages/{page_id}", headers=NOTION_HEADERS)
    if r.status_code != 200:
        return None
    props = r.json().get("properties", {})
    title_prop = next((v for v in props.values() if v.get("type") == "title"), None)
    title = title_prop["title"][0].get("plain_text") if title_prop and title_prop.get("title") else None
    _page_title_cache[page_id] = title
    return title


def get_items_tags(page):
    brands, seasons, colours = set(), set(), set()
    item_ids = [x["id"] for x in page["properties"].get("Items", {}).get("relation", [])]

    for item_id in item_ids:
        r = requests.get(f"https://api.notion.com/v1/pages/{item_id}", headers=NOTION_HEADERS)
        if r.status_code != 200:
            continue
        p = r.json().get("properties", {})

        for s in p.get("Season", {}).get("multi_select", []):
            seasons.add(s["name"])

        sku_rt = p.get("SKU", {}).get("rich_text", [])
        sku_prefix = sku_rt[0]["plain_text"].split("-")[0].upper() if sku_rt else ""

        if sku_prefix == "UNB":
            pass
        elif sku_prefix == "MTM":
            brands.add("MTM")
        else:
            for d in p.get("Designer", {}).get("relation", []):
                name = _fetch_page_title(d["id"])
                if name:
                    brands.add(name)

        for c in p.get("Colour", {}).get("relation", []):
            name = _fetch_page_title(c["id"])
            if name:
                colours.add(name)

    return sorted(brands), sorted(seasons), sorted(colours)


def mark_posted(page_id):
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=NOTION_HEADERS,
        json={"properties": {"Substack": {"status": {"name": STATUS_DONE}}}},
    )
    return r.status_code == 200


# ── Images ────────────────────────────────────────────────────────────────────

def download_image(url):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.content
    ct = r.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
    if ct not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        ct = "image/jpeg"

    if len(data) > MAX_IMG_BYTES:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        scale = 0.7
        while True:
            w, h = int(img.width * scale), int(img.height * scale)
            buf = io.BytesIO()
            img.resize((w, h), Image.LANCZOS).save(buf, format="JPEG", quality=85)
            if buf.tell() <= MAX_IMG_BYTES or scale < 0.2:
                data, ct = buf.getvalue(), "image/jpeg"
                break
            scale *= 0.7

    return data, ct


def upload_image_to_github(image_data, content_type, path):
    """Upload image to GitHub repo and return raw CDN URL."""
    ext = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}.get(content_type, "jpg")
    filepath = f"{path}.{ext}"
    encoded = base64.b64encode(image_data).decode()

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    # Check if file already exists (get its SHA to update)
    check = requests.get(
        f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filepath}",
        headers=headers,
    )
    payload = {"message": f"Add {filepath}", "content": encoded}
    if check.status_code == 200:
        payload["sha"] = check.json()["sha"]

    r = requests.put(
        f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filepath}",
        headers=headers,
        json=payload,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"GitHub upload failed ({r.status_code}): {r.text[:200]}")

    return f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{filepath}"


# ── Post builder ──────────────────────────────────────────────────────────────

def build_body_json(image_urls, story_text):
    content = []
    for url in image_urls:
        content.append({
            "type": "image",
            "attrs": {
                "src": url, "fullscreen": False, "imageSize": "normal",
                "height": None, "width": None, "resizeWidth": None,
                "bytes": None, "alt": None, "title": None, "type": None,
                "href": None, "belowTheFold": False, "internalRedirectUrl": None,
                "isProcessing": False, "id": None,
            },
        })
    for para in story_text.split("\n\n"):
        para = para.strip()
        if para:
            content.append({"type": "paragraph", "content": [{"type": "text", "text": para}]})
    return {"type": "doc", "content": content}


def next_daily_slots(count, hour_utc=1):
    """Return `count` consecutive daily datetimes at hour_utc (UTC), starting tomorrow."""
    now = datetime.now(timezone.utc)
    start = (now + timedelta(days=1)).replace(hour=hour_utc, minute=0, second=0, microsecond=0)
    return [start + timedelta(days=i) for i in range(count)]


def post_to_substack(api, title, body_json, tags, schedule_dt=None):
    r = api.post(
        f"{PUB_BASE}/api/v1/drafts",
        data=json.dumps({
            "draft_title": title,
            "draft_subtitle": "",
            "draft_podcast_url": None,
            "draft_podcast_duration": None,
            "draft_body": json.dumps(body_json),
            "section_chosen": False,
            "draft_section_id": None,
            "draft_bylines": [{"id": 2603511, "is_guest": False}],
            "audience": "everyone",
        }),
        headers={"Content-Type": "application/json"},
    )
    if r.status not in (200, 201):
        raise RuntimeError(f"Draft creation failed ({r.status}): {r.text()[:300]}")

    post_id = r.json().get("id")
    print(f"  Draft created (id={post_id})")

    if tags and post_id:
        try:
            api.put(
                f"{PUB_BASE}/api/v1/posts/{post_id}/tags",
                data=json.dumps({"tags": [{"name": t} for t in tags]}),
                headers={"Content-Type": "application/json"},
            )
        except Exception as e:
            print(f"  Tag warning: {e}")

    publish_payload = {"audience": "everyone", "send": True}
    if schedule_dt:
        publish_payload["post_date"] = schedule_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    r2 = api.post(
        f"{PUB_BASE}/api/v1/drafts/{post_id}/publish",
        data=json.dumps(publish_payload),
        headers={"Content-Type": "application/json"},
    )
    if r2.status not in (200, 201):
        raise RuntimeError(f"Publish failed ({r2.status}): {r2.text()[:200]}")

    url = r2.json().get("canonical_url") or f"{PUB_BASE}/p/{post_id}"
    return url, post_id


# ── Main ──────────────────────────────────────────────────────────────────────

def process_entry(page, api, schedule_dt):
    page_id = page["id"]
    props = page["properties"]

    story_rt = props.get("OOTD Story", {}).get("rich_text", [])
    story = "".join(x.get("plain_text", "") for x in story_rt)

    lines = story.strip().split("\n")
    title_match = re.match(r"^\*\*(.+?)\*\*$", lines[0].strip())
    post_title = title_match.group(1) if title_match else lines[0].strip()
    story_body = "\n".join(lines[1:]).strip()

    print(f"\n[{schedule_dt.strftime('%a %d %b %Y %H:%M UTC')}] {post_title}")

    if not story_body:
        print("  No story yet — skipping")
        return False

    image_notion_urls = get_page_images(page_id)
    if not image_notion_urls:
        print("  No images — skipping")
        return False
    print(f"  {len(image_notion_urls)} image(s) found")

    print("  Collecting tags...")
    brands, seasons, colours = get_items_tags(page)
    all_tags = brands + seasons + colours
    print(f"  Tags: {all_tags}")

    print("  Uploading images to GitHub...")
    worn_date = props.get("Worn", {}).get("date", {})
    date_str = (worn_date.get("start") or "unknown").replace("-", "") if worn_date else "unknown"
    github_urls = []
    for i, notion_url in enumerate(image_notion_urls[:MAX_IMAGES]):
        try:
            img_data, ct = download_image(notion_url)
            gh_path = f"images/{date_str}_{page_id[:8]}_{i+1}"
            gh_url = upload_image_to_github(img_data, ct, gh_path)
            github_urls.append(gh_url)
            print(f"    Image {i+1} → {gh_url}")
        except Exception as e:
            print(f"    Image {i+1} upload failed: {e}")

    if not github_urls:
        print("  No images uploaded — skipping")
        return False

    body_json = build_body_json(github_urls, story_body)
    post_url, _ = post_to_substack(api, post_title, body_json, all_tags, schedule_dt)
    print(f"  Scheduled: {post_url}")

    mark_posted(page_id)
    print("  Marked as Posted in Notion")
    return True


def main():
    print("Fetching pending entries...")
    pages = fetch_pending()
    print(f"  {len(pages)} entries queued")

    if not pages:
        print("Nothing to schedule.")
        return

    slots = next_daily_slots(len(pages), hour_utc=1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()

        print("  Loading Substack session...")
        load_cookies_into_context(context)

        api = context.request

        if not verify_session(api):
            browser.close()
            raise RuntimeError(
                "Substack session invalid or expired.\n"
                "Run: python3 setup_cookies.py"
            )
        print("  Session verified.\n")

        scheduled, skipped = 0, 0
        for page, slot in zip(pages, slots):
            try:
                ok = process_entry(page, api, slot)
                if ok:
                    scheduled += 1
                else:
                    skipped += 1
            except Exception as e:
                print(f"  ERROR: {e}")
                skipped += 1

        browser.close()

    print(f"\nDone. {scheduled} posts scheduled, {skipped} skipped.")


if __name__ == "__main__":
    main()
