# Skill: Write Heritage & Archive Notes

Generate and write the full six-layer provenance document for a collection item page in Notion.

**Script:** `heritage.py`
**Follow-up:** [`heritage-audit.md`](./heritage-audit.md)
**See also:** [`add-collection-item.md`](./add-collection-item.md)

---

## The Six-Layer Framework

Every collection item page should contain all six layers. This is not generic heritage writing — it is a fingerprint of this specific object. Each layer must be about THIS piece, not the brand in general.

---

### Layer 1 — Object Identity

The piece itself, unambiguously identified.

- Maker, line/model name, colorway, size
- Materials — specific: fabric composition, leather type, hardware finish, lining material, date code (location and what it reads)
- Production era: year or year range, country of manufacture
- Distinguishing physical details that survive over time: stitching count per cm on main seams, hardware weight and finish, interior stamp placement, label typography and placement

**What fails here:** describing the category instead of the object. If the date code is unread, say so. If the hardware is unverified, say so. Do not describe what LV's materials are in general — describe what this specific bag has.

**Banned phrase:** never write "quiet luxury" or any variation of it. Describe what the piece actually is.

---

### Layer 2 — Maker Context

Why this piece matters relative to others from the same house.

- Who was creative director at time of production
- How this specific garment/object type fits into the house's design history
- What made this era's production different from earlier or later output
- What changed after — why this version is different from what's sold today

---

### Layer 3 — Authentication

Proof the object is what it claims to be. Model-specific, not brand-generic.

- How to authenticate THIS SPECIFIC MODEL: date code format and location, hardware tells, stitching count, material characteristics for this piece type
- Known fakes for this model — what they get wrong (zipper pull weight, stamp placement, hardware magnet test, fabric hand, embossing depth)
- Condition assessment: honest grading — what is worn, pristine, or needs attention
- Authentication gaps: what can only be confirmed by physical inspection or trade documentation

**What fails here:** authenticating Louis Vuitton in general instead of Monogram Vernis Brea GM specifically. Vernis has its own tells. Every model has its own fakes. Write for the model.

---

### Layer 4 — Ownership History

Where the piece has been. Often incomplete — honest incompleteness is correct.

- Original retail context: which store type, approximate year of sale, original retail price range if known
- Subsequent ownership: what is known or can be inferred (estate, collector, first-generation owner, number of previous owners)
- Geographic and climate history if determinable from condition
- Care and storage history based on current condition evidence

This layer is the hardest to reconstruct. Partial information is still information. "One previous owner versus five is meaningful."

---

### Layer 5 — Market Context

Where this piece sits in the broader secondary market. Specific, not vague.

- Current resale price range for THIS model and colorway specifically (not the brand or line in general)
- Price trajectory: appreciating, stable, or declining — and why
- Rarity: how frequently this model and colorway surfaces on the secondary market
- Comparable pieces: what else exists at this price and quality level, and why this is or is not the better choice

**What fails here:** "Vernis bags hold value well." Instead: "Magenta Vernis Brea GM in this condition currently trades at £X–£Y on Vestiaire; colourway was produced 2012–2014 only and surfaces roughly 3–5 times per quarter."

---

### Layer 6 — Wearability Assessment

How this piece actually functions for a real woman. **This is the layer that differentiates Giada Archive from every authentication service and resale platform that exists.** Anyone can verify a date code. Nobody tells her how the bag feels on her arm or which three outfits it resolves.

- Who it suits: body proportion, lifestyle, wardrobe profile
- How it wears: weight empty and loaded, drape or structure, strap options, closure handling
- What it pairs with: 2–3 specific outfit contexts where this piece is the right answer
- What wardrobe it fights with: what it doesn't work alongside
- CPW potential: realistic estimate of how often a woman with the right wardrobe profile would reach for it

---

## Process

### Run for one specific item (most common)

```bash
cd /Users/lisa/lookbook-stories
python3 heritage.py --force <notion_page_id>
```

`--force` reads all existing page content, deletes any existing Heritage section, and rewrites it fresh across all six layers.

The page ID is the 32-character string in the Notion URL (with or without dashes — both work).

### Run for the N most recently added items

```bash
python3 heritage.py --recent 20
```

Processes the 20 most recently created items. Skips items that already have heritage content (use `--force` to rewrite those).

### Run for all items by target designer

```bash
python3 heritage.py
```

Processes all items in `TARGET_DESIGNERS` (Hermès, Dior, Chanel, Ferragamo, Burberry, Louis Vuitton) that are missing heritage content.

---

## Before running — ensure the page has context

The script reads the page body above the Heritage section as context for the prompt. The richer this content, the more piece-specific the output:

- Correct item title
- At least one image
- Designer relation linked
- Year made set if known
- Body text: any details about material, condition, provenance, how it was acquired

---

## What the script writes

Six labelled sections appended under a `Heritage & House Notes` heading:

| Section | Layer |
|---|---|
| Object Identity | 1 |
| Maker Context | 2 |
| Authentication | 3 |
| Ownership History | 4 |
| Market Context | 5 |
| Wearability | 6 |
| Research Notes (toggle) | — |

---

## TARGET_DESIGNERS in heritage.py

```python
TARGET_DESIGNERS = {
    "Hermès":               "2b9ccd15-cda1-80fe-9888-dabde81bb8b1",
    "Christian Dior":       "33c5aada-5e92-44d7-9dcb-747e770a8acc",
    "Chanel":               "10fccd15-cda1-8031-9e26-c0c3b6bb99d3",
    "Salvatore Ferragamo":  "2b9ccd15-cda1-80f6-a3ed-edb298b97a02",
    "Burberry":             "10fccd15-cda1-808f-b12a-d13411d7b58d",
    "Louis Vuitton":        "10fccd15-cda1-80b7-bd9f-d0abc8bfd469",
}
```

Items from brands outside this dict are processed with generic era context (no creative director timeline).

---

## Common errors

| Error | Cause | Fix |
|---|---|---|
| Notes are house-generic, not piece-specific | Page body was empty at run time | Add description to page body, then re-run with `--force` |
| Layer 3 doesn't address this model's fakes | Prompt didn't have enough piece context | Ensure item title and category are specific in Notion |
| JSON parse error | Claude returned malformed JSON | Re-run — usually a one-off API issue |
| Duplicate Heritage sections | `--force` run after partial content | Manually delete the duplicate heading in Notion, then re-run |
