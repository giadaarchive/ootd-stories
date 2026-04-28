# Skill: Write Heritage & Garment Notes

Generate and write the Heritage & House Notes section for a collection item — About This Piece, Design Language, Craft & Materials, and Historical Context — directly into the Notion page.

**Script:** `heritage.py`
**Follow-up:** [`heritage-audit.md`](./heritage-audit.md)
**See also:** [`add-collection-item.md`](./add-collection-item.md)

---

## When to use

- After adding a new item to the collection
- When an item's heritage section is missing or was written with the old house-centric format
- When you want to update a piece's notes with `--force`

---

## What it writes

Four sections appended to the Notion page body under a `Heritage & House Notes` heading:

| Section | Content |
|---------|---------|
| **About This Piece** | This specific object — date code, materials, what makes it distinct within the model line |
| **Design Language** | The aesthetic vocabulary: silhouette, proportions, hardware, colour logic |
| **Craft & Materials** | Construction method, leather/fabric type, stitching, hardware, lining |
| **Historical Context** | The house's output at the time this piece was made, the creative director's era |

A collapsible **Research Notes** toggle is also added with claims to verify and gaps for future physical inspection.

---

## Process

### Step 1 — Ensure the item exists in Notion with a description

Before running `heritage.py`, the Notion page should have:
- Correct title
- At least one image (or a page body description of what the item is)
- Designer relation linked
- `Year It's Made` date set if known

The script reads the page body text above the Heritage heading as context. The richer this content, the more piece-specific the output.

### Step 2 — Run for a single item (most common)

```bash
python3 heritage.py --force <notion_page_id>
```

`<notion_page_id>` is the 32-character ID without dashes, or with dashes — both work.

The `--force` flag:
- Reads all existing page content (including body text) as context
- Deletes any existing Heritage section
- Rewrites it fresh

Without `--force`, the script skips pages that already have heritage content.

### Step 3 — Run for all items of a specific designer

To write heritage notes for every item by a designer that doesn't yet have them:

```bash
python3 heritage.py
```

This processes all items in `TARGET_DESIGNERS` (Hermès, Dior, Chanel, Ferragamo, Burberry, Louis Vuitton) that are missing heritage content.

### Step 4 — Review the output

Open the Notion page and check:
- Does "About This Piece" describe *this specific item*, not a generic one?
- Is the date code / production year referenced correctly?
- Are the design language notes about the actual piece, not just the brand?
- Is the historical context tied to the creative director who was active when this piece was made?

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

To add a new designer: add their name and Notion designer page ID to this dict.

---

## Outputs

- Heritage & House Notes section appended to the Notion page
- Sections: About This Piece, Design Language, Craft & Materials, Historical Context, Research Notes (toggle)

---

## Common errors

| Error | Cause | Fix |
|-------|-------|-----|
| Heritage section is house-centric, not piece-specific | Old prompt format, or page body was empty at run time | Add description to page body, then re-run with `--force` |
| `JSON parse error` | Claude returned malformed JSON | Re-run — usually a one-off API issue |
| Duplicate Heritage sections | `--force` run after a previous `--force` left partial content | See `MISTAKES.md` → "Duplicate Heritage sections" |
| Wrong creative director referenced | Date code parsed incorrectly | Manually verify date code, correct in Notion, re-run with `--force` |
