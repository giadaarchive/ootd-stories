# Skill: Write Heritage & Archive Notes

Generate and write the four-section heritage document for a collection item page in Notion.

**Script:** `heritage.py`
**Follow-up:** [`heritage-audit.md`](./heritage-audit.md)
**See also:** [`add-collection-item.md`](./add-collection-item.md)

Four sections: About This Piece → Design Language → Craft & Materials → Historical Context.
Full section guidance lives in `SYSTEM_PROMPT` inside `heritage.py`.

Do NOT include: retail prices, retailers, where to buy, resale value, market context,
authentication, ownership history, purchase details, or previous owners — in any section.

---

## Process

### Run for one specific item (most common)

```bash
cd /Users/lisa/lookbook-stories
python3 heritage.py --force <notion_page_id>
```

`--force` fetches the page directly from Notion, deletes any existing Heritage section, and rewrites it. Works for any brand — not limited to TARGET_DESIGNERS.

The page ID is the 32-character string in the Notion URL (with or without dashes — both work).

### Run for the N most recently added items

```bash
python3 heritage.py --recent 20
```

Processes the 20 most recently created items. Skips items that already have heritage content.

### Run in checkpoint mode (cron)

```bash
python3 heritage.py --limit 100
```

Writes up to 100 items in descending chronological order, resuming from `heritage_checkpoint.json`. Use for scheduled runs — never re-scans processed items.

### Run for all items by target designer

```bash
python3 heritage.py
```

Processes all items in `TARGET_DESIGNERS` (Hermès, Dior, Chanel, Ferragamo, Burberry, Louis Vuitton) missing heritage content.

---

## Before running — ensure the page has context

The script reads the page body above the Heritage section as context. The richer this content, the more piece-specific the output:

- Correct item title
- At least one image
- Designer relation linked
- Year made set if known
- Body text: material, condition, provenance, how it was acquired

---

## What the script writes

Four labelled sections under a `Heritage & House Notes` heading:

| Section heading | Content |
|---|---|
| About This Piece | Exact type, silhouette, colour, identifying details, condition |
| Design Language | Aesthetic choices, visual vocabulary, creative decisions |
| Craft & Materials | Materials, construction, hardware, finishing, production quality |
| Historical Context | Creative director era, fashion moment, how this fits the house's arc |

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

`--force <page_id>` works for any brand (fetches page directly). The TARGET_DESIGNERS dict is only used for creative director era context in the prompt.

---

## Common errors

| Error | Cause | Fix |
|---|---|---|
| Notes are generic, not piece-specific | Page body was empty at run time | Add description to page body, re-run with `--force` |
| JSON parse error | Claude returned malformed JSON | Re-run — usually a one-off API issue |
| Duplicate Heritage sections | `--force` run after partial content | Delete the duplicate heading in Notion, re-run |
