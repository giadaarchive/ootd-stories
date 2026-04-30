# Skill: Retitle Collection Items

Generate SEO-optimized, editorial product titles. Replaces Japanese resale boilerplate, raw listing copy, and broken titles with clean, searchable, editorial-quality names.

**Script:** `retitle.py`

---

## Title formula

```
[Brand] [Model Name] [Item Type] — [Material], [Colour], [Era/CD if notable]
```

| Element | Rule |
|---|---|
| Brand | First. Correct spelling with accents (Hermès, not Hermes). Never ALL CAPS. |
| Model name | Official name if known: Birkin 25, Tuileries Hobo, Cannes MM, Classic Flap, Iside Mini |
| Item type | Only if model name doesn't imply it |
| — | Em dash separator before details |
| Material | Specific: lambskin, canvas, corduroy, merino wool. Not "leather" alone if type is known. |
| Colour | One word. Most distinctive colour only. |
| Era/CD | Only if genuinely adds value: "Galliano Era", "1990s Archive", "Raf Simons" |
| Max length | 80 characters |

---

## Examples

| Before (raw resale title) | After (editorial SEO title) |
|---|---|
| `Wool Knit Turtleneck Top Christian Dior Black` | `Christian Dior Ribbed Turtleneck — Black Wool` |
| `VALEXTRA Valextra Mini Iside 2-Way Bag Hand/Shoulder Black Leather Made in Italy Nº 5053` | `Valextra Mini Iside — Black Leather` |
| `Hermes Cannes MM Tote Bag Handbag Canvas Red` | `Hermès Cannes MM Tote — Red Canvas` |
| `90s 00s Oscar de la Renta tailored jacket blazer corduroy navy outer jacket 100% wool vintage` | `Oscar de la Renta Blazer — Navy Corduroy, 1990s Archive` |
| `HERMES / Hermes Lambskin Piping Corduroy Trousers Vintage Archive Piece Navy Size M` | `Hermès Trousers — Navy Lambskin Piping, Vintage Archive` |
| `Louis Vuitton Tuileries Hobo bag from Monogram canvas with red leather accents — CA3138` | `Louis Vuitton Tuileries Hobo — Monogram Canvas, Red Leather` |
| `Hermes (` | `Hermès Bag` *(minimal fallback when no data)* |

---

## Usage

### Preview first (always)

```bash
cd /Users/lisa/lookbook-stories
python3 retitle.py --recent 20 --dry-run
```

### Write titles

```bash
# Most recently added items
python3 retitle.py --recent 20

# One specific page
python3 retitle.py --force <notion_page_id>

# Use a different model
python3 retitle.py --recent 20 --model deepseek
python3 retitle.py --recent 20 --model llama
```

---

## What gets stripped

- Japanese resale boilerplate: `2WAY`, `Hand/Shoulder`, `[Used]`, `Made in Italy`, serial numbers in title, `Nº XXXXXX`
- Condition language: `Excellent condition`, `Rank B`, `signs of use`
- Listing noise: `[Rare and high-end item]`, `Free Shipping`, personal notes like `(xav's)`
- Duplicate brand names: `VALEXTRA Valextra` → `Valextra`
- ALL CAPS: `HERMES` → `Hermès`
- Measurement specs in title: width/height/depth, weight in grams

---

## SEO rationale

Search intent for luxury archive fashion: **Brand + Model/Style + Material + Colour**.
Brand first because it carries the most search weight (31% better conversion than material-first).
Era/creative director adds long-tail value for archive collectors searching "Galliano Dior" or "Raf Simons era".
Max 80 chars keeps titles clean in search results without truncation.

---

## After running

No deployment needed — titles update in Notion immediately. Shop reflects the new titles within 30 minutes (ISR cache) or on next deployment.
