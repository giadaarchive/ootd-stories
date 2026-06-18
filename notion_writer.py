#!/usr/bin/env python3
"""
Writes approved outfit entries to the Notion OOTD database.

Creates a new page with:
- Name (title): "OOTD YYYY-MM-DD" or "OOTD YYYY-MM-DD (2)" for same-day extras
- Worn (date): ISO date string
- Items Worn (relation): list of approved Collection page IDs
- Image block: uploaded to GitHub raw URL or Imgur fallback
"""

import os, json, base64, time, requests
from dotenv import load_dotenv
load_dotenv()

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
OOTD_DB_ID = os.environ["NOTION_DATABASE_ID"]
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "giadaarchive/ootd-stories")

NOTION_H = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def _existing_ootd_count(date_str: str) -> int:
    """Count how many OOTD entries exist for a given date."""
    r = requests.post(
        f"https://api.notion.com/v1/databases/{OOTD_DB_ID}/query",
        headers=NOTION_H,
        json={
            "filter": {
                "property": "Worn",
                "date": {"equals": date_str},
            },
            "page_size": 10,
        },
    )
    if r.status_code != 200:
        return 0
    return len(r.json().get("results", []))


def _make_title(date_str: str) -> str:
    existing = _existing_ootd_count(date_str)
    if existing == 0:
        return f"OOTD {date_str}"
    return f"OOTD {date_str} ({existing + 1})"


def upload_to_github(image_bytes: bytes, date_str: str, suffix: str = "") -> str | None:
    """
    Push outfit photo to giadaarchive/collection-images repo (public, permanent URLs).
    Uses the scripts branch of ootd-stories as fallback.
    Returns raw.githubusercontent.com URL or None on failure.
    """
    if not GITHUB_TOKEN:
        print("  [image] no GITHUB_TOKEN, skipping GitHub upload")
        return None

    # Use collection-images repo for public permanent image hosting
    image_repo = "giadaarchive/collection-images"
    filename = f"ootd/{date_str}/outfit{suffix}.jpg"
    api_url = f"https://api.github.com/repos/{image_repo}/contents/{filename}"
    b64 = base64.b64encode(image_bytes).decode()
    gh_headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    # Get SHA if file exists (required for updates)
    existing = requests.get(api_url, headers=gh_headers, timeout=15)
    body = {"message": f"outfit {date_str}", "content": b64}
    if existing.status_code == 200:
        body["sha"] = existing.json()["sha"]

    r = requests.put(api_url, headers=gh_headers, json=body, timeout=30)
    if r.status_code in (200, 201):
        url = f"https://raw.githubusercontent.com/{image_repo}/main/{filename}"
        print(f"  [image] uploaded to GitHub: {url}")
        return url

    print(f"  [image] GitHub upload failed: {r.status_code} {r.text[:200]}")
    return None


def upload_to_imgur(image_bytes: bytes) -> str | None:
    """Anonymous Imgur upload. Returns direct image URL or None."""
    client_id = os.environ.get("IMGUR_CLIENT_ID", "")
    if not client_id:
        return None
    r = requests.post(
        "https://api.imgur.com/3/image",
        headers={"Authorization": f"Client-ID {client_id}"},
        data={"image": base64.b64encode(image_bytes).decode(), "type": "base64"},
        timeout=30,
    )
    if r.status_code == 200:
        return r.json()["data"]["link"]
    return None


def upload_to_freeimage(image_bytes: bytes) -> str | None:
    """
    Upload to freeimage.host — anonymous, permanent URLs, no account needed.
    Returns direct image URL or None.
    """
    b64 = base64.b64encode(image_bytes).decode()
    r = requests.post(
        "https://freeimage.host/api/1/upload",
        data={
            "key": "6d207e02198a847aa98d0a2a901485a5",  # public demo key
            "source": b64,
            "format": "json",
        },
        timeout=30,
    )
    if r.status_code == 200:
        url = r.json().get("image", {}).get("url")
        if url:
            print(f"  [image] uploaded to freeimage: {url}")
            return url
    print(f"  [image] freeimage upload failed: {r.status_code} {r.text[:200]}")
    return None


def host_image(image_bytes: bytes, date_str: str = "", suffix: str = "") -> str | None:
    """Try GitHub, then freeimage.host, then Imgur."""
    if date_str:
        url = upload_to_github(image_bytes, date_str, suffix)
        if url:
            return url
    url = upload_to_freeimage(image_bytes)
    if url:
        return url
    return upload_to_imgur(image_bytes)


def create_ootd_entry(
    date_str: str,
    item_ids: list[str],
    image_urls: list[str] | None = None,
    season: str | None = None,
) -> str:
    """
    Create an OOTD page in Notion.

    date_str:   ISO date "YYYY-MM-DD"
    item_ids:   Collection page IDs to link via Items relation
    image_urls: list of public URLs — each becomes an image block on the page
    season:     "SS" or "AW" — written to the Style select property

    Returns the new page ID.
    """
    title = _make_title(date_str)

    properties = {
        "Name": {"title": [{"text": {"content": title}}]},
        "Worn": {"date": {"start": date_str}},
        "Items": {"relation": [{"id": pid} for pid in item_ids]},
    }

    if season in ("SS", "AW"):
        properties["Style"] = {"select": {"name": season}}

    body = {
        "parent": {"database_id": OOTD_DB_ID},
        "properties": properties,
    }

    if image_urls:
        body["children"] = [
            {
                "object": "block",
                "type": "image",
                "image": {"type": "external", "external": {"url": url}},
            }
            for url in image_urls
        ]

    r = requests.post(
        "https://api.notion.com/v1/pages",
        headers=NOTION_H,
        json=body,
    )
    r.raise_for_status()
    page_id = r.json()["id"]
    print(f"Created OOTD page: {title} → {page_id}")
    return page_id


if __name__ == "__main__":
    import sys
    from datetime import date
    # Quick smoke test: create a test entry with no items
    today = date.today().isoformat()
    print(f"Creating test OOTD entry for {today}...")
    pid = create_ootd_entry(today, [], None)
    print(f"OK: {pid}")
