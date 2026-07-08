# Skill: Find and Set Designer House Logos

Backfill missing designer logos automatically — search Wikimedia Commons, rehost permanently, set as the Notion reference point.

**Script:** `find_designer_logos.py`
**GitHub repo for images:** `giadaarchive/ootd-stories`
**Image folder convention:** `designer-logos/<brand-slug>/logo.<ext>`
**Reads/writes:** `Designer` database (`079fa275-238c-4427-94b5-2c0b0f485bf9`), property `Logo URL` (rich_text)

---

## When to use

- A new designer is added to the Designer database with no logo
- Periodically, to catch up on any designers still missing one
- Safe to re-run any time — it only processes designers where `Logo URL` is empty

## Why this exists

The shop site (`giadaarchive-shop`) shows the house logo next to each item's designer name (the "Maison" field). It reads a `Logo URL` text property directly — no relation-following or image search happens at request time. This script is what populates that property.

Logos set directly in Notion as a page icon **expire** (Notion re-hosts uploaded images as temporary S3 links, dead within about an hour). Wikimedia-sourced files are pulled once and rehosted to `raw.githubusercontent.com`, which never expires — same pattern as [`rehost-images.md`](./rehost-images.md) for product photos.

---

## Process

```bash
cd ~/lookbook-stories
python3 find_designer_logos.py              # process everything missing
python3 find_designer_logos.py --limit 20   # process first 20 only
python3 find_designer_logos.py --dry-run    # search only, no writes — check hit rate first
```

What it does, per missing designer:
1. Search Wikimedia Commons (`commons.wikimedia.org` API) for `"<name> logo"`, restricted to the File namespace
2. Relevance-check the result — the file title must actually contain a real word from the brand name, not just "logo" (avoids wrong-brand matches on ambiguous names)
3. Download the image. SVGs get rasterized via headless Chromium (Notion/`<img>` need raster); everything gets auto-cropped tight to the actual mark (source files often ship with huge whitespace margins that make the logo invisible at the small size it's displayed at)
4. Rehost to `giadaarchive/ootd-stories`, path `designer-logos/<slug>/logo.<ext>`
5. Set the Notion page icon (type `external`, permanent URL) **and** the `Logo URL` property to that same URL

Not every brand has a Wikimedia Commons file — expect roughly 40–50% hit rate across obscure/small-atelier names, much higher (80%+) for recognized global houses. Misses are printed at the end under "No logo found" for manual sourcing.

---

## Manual sourcing (when Wikimedia has nothing)

For a designer the script couldn't find:
1. Find an official logo yourself (brand's own site, press kit, or a clean Wikipedia/press image)
2. Rehost it the same way `rehost-images.md` does — download, `PUT` to `designer-logos/<slug>/logo.<ext>` in `giadaarchive/ootd-stories`
3. Set the Notion page's `Logo URL` property directly to the resulting raw.githubusercontent.com URL

---

## Outputs

- Logos permanently hosted at `https://raw.githubusercontent.com/giadaarchive/ootd-stories/main/designer-logos/<slug>/logo.<ext>`
- Notion `Logo URL` property set per designer
- Notion page icon set to the same URL (visual reference inside Notion itself)
- Shop site picks it up automatically — no code changes needed, it reads `Logo URL` live via `resolveDesignerLogo()` in `giadaarchive-shop/src/lib/notion.ts`

---

## Common errors

| Error | Cause | Fix |
|-------|-------|-----|
| `git push` fails: "could not read Password" | `GITHUB_TOKEN` in `.env` is stale/revoked | Generate a fresh token at github.com/settings/tokens, update `.env` |
| Wrong/unrelated logo attached | Ambiguous brand name matched an unrelated Commons file | Add the designer to `SKIP_NAMES` in the script, or manually source (see above) |
| Logo looks tiny/invisible on the site | Source file has large whitespace padding, trim step ran on an image with no clean bbox | Re-run just that designer; if it recurs, manually crop before rehosting |
| Script crashes mid-run | Search/download/API hiccup | Safe to just re-run — `staging` dir isn't deleted until full success, and `get_missing_designers()` only ever processes designers still missing a logo, so nothing is redone unnecessarily |
