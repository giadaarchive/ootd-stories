# Skill: Re-host Expired Images

Download images from a Notion page (sourced from auction sites) and permanently re-host them on GitHub so they never expire.

**Script:** write inline per-page (see pattern below)
**GitHub repo for images:** `giadaarchive/ootd-stories`
**Image folder convention:** `collection-images/<item-slug>/`
**See also:** [`add-collection-item.md`](./add-collection-item.md)

---

## When to use

- Images on a Notion page stop loading (broken image icon)
- Immediately after adding a Yahoo Japan or Mercari item — these images expire within hours to days
- Before running `heritage.py` — the script reads images; broken URLs produce empty context

---

## Why images expire

Yahoo Japan (`auctions.c.yimg.jp`) and Mercari (`static.mercdn.net`) serve images with hotlink protection and session-based tokens. URLs that work at scrape time stop working for external referrers within hours. GitHub raw URLs (`raw.githubusercontent.com`) are permanent public CDN links.

---

## Process

### Step 1 — Write the re-host script

Use this template. Change `PAGE_ID` and `IMG_FOLDER` for each item.

```python
#!/usr/bin/env python3
import os, base64, time, requests
from dotenv import load_dotenv
load_dotenv()

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPO  = os.environ["GITHUB_REPO"]   # giadaarchive/ootd-stories
PAGE_ID      = "PASTE_NOTION_PAGE_ID_HERE"
IMG_FOLDER   = "collection-images/ITEM-SLUG-HERE"

NH = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
GH = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}

def get_image_blocks():
    blocks = requests.get(f"https://api.notion.com/v1/blocks/{PAGE_ID}/children", headers=NH).json()
    return [(b["id"], b["image"].get("external", {}).get("url") or b["image"].get("file", {}).get("url"))
            for b in blocks.get("results", []) if b.get("type") == "image"]

def download(url):
    r = requests.get(url, headers={"Referer": "https://auctions.yahoo.co.jp/"}, timeout=30)
    r.raise_for_status()
    ext = "jpg"
    return r.content, ext

def upload_github(data, filename):
    path = f"{IMG_FOLDER}/{filename}"
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    existing = requests.get(api_url, headers=GH)
    sha = existing.json().get("sha") if existing.ok else None
    payload = {"message": f"add {path}", "content": base64.b64encode(data).decode()}
    if sha: payload["sha"] = sha
    r = requests.put(api_url, headers=GH, json=payload)
    r.raise_for_status()
    return f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{path}"

image_blocks = get_image_blocks()
github_urls = []
for i, (block_id, url) in enumerate(image_blocks):
    data, ext = download(url)
    gh_url = upload_github(data, f"{i+1:02d}.{ext}")
    github_urls.append((block_id, gh_url))
    print(f"  [{i+1}] {gh_url}")
    time.sleep(0.5)

# Delete old blocks and re-add with GitHub URLs
all_blocks = requests.get(f"https://api.notion.com/v1/blocks/{PAGE_ID}/children", headers=NH).json()["results"]
for b in all_blocks:
    requests.delete(f"https://api.notion.com/v1/blocks/{b['id']}", headers=NH)
    time.sleep(0.2)

# Re-build: images first, then other blocks
new_blocks = [{"object": "block", "type": "image", "image": {"type": "external", "external": {"url": u}}} for _, u in github_urls]
non_image = [b for b in all_blocks if b.get("type") != "image"]
for b in non_image:
    btype = b["type"]
    if btype in ("heading_3", "paragraph"):
        rt = b.get(btype, {}).get("rich_text", [])
        if rt: new_blocks.append({"object": "block", "type": btype, btype: {"rich_text": rt}})

requests.patch(f"https://api.notion.com/v1/blocks/{PAGE_ID}/children", headers=NH, json={"children": new_blocks})
requests.patch(f"https://api.notion.com/v1/pages/{PAGE_ID}", headers=NH,
    json={"icon": {"type": "external", "external": {"url": github_urls[0][1]}}})
print("Done.")
```

### Step 2 — Run it

```bash
python3 _rehost_ITEMNAME.py
# delete the file after it succeeds
```

### Step 3 — Verify

Open the Notion page. All images should load. The icon should update.

---

## IMG_FOLDER naming convention

```
collection-images/BRAND-ITEM-DESCRIPTOR
```

Examples:
- `collection-images/dior-wool-top`
- `collection-images/hermes-destin-loafer`
- `collection-images/lv-tuileries-hobo`

Keep slugs lowercase, hyphenated, no spaces.

---

## GitHub image repo structure

All collection item images live in `giadaarchive/ootd-stories` under `collection-images/`. This is separate from OOTD outfit photos (which live in the `images/` folder at the repo root).

---

## Outputs

- Images permanently hosted at `https://raw.githubusercontent.com/giadaarchive/ootd-stories/main/collection-images/...`
- Notion page updated: old blocks deleted, new blocks written with GitHub URLs
- Page icon updated to first image

---

## Common errors

| Error | Cause | Fix |
|-------|-------|-----|
| `403` downloading image | Hotlink protection | Add `Referer: https://auctions.yahoo.co.jp/` header |
| GitHub `422` on upload | File already exists without SHA | Fetch existing file SHA and include in PUT payload |
| Notion blocks not in right order | Images appended to end, not prepended | Delete all blocks first, then rebuild in correct order |
