# SHOPPING ADVISOR SKILLS

A wardrobe-aware purchase advisor. Given product URLs from Japanese resale marketplaces, it scrapes listings, reads the full Notion wardrobe, and uses Claude to recommend whether to buy — and if comparing two items, which one to choose.

The core question it answers: **will I actually wear this 30 times?**

---

## Two modes

### Mode 1 — Compare two items, pick one

```bash
python shopping_advisor.py <url1> <url2>
```

Use when torn between two options while shopping. The script produces:
- Product details extracted from each listing (colour, material, silhouette, size)
- 5 outfit ideas per product, naming specific wardrobe pieces
- Versatility score (1–10) and estimated annual wears for each
- Gap analysis: what each fills vs. what it duplicates
- A single final recommendation with clear reasoning

### Mode 2 — Single item check: should I buy this?

```bash
python shopping_advisor.py <url>
```

Use when you've found one item and want a wardrobe assessment before committing.
Output is the same format but concludes with a Buy / Skip / Maybe verdict.

### Optional — Post results to a Notion page

```bash
python shopping_advisor.py <url1> <url2> --notion <notion_page_url_or_id>
```

Posts the full analysis to a Notion page. Images are inserted **before any existing table** on the page, then the analysis text follows.

---

## Supported sources

| Marketplace | URL pattern |
|-------------|-------------|
| Mercari Japan | `jp.mercari.com/item/...` |
| Fril / Rakuma | `item.fril.jp/...` |

More sources can be added by writing a new `_scrape_*` function in `shopping_advisor.py` and registering it in the `scrape()` dispatcher.

---

## What the analysis covers

For each product:

1. **Item profile** — colour, material, silhouette/cut, size extracted from the listing
2. **5 outfit ideas** — each names specific pieces from the actual wardrobe (not generic suggestions)
3. **Versatility score** — 1–10, weighted for Singapore climate (30°C, humid year-round)
4. **Annual wear estimate** — realistic number of times per year based on style and occasion range
5. **Gap vs. duplicate audit** — what already exists in the wardrobe that serves a similar function
6. **30-wear verdict** — explicit reasoning on whether the item will realistically reach the cost-per-wear threshold

---

## Decision framework

The 30-wear threshold is the minimum bar. Factors that raise or lower confidence:

**Raises confidence (toward Buy)**
- Fills a genuine colour or silhouette gap — nothing equivalent exists in the wardrobe
- Shoulder/crossbody carry → everyday use → more wears
- Neutral or complementary colour to dominant wardrobe colours
- Versatile across casual and semi-formal occasions
- Brand being explored for the first time (research value counts)

**Lowers confidence (toward Skip)**
- Duplicates an existing item in the same colour family and function
- Formal/occasion-specific → limited wear window
- Statement item in a colour already well-covered
- Style works only with a narrow subset of the wardrobe

**Override conditions (always Skip)**
- Exact functional duplicate already owned
- Item only works in cold weather (Singapore has no winter)

---

## How it connects to the rest of the system

`shopping_advisor.py` reads from the same Notion wardrobe database used by all other scripts (`ITEMS_DB = ad079964-9690-43ae-9fa8-5a4f3ca1a9ee`). It does not write to the wardrobe — it is read-only.

If the item is purchased and added to the wardrobe, the normal workflow applies:
1. Create a row in Wardrobe Items in Notion
2. Run `generate_skus.py` to assign a SKU
3. If there is a video: run `wardrobe_archive.py <notion_url> <youtube_url>`

If the item is considered but ultimately not purchased, it belongs in the Deinfluence Tracker:
```bash
python deinfluence_collector.py <url>
```

---

## Roadmap — future app

This script is the backend logic for a planned mobile-friendly app for use while shopping in person overseas (no laptop, phone only).

The interface layer will change; the core logic stays constant:
```
scrape(url) → load_wardrobe() → analyse() → [post_to_notion()]
```

Future features to add:
- [ ] Budget / price threshold input
- [ ] Season filter (already in wardrobe schema)
- [ ] Support for additional marketplaces (Yahoo Auctions Japan, Vestiaire, Vinted)
- [ ] Output as a formatted PDF or shareable link
- [ ] Conversational follow-up (ask follow-up questions about specific outfits)
- [ ] Comparison against the Deinfluence Tracker (have I considered and rejected this before?)

---

## Environment variables required

All secrets are stored locally in `.env` — never committed to GitHub.

| Variable | Used for |
|----------|----------|
| `NOTION_TOKEN` | Reading the wardrobe database |
| `ANTHROPIC_API_KEY` | Claude analysis (uses `claude-opus-4-7`) |

---

## Example commands

```bash
# Should I buy this Valextra burgundy hobo?
python shopping_advisor.py https://jp.mercari.com/item/m97567661633

# Green Valextra vs burgundy Valextra — which one?
python shopping_advisor.py https://jp.mercari.com/item/m90034940216 https://jp.mercari.com/item/m97567661633

# Compare and post the result to a Notion page
python shopping_advisor.py https://jp.mercari.com/item/m90034940216 https://jp.mercari.com/item/m97567661633 \
  --notion https://www.notion.so/lisajyt/some-page-id

# Single item check from Fril
python shopping_advisor.py https://item.fril.jp/d3ecac09e1f8552dfe9eafd02150ad00
```
