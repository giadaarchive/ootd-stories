# Skill: Generate SKUs

Assign a unique SKU to every item in the collection that is missing one.

**Script:** `generate_skus.py`
**Related reference:** [`COLLECTION_SKILLS.md`](../COLLECTION_SKILLS.md) → SKU format

---

## When to use

- After adding new items to the collection
- Run any time — safe to run repeatedly; only assigns SKUs to items missing them

---

## SKU format

```
BRAND-CATEGORY-MATERIAL-YY-###
```

| Segment | Example | Source |
|---------|---------|--------|
| BRAND | `DIO` | 3-letter code from Designer database (`SKU Code` property) |
| CATEGORY | `TOP` | 3-letter code from Category database |
| MATERIAL | `WOL` | 3-letter code from Material Category database |
| YY | `26` | Last 2 digits of `Year It's Made` |
| ### | `001` | Sequential 3-digit counter per brand |

Full example: `DIO-TOP-WOL-26-001`

---

## Process

```bash
python3 generate_skus.py
```

The script:
1. Queries all items in `L's Collection of Amazing Pieces`
2. Finds items where `SKU` is empty
3. Resolves the brand code, category code, material code, and year
4. Assigns the next available sequential number for that brand
5. Writes the SKU back to the Notion `SKU` property

---

## Prerequisites

- Designer, Category, and Material Category databases must have `SKU Code` properties filled in
- `Year It's Made (first hand)` should be set on each item
- `tag_id_map.json` and `type_id_map.json` present in repo root

---

## Outputs

- `SKU` property populated for all previously empty items
