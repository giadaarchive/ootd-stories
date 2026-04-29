# Skill: Write Brand Heritage (House Documentation)

Write the full house history for each brand in the Designer database — founding story, family background, historical events, design philosophy, craft signature, current status. This is brand-level documentation, separate from item-level heritage notes.

**Script:** `brand_heritage.py`
**Designer database:** `18accd15-cda1-80ae-b0ec-e6bd60e4c4ed`
**See also:** [`heritage-notes.md`](./heritage-notes.md) — item-level six-layer documentation

---

## What it writes

Seven sections appended to each brand's Notion designer page under a `Brand Heritage` heading:

| Section | Content |
|---|---|
| **Founding Story** | When, where, by whom, and why — specific context, not marketing copy |
| **Family & Founders** | Who the people were, their backgrounds outside fashion, generational transfers |
| **Historical Moments** | Wars, crises, ownership changes, pivotal commissions — what happened to this brand specifically |
| **Design Philosophy** | What this house stands for in observable craft/aesthetic terms |
| **Creative Direction** | Key directors in chronological order with dates and what each changed |
| **Craft Signature** | Specific techniques, materials, construction methods, patents |
| **Current Status** | Current ownership, direction, market position |

---

## Why this exists separately from item heritage

Item heritage (in `heritage.py`) writes about a specific bag, coat, or shoe. Brand heritage writes about the house that made it. A TecknoMonster suitcase page should link to a brand page that explains the family's aeronautics background — that context informs why the materials and construction are what they are. A Valextra bag page gains meaning when the brand page explains the Milanese atelier origins and the specific leather philosophy.

---

## Usage

### List all brands and their status

```bash
cd /Users/lisa/lookbook-stories
python3 brand_heritage.py --list
```

Shows every brand in the designer database and whether it already has brand heritage written.

### Write heritage for all brands missing it

```bash
python3 brand_heritage.py
```

Processes all brands that don't yet have a `Brand Heritage` section. Skips brands that already have one.

### Force-rewrite one specific brand

```bash
python3 brand_heritage.py --force "TecknoMonster"
python3 brand_heritage.py --force "Valextra"
python3 brand_heritage.py --force "Colombo"
```

Clears existing brand heritage and rewrites it fresh. Use when:
- The existing entry is thin or inaccurate
- New information has been added to the brand page
- The prompt has been updated and you want to regenerate

Brand name must match exactly as it appears in Notion (use `--list` to check).

---

## What makes a good brand heritage entry

The prompt is specifically designed to go beyond marketing copy. Key principles:

- **Industrial origins matter most.** TecknoMonster's aeronautics family background, Colombo's textile mill origins, a shoemaker's apprenticeship under a specific master — these are what differentiate serious archival documentation from what you'd find on a brand website.
- **Historical events mean specific events.** Not "WWII affected European luxury" but "Hermès pivoted to leather goods during the Occupation because silk imports were blocked."
- **Founding story means the founder, not just the brand.** Where were they born, what did they do before, who trained them, what was their first product and first client.
- **Current status should name the conglomerate.** LVMH, Kering, Richemont, Tapestry, independent, family-held — be specific.

---

## Banned phrases

- "quiet luxury" (or any variation)
- "heritage brand" as a filler descriptor
- Vague statements like "known for quality craftsmanship" — describe what specific quality, what specific craft

---

## Capacity estimate for cron use

Each brand takes ~20–30 seconds (one Claude API call + Notion reads/writes). A typical designer database with 30–50 brands would complete in 15–25 minutes. Brand heritage only needs to run once per brand (or when re-researching), so this is not a daily cron — run it manually or on a weekly schedule as new brands are added to the collection.

---

## Adding new brands

When a new brand is added to the collection (via `add-collection-item.md`):
1. The brand is already in the designer database (it must be, to link items to it)
2. Run `python3 brand_heritage.py --force "Brand Name"` to write its heritage entry
3. This can also be triggered by adding to the designer database manually in Notion and then running the script
