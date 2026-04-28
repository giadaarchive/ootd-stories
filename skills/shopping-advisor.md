# Skill: Shopping Advisor — Buy or Skip

Before purchasing, run a wardrobe-aware analysis: does this item fill a gap, or duplicate something you already own?

**Script:** `shopping_advisor.py`
**Related reference:** [`SHOPPING_SKILLS.md`](../SHOPPING_SKILLS.md)
**See also:** [`deinfluence-tracker.md`](./deinfluence-tracker.md)

---

## When to use

Before committing to a purchase — especially for:
- Items above SGD 200
- Items where you suspect a similar piece already exists in the wardrobe
- Comparing two options (e.g. two versions of the same bag)

---

## Supported sources

- `jp.mercari.com`
- `item.fril.jp`

For Yahoo Japan auctions, use the add-collection-item pattern instead.

---

## Process

### Single item — should I buy this?

```bash
python3 shopping_advisor.py <url>
```

Output: Buy / Skip / Maybe verdict with 5 specific outfit ideas using named wardrobe pieces.

### Compare two items — which one?

```bash
python3 shopping_advisor.py <url_a> <url_b>
```

Output: Side-by-side analysis with a final recommendation.

### Log the decision to a Notion page

```bash
python3 shopping_advisor.py <url> --notion <notion_page_id>
```

Writes the analysis to an existing Notion item page (the item must already exist in the collection DB).

### Add purchase context for ownership tags

```bash
python3 shopping_advisor.py <url> --notion <page_id> --context "Bought because it fills my vintage Dior gap"
```

The `--context` text is used to infer `Why I own it` tags, which are written to the Notion item.

---

## The 30-wear threshold

The advisor scores every item against a 30-wear cost-per-wear threshold. An item is a **Buy** only if there is a realistic path to 30+ wears. This is the primary filter.

---

## Outputs

When run without `--notion`:
- Printed analysis: colour, material, silhouette, 5 outfit ideas, versatility score, CPW estimate, duplicate check, verdict

When run with `--notion`:
- All of the above written to the Notion page body
- Images embedded on the page
- `Why I own it` tags applied if `--context` is provided
- Page icon set to first product image
