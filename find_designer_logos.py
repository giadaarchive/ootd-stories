#!/usr/bin/env python3
"""
Backfill designer house logos for the Designer database.

For every designer page with no "Logo URL" set:
  1. Search Wikimedia Commons for an official logo file.
  2. Download it, rehost to raw.githubusercontent.com (giadaarchive/ootd-stories,
     designer-logos/<slug>/logo.<ext>) so it never expires.
  3. Set the Notion page icon (type: external) and the "Logo URL" property
     to that permanent URL — this becomes the reference point going forward.

Run again any time new designers are added with no logo yet — it only
processes designers where "Logo URL" is empty, so it's safe to re-run.

Usage:
    python3 find_designer_logos.py            # process all missing
    python3 find_designer_logos.py --limit 20 # process first 20 only
    python3 find_designer_logos.py --dry-run  # search only, no writes
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile

import requests
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPO = os.environ.get("GITHUB_REPO", "giadaarchive/ootd-stories")
DESIGNER_DB = "079fa275-238c-4427-94b5-2c0b0f485bf9"

# Generic/placeholder entries, not real houses with a brand mark —
# searching for these returns unrelated matches, so skip outright.
SKIP_NAMES = {"Handmade", "Made to Measure (MTM)"}

NH = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
WIKI_UA = {"User-Agent": "GiadaArchiveLogoBot/1.0 (https://giadaarchive.store; contact hello@giadaarchive.store)"}


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "brand"


def get_missing_designers():
    all_results, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        resp = requests.post(f"https://api.notion.com/v1/databases/{DESIGNER_DB}/query", headers=NH, json=body, timeout=20)
        d = resp.json()
        all_results.extend(d["results"])
        if not d.get("has_more"):
            break
        cursor = d["next_cursor"]

    missing = []
    for p in all_results:
        title = "".join(t.get("plain_text", "") for t in p["properties"].get("Designer/Label", {}).get("title", []))
        logo_url = "".join(t.get("plain_text", "") for t in p["properties"].get("Logo URL", {}).get("rich_text", []))
        if title and title not in SKIP_NAMES and not logo_url.strip():
            missing.append((title, p["id"]))
    return missing


def search_wikimedia_logo(name: str):
    """Return a direct image URL for the brand's logo, or None."""
    query = f"{name} logo"
    search_resp = requests.get(
        "https://commons.wikimedia.org/w/api.php",
        params={
            "action": "query", "list": "search", "srnamespace": 6,
            "srsearch": query, "format": "json", "srlimit": 5,
        },
        timeout=15,
        headers=WIKI_UA,
    )
    hits = search_resp.json().get("query", {}).get("search", [])
    if not hits:
        return None

    # Relevance gate: the file title must contain a real word from the brand
    # name (not just stopwords), or this isn't actually a match for this brand.
    stopwords = {"the", "de", "des", "and", "&", "co", "of", "for", "a", "an"}
    name_words = [w for w in re.sub(r"[^\w\s]", " ", name.lower()).split() if w not in stopwords and len(w) > 2]
    hits = [h for h in hits if any(w in h["title"].lower() for w in name_words)]
    if not hits:
        return None

    # Prefer hits whose title actually contains "logo"
    hits.sort(key=lambda h: 0 if "logo" in h["title"].lower() else 1)

    for hit in hits:
        title = hit["title"]  # e.g. "File:Prada-Logo.svg"
        info_resp = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query", "titles": title, "prop": "imageinfo",
                "iiprop": "url|mime", "format": "json",
            },
            timeout=15,
            headers=WIKI_UA,
        )
        pages = info_resp.json().get("query", {}).get("pages", {})
        for page in pages.values():
            imageinfo = page.get("imageinfo")
            if imageinfo:
                url = imageinfo[0]["url"]
                mime = imageinfo[0].get("mime", "")
                if "svg" in mime or "png" in mime or "jpeg" in mime or "webp" in mime:
                    return url
    return None


def trim_whitespace(path: str, pad: int = 6):
    """Crop a logo image tight to its actual mark. Wikimedia logo files
    often ship with huge surrounding whitespace, which makes them
    effectively invisible at the small size we display logos at."""
    from PIL import Image, ImageChops

    img = Image.open(path).convert("RGBA")
    alpha = img.split()[-1]
    if alpha.getextrema() != (255, 255):
        # Has real transparency — crop to non-transparent bbox
        bbox = alpha.getbbox()
    else:
        # Opaque image — crop to non-white content bbox
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        diff = ImageChops.difference(img, bg).convert("L")
        bbox = diff.getbbox()

    if bbox:
        left, top, right, bottom = bbox
        left = max(0, left - pad)
        top = max(0, top - pad)
        right = min(img.width, right + pad)
        bottom = min(img.height, bottom + pad)
        img = img.crop((left, top, right, bottom))

    if path.lower().endswith((".jpg", ".jpeg")):
        flat = Image.new("RGB", img.size, (255, 255, 255))
        flat.paste(img, mask=img.split()[-1])
        flat.save(path)
    else:
        img.save(path)


