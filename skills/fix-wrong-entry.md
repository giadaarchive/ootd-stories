# Skill: Fix a Wrong Notion Entry

Correct an entry where the scraped images or description don't match the actual item purchased.

**Script:** write inline per-item (see pattern below)
**See also:** [`add-collection-item.md`](./add-collection-item.md), [`rehost-images.md`](./rehost-images.md)

---

## When to use

- Scraped item has the wrong images (e.g. related listing was captured instead of the target item)
- Title/description doesn't match what was actually purchased
- Images are from a different colourway or size variant

---

## Prevention

Before closing the script after scraping, always verify:
1. The first image matches the item you purchased
2. The title/description references the correct colour, material, size

Yahoo Japan auction pages sometimes surface related listings in their HTML that get picked up by the image extractor. Check the first 2–3 image URLs visually before writing to Notion.

---

## Fix process

### Step 1 — Get the Notion page ID

From the Notion URL or the script output.

### Step 2 — Write a fix script

```python
#!/usr/bin/env python3
import os, re, base64, time, requests, anthropic
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
load_dotenv()

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPO  = os.environ["GITHUB_REPO"]
PAGE_ID      = "PASTE_PAGE_ID_HERE"        # The page to fix
AUCTION_URL  = "PASTE_CORRECT_URL_HERE"    # The correct listing
IMG_FOLDER   = "collection-images/ITEM-SLUG"

H  = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
GH = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}

# 1. Scrape correct images from auction
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(user_agent="Mozilla/5.0...", locale="ja-JP")
    page = ctx.new_page()
    page.goto(AUCTION_URL, wait_until="load", timeout=60000)
    page.wait_for_timeout(8000)
    html = page.content()
    import re as _re
    images = list(dict.fromkeys(_re.findall(
        r"https://auctions\.c\.yimg\.jp/images\.auctions\.yahoo\.co\.jp/image/[^\"'>\s]+", html
    )))
    print(f"Found {len(images)} images")
    browser.close()

# 2. Upload images to GitHub
def upload_github(data, filename):
    path = f"{IMG_FOLDER}/{filename}"
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    existing = requests.get(api_url, headers=GH)
    sha = existing.json().get("sha") if existing.ok else None
    payload = {"message": f"fix: add {path}", "content": base64.b64encode(data).decode()}
    if sha: payload["sha"] = sha
    r = requests.put(api_url, headers=GH, json=payload)
    r.raise_for_status()
    return f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{path}"

github_urls = []
for i, url in enumerate(images[:10]):
    r = requests.get(url, headers={"Referer": "https://auctions.yahoo.co.jp/"}, timeout=30)
    gh_url = upload_github(r.content, f"{i+1:02d}.jpg")
    github_urls.append(gh_url)
    print(f"  [{i+1}] {gh_url}")
    time.sleep(0.5)

# 3. Delete all existing blocks
blocks = requests.get(f"https://api.notion.com/v1/blocks/{PAGE_ID}/children", headers=H).json()["results"]
for b in blocks:
    requests.delete(f"https://api.notion.com/v1/blocks/{b['id']}", headers=H)
    time.sleep(0.2)

# 4. Write new blocks: images first
new_blocks = [
    {"object": "block", "type": "image", "image": {"type": "external", "external": {"url": u}}}
    for u in github_urls
]
requests.patch(f"https://api.notion.com/v1/blocks/{PAGE_ID}/children", headers=H, json={"children": new_blocks})

# 5. Update title and icon
NEW_TITLE = "CORRECT TITLE HERE"
requests.patch(f"https://api.notion.com/v1/pages/{PAGE_ID}", headers=H, json={
    "properties": {"Second best": {"title": [{"type": "text", "text": {"content": NEW_TITLE}}]}},
    "icon": {"type": "external", "external": {"url": github_urls[0]}},
})
print("Fixed.")
```

### Step 3 — Run and delete

```bash
python3 _fix_ITEMNAME.py
rm _fix_ITEMNAME.py
```

### Step 4 — Update remaining properties in Notion

Verify and correct manually: material, colour, dimensions, condition.

---

## Outputs

- Notion page updated with correct images (GitHub-hosted), title, and icon
- Old wrong content removed
