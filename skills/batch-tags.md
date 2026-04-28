# Skill: Batch-Tag "Why I Own It"

Mass-infer and apply ownership tags to all collection items that are missing them.

**Script:** `batch_tag_why_i_own_it.py`
**Related reference:** [`COLLECTION_SKILLS.md`](../COLLECTION_SKILLS.md) → Why I Own It tags

---

## When to use

- After adding new items to the collection that don't have ownership tags yet
- Periodic maintenance to fill in missing tags across the whole database
- After importing a batch of items

---

## Process

### Dry run — see what would be applied, write nothing

```bash
python3 batch_tag_why_i_own_it.py
```

### Apply tags to Notion

```bash
python3 batch_tag_why_i_own_it.py --apply
```

### Apply to first N items only (useful for spot-checking)

```bash
python3 batch_tag_why_i_own_it.py --apply --limit 10
```

### Apply with a purchase context string

```bash
python3 batch_tag_why_i_own_it.py --apply --context "Bought for the monogram canvas and brand legacy"
```

The `--context` text is passed to Claude alongside the item's name, brand, price, and description. More specific context → better tag accuracy.

---

## Tag vocabulary (positive "Why I own it" only)

| Tag | When to apply |
|-----|--------------|
| `30-plus-wears` | Versatile daily-use piece with strong evidence of 30+ wears |
| `brand-discovery` | First piece from this brand — bought to explore |
| `brand-legacy` | Bought for heritage, history, or prestige of the house |
| `colour` | A specific, striking, or hard-to-find shade was the draw |
| `condition` | Exceptional pre-owned condition was a deciding factor |
| `craftsmanship` | Quality of construction — stitching, material, hardware |
| `gifted` | Received as a gift (SGD 0) |
| `investment-piece` | Classic or appreciating piece bought as a long-term hold |
| `love-the-designer` | Personal affinity for the specific designer or creative director |
| `natural-patina` | Leather/material's ageing quality was the draw |
| `pattern-integrity` | Print, pattern, or motif was the primary draw |
| `price` | Significant discount to retail — excellent value |
| `rare-find` | Hard to find, limited edition, or one-of-a-kind |
| `sentimental` | Emotional or heritage connection — family, memory, identity |
| `timeless-silhouette` | Classic, enduring cut or shape — not trend-dependent |
| `travel-worthy` | Compact, packable, suited for travel |
| `versatile` | Styles across multiple occasions and dress codes |
| `vintage-provenance` | Pre-owned/vintage piece valued for its history or era |

---

## Caveats

- Non-fashion items (whisky, tableware, etc.) are automatically skipped
- Items already tagged are skipped — safe to run repeatedly
- The script reads `tag_id_map.json` for Notion tag IDs — if a tag is missing, the file needs updating

---

## Common mistake

**Wrong tags applied.** Cause: `--context` was too vague (e.g. "good buy"). Fix: delete wrong tags from Notion, re-run with a more specific `--context` string, or set tags manually.

See [`MISTAKES.md`](../MISTAKES.md) for the full fix procedure.

---

## Outputs

- `Why I own it` multi-select property populated for all previously untagged items
