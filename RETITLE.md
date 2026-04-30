# Retitle — SEO-Optimized Collection Titles

Generates editorial, SEO-optimized product titles for the Giada Archive collection. Replaces raw Japanese resale copy-paste with clean, searchable names.

**Script:** `retitle.py`  
**Skill guide:** `skills/retitle.md`

---

## Formula

```
[Brand] [Model Name] [Item Type] — [Material], [Colour], [Era if notable]
```

Max 80 characters. Brand first. Em dash before details. No resale boilerplate.

---

## Quick start

```bash
# Always preview first
python3 retitle.py --recent 20 --dry-run

# Write when satisfied
python3 retitle.py --recent 20

# One page
python3 retitle.py --force <notion_page_id>

# Switch model
python3 retitle.py --recent 20 --model deepseek
```

Model aliases: `sonnet` · `haiku` · `opus` · `deepseek` · `llama` · `qwen` · `mistral`

---

## What it strips

| Banned | Example |
|---|---|
| Japanese resale format | `2WAY`, `Hand/Shoulder`, `Nº 5053` |
| Listing noise | `[Rare and high-end item]`, `[Used]`, `Free Shipping` |
| Personal notes | `(xav's)`, `(elephant)` |
| Duplicate brand | `VALEXTRA Valextra` → `Valextra` |
| ALL CAPS brand | `HERMES` → `Hermès` |
| Condition grades | `Rank B`, `Excellent condition` |
| Measurements in title | W/H/D specs, weight in grams |

---

## SEO keywords that matter (in priority order)

1. Brand name (Hermès, Chanel, Dior)
2. Model/style name (Birkin, Tuileries, Cannes MM)
3. Era or creative director (Galliano, Raf Simons, 1990s)
4. Material (lambskin, canvas, corduroy)
5. Colour (singular, most distinctive)
6. "Archive" or "Vintage" for long-tail collector search

---

## Examples

| Before | After |
|---|---|
| `Wool Knit Turtleneck Top Christian Dior Black` | `Christian Dior Ribbed Turtleneck — Black Wool` |
| `VALEXTRA Valextra Mini Iside 2-Way Bag Hand/Shoulder Black Leather Made in Italy Nº 5053` | `Valextra Mini Iside — Black Leather` |
| `Hermes Cannes MM Tote Bag Handbag Canvas Red` | `Hermès Cannes MM Tote — Red Canvas` |
| `HERMES / Hermes Lambskin Piping Corduroy Trousers` | `Hermès Trousers — Navy Lambskin Piping, Vintage Archive` |
