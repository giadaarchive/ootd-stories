# Skill: Add Item from Online Purchase

Add a newly purchased item to the `L's Collection of Amazing Pieces` Notion database, with images, description, and metadata extracted from the listing.

**Script:** none yet (write per-item inline script — see pattern below)
**Related reference:** [`COLLECTION_SKILLS.md`](../COLLECTION_SKILLS.md)
**See also:** [`rehost-images.md`](./rehost-images.md), [`fix-wrong-entry.md`](./fix-wrong-entry.md), [`heritage-notes.md`](./heritage-notes.md)

---

## When to use

Every time a new item is acquired. Run this before running `heritage.py` — the item needs to exist in Notion first.

---

## Inputs required

- Purchase URL (Yahoo Japan auction, Mercari, etc.)
- Designer name (to look up the Notion designer relation ID)
- Basic description: what material and colour it is

---

## Designer relation IDs

These are the Notion page IDs for each designer in the Designer database. Required when creating a page via the API.

| Designer | Notion ID |
|----------|-----------|
| Hermès | `2b9ccd15-cda1-80fe-9888-dabde81bb8b1` |
| Christian Dior | `33c5aada-5e92-44d7-9dcb-747e770a8acc` |
| Chanel | `10fccd15-cda1-8031-9e26-c0c3b6bb99d3` |
| Salvatore Ferragamo | `2b9ccd15-cda1-80f6-a3ed-edb298b97a02` |
| Burberry | `10fccd15-cda1-808f-b12a-d13411d7b58d` |
| Louis Vuitton | `10fccd15-cda1-80b7-bd9f-d0abc8bfd469` |

To find an unlisted designer: query the Designer database via the Notion API or look up the page ID from the Notion URL.

---

## Process

### Step 1 — Scrape the listing

For Yahoo Japan auctions, use this script pattern (copy, adjust `AUCTION_URL`, `DESIGNER_ID`, `IMG_FOLDER`):

```python
#!/usr/bin/env python3
import os, re, json, time, requests, anthropic
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
COLLECTION_DB = "ad079964969043ae9fa85a4f3ca1a9ee"
AUCTION_URL = "https://auctions.yahoo.co.jp/jp/auction/XXXXX"
DESIGNER_ID = "PASTE_DESIGNER_ID_HERE"

H = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}
```

See the full working example in `_add_dior_top.py` (run previously — deleted after use, recreate from this pattern).

### Step 2 — Verify images loaded

After running the script, open the Notion page and check that images display. Yahoo Japan images are hotlink-protected — they often stop loading within hours.

If images are not loading: run [`rehost-images.md`](./rehost-images.md) immediately.

### Step 3 — Set remaining properties in Notion

The script sets: title, Designer relation, Material, Colour Detail, Dimensions, images.

Fill these manually in Notion after the script runs:

- `Category` — select the correct category (Tops & Shirts, Bags, Shoes, etc.)
- `Condition` — Excellent / Very Good / Good
- `SGD` — what you paid
- `Year It's Made (first hand)` — manufacture year if known
- `Date I bought/own` — purchase date
- `Season` — which seasons it works for

### Step 4 — Generate SKU

Once properties are filled, run:

```bash
python3 generate_skus.py
```

This assigns a SKU to all items missing one.

### Step 5 — Write heritage notes

Run `heritage.py` on the new item's page ID to generate the design language, craft, and historical context sections:

```bash
python3 heritage.py --force <notion_page_id>
```

See [`heritage-notes.md`](./heritage-notes.md).

---

## Supported sources

| Platform | Scraping method |
|----------|----------------|
| Yahoo Japan auctions | Playwright + yimg image extraction |
| Mercari Japan | `shopping_advisor.py` scraper (`_scrape_mercari`) |
| Fril | `shopping_advisor.py` scraper (`_scrape_fril`) |
| Other | Manual entry — copy listing details into Notion directly |

---

## What goes on the page body

**Only images.** Nothing else before the Heritage section.

| Allowed | Banned |
|---|---|
| Images (rehosted on GitHub) | Raw listing/auction text as a paragraph |
| Heritage & House Notes (added by heritage.py) | "Description" heading + paragraph |
| | Condition grades: "excellent used condition", "美品", "Rank B" |
| | Auction context: "listed on Yahoo Japan", "auction has ended" |
| | Japanese resale boilerplate of any kind |

Do NOT paste the listing description into the page body. The listing text is used as context when generating heritage notes, but it must never be written as a block on the page.

## Outputs

- New page in `L's Collection of Amazing Pieces` (`ad079964969043ae9fa85a4f3ca1a9ee`)
- Page icon set to first image
- Images (rehosted to public GitHub) added above Heritage section
- Properties populated: material, colour, dimensions, Designer relation
- **No raw description text block**

---

## Common errors

| Error | Cause | Fix |
|-------|-------|-----|
| `400 Bad Request` from Notion | A property value is wrong type (e.g. dict instead of string for Dimensions) | Check Claude's JSON output — ensure Dimensions is a plain string |
| Images not loading | Yahoo/Mercari hotlink protection | Run rehost-images skill immediately |
| Wrong item scraped | OG image from related listing, not the actual item | Verify images match the item before closing the browser; see `fix-wrong-entry.md` |
