# Generate Outfit Looks — AI Styling Images for Shop Items

Generates three AI-styled outfit images for a collection item and hosts them on GitHub, making them available as the "As Styled" section on the shop item page.

**Script:** `generate_outfits.py`
**Output:** `outfits/<page_id>/look_1.png`, `look_2.png`, `look_3.png`
**Model:** `google/gemini-2.5-flash-image` via OpenRouter

---

## When to run

After an item is listed for sale on the shop and you want to show how it can be styled. The shop auto-detects whether outfit images exist for a given item — the "As Styled" section appears automatically once images are pushed to GitHub.

---

## How to run

```bash
cd ~/lookbook-stories

# Generate for one item (use the Notion page ID — no dashes needed)
python3 generate_outfits.py --page 350ccd15cda181489163c56c57742363

# Dry run — prints prompts without generating images
python3 generate_outfits.py --page <page_id> --dry-run

# Use a different image model
python3 generate_outfits.py --page <page_id> --model google/gemini-2.5-flash-image
```

The page ID comes from the Notion URL: `notion.so/.../350ccd15cda181...` — strip the dashes.

---

## What it generates

Three looks per item:

| Look | Label | Style |
|------|-------|-------|
| `look_1.png` | Off-Duty | Street-style, Paris, golden light, candid editorial |
| `look_2.png` | Gallery Opening | Refined, monochrome, gallery-white background |
| `look_3.png` | Business Casual | Polished, structured, office-corridor setting |

The prompt pulls item title, material, colour, and the first 200 characters of heritage notes from Notion. No brand logos or text overlays are generated.

---

## After generating — push to GitHub

Images must be committed to the `scripts` branch and pushed before the shop can serve them:

```bash
git add outfits/
git commit -m "feat: add outfit looks for <item name>"
git push origin scripts
```

Images are then available at:
```
https://raw.githubusercontent.com/giadaarchive/ootd-stories/scripts/outfits/<page_id>/look_1.png
```

The shop (`giadaarchive-shop.vercel.app`) does a HEAD check at build time — the "As Styled" section renders automatically once images exist. No shop code changes needed.

---

## Requirements

```
OPENROUTER_API_KEY=sk-or-...   # in .env
NOTION_TOKEN=secret_...        # already set
```

OpenRouter key must be active. The default model (`google/gemini-2.5-flash-image`) costs roughly $0.003–0.005 per image.

---

## Notes

- Images take 15–60s each to generate. The script sleeps 2s between calls.
- If an image fails, the script prints the error and continues. Rerun for individual failures.
- The `outfits/` folder on the `scripts` branch is image-only — do not confuse with the `main` branch (which holds `collection-images/`).
- Do NOT run on items not listed for sale — the "As Styled" section only shows on shop pages.