def download_and_convert(url: str, dest_path_no_ext: str):
    """Download the logo. SVGs get rasterized to PNG via a headless browser
    (Notion/img tags need a raster format); everything else saved as-is.
    Always trimmed to the actual mark — source files often carry large
    whitespace margins that make the logo invisible at small display sizes."""
    resp = requests.get(url, timeout=25, headers=WIKI_UA)
    resp.raise_for_status()
    if url.lower().endswith(".svg"):
        from playwright.sync_api import sync_playwright
        svg_path = dest_path_no_ext + ".svg"
        with open(svg_path, "wb") as f:
            f.write(resp.content)
        png_path = dest_path_no_ext + ".png"
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 400, "height": 400})
            page.goto(f"file://{svg_path}")
            page.wait_for_timeout(200)
            el = page.query_selector("svg")
            if el:
                el.screenshot(path=png_path, omit_background=True)
            else:
                page.screenshot(path=png_path, omit_background=True)
            browser.close()
        os.remove(svg_path)
        trim_whitespace(png_path)
        return png_path
    else:
        ct = resp.headers.get("content-type", "")
        ext = "png" if "png" in ct else "jpg" if "jpe" in ct else "webp" if "webp" in ct else "png"
        out_path = dest_path_no_ext + f".{ext}"
        with open(out_path, "wb") as f:
            f.write(resp.content)
        trim_whitespace(out_path)
        return out_path


def push_to_github(local_dir: str):
    """Sparse-clone, copy in the new logo files, commit, push."""
    def run(cmd, **kw):
        r = subprocess.run(cmd, capture_output=True, text=True, **kw)
        if r.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}\nSTDOUT: {r.stdout}\nSTDERR: {r.stderr}")
        return r

    tmp = tempfile.mkdtemp()  # NOT auto-deleted — keep clone around if push fails, for retry
    run(["git", "clone", "--filter=blob:none", "--no-checkout",
         f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git", tmp])
    run(["git", "-C", tmp, "sparse-checkout", "init", "--cone"])
    run(["git", "-C", tmp, "sparse-checkout", "set", "designer-logos"])
    run(["git", "-C", tmp, "checkout", "main"])

    dest = os.path.join(tmp, "designer-logos")
    os.makedirs(dest, exist_ok=True)
    run(["cp", "-R", f"{local_dir}/.", dest])

    status = run(["git", "-C", tmp, "status", "--short"]).stdout
    # Safety check — refuse to push if anything outside designer-logos/ is touched
    for line in status.splitlines():
        path = line.split()[-1]
        if not path.startswith("designer-logos/"):
            raise RuntimeError(f"Refusing to push — unexpected change outside designer-logos/: {line}")

    run(["git", "-C", tmp, "add", "designer-logos"])
    if not status.strip():
        print("Nothing new to push.")
        return
    run(["git", "-C", tmp, "commit", "-m", "add designer logos (auto backfill)"])
    run(["git", "-C", tmp, "push", "origin", "main"])
    subprocess.run(["rm", "-rf", tmp])  # only clean up on success


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    missing = get_missing_designers()
    if args.limit:
        missing = missing[: args.limit]
    print(f"Processing {len(missing)} designers missing a logo…")

    # NOT auto-deleted — if anything downstream fails, the downloaded logos
    # survive on disk for a retry instead of vanishing with the crash.
    staging = tempfile.mkdtemp()
    print(f"staging dir: {staging}")
    found = []  # (name, page_id, slug, ext)
    not_found = []

    for name, page_id in missing:
        try:
            url = search_wikimedia_logo(name)
            if not url:
                not_found.append(name)
                print(f"NOT FOUND: {name}")
                continue
            slug = slugify(name)
            slug_dir = os.path.join(staging, slug)
            os.makedirs(slug_dir, exist_ok=True)
            local_path = download_and_convert(url, os.path.join(slug_dir, "logo"))
            ext = local_path.rsplit(".", 1)[-1]
            found.append((name, page_id, slug, ext))
            print(f"found: {name} -> {slug}/logo.{ext}")
        except Exception as e:
            not_found.append(name)
            print(f"ERROR {name}: {e}")

    print(f"\nFound: {len(found)}  |  Not found: {len(not_found)}")

    if args.dry_run:
        print("Dry run — not pushing or updating Notion.")
        return

    if found:
        push_to_github(staging)
        print("Pushed to GitHub OK.")

    updated, update_failed = 0, []
    for name, page_id, slug, ext in found:
        raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/designer-logos/{slug}/logo.{ext}"
        try:
            resp = requests.patch(
                f"https://api.notion.com/v1/pages/{page_id}",
                headers=NH,
                json={
                    "icon": {"type": "external", "external": {"url": raw_url}},
                    "properties": {"Logo URL": {"rich_text": [{"text": {"content": raw_url}}]}},
                },
                timeout=15,
            )
            if resp.status_code == 200:
                updated += 1
                print(f"updated Notion: {name}")
            else:
                update_failed.append(name)
                print(f"NOTION UPDATE FAILED ({resp.status_code}): {name}")
        except Exception as e:
            update_failed.append(name)
            print(f"NOTION UPDATE ERROR: {name}: {e}")

    print(f"\nNotion updated: {updated}  |  Notion update failed: {len(update_failed)}")

    if not_found:
        print("\nNo logo found for (needs manual sourcing):")
        for n in not_found:
            print(f"  - {n}")

    subprocess.run(["rm", "-rf", staging])


if __name__ == "__main__":
    main()
