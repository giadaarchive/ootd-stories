# What's Missing — Workflow Documentation Gap Analysis

A review of the full workflow system (collection, shop, brand presence) against what is documented. Covers all three repos: `ootd-stories`, `shop`, `behindthecultured`.

---

## What exists

- `skills/` folder in all three repos — one file per task
- `MISTAKES.md` in all three repos — errors and fixes
- `SETUP.md` in `ootd-stories` — first-time environment setup
- Reference docs (`COLLECTION_SKILLS.md`, `OOTD_SKILLS.md`, etc.) — database property reference
- Python scripts for every collection task

---

## Gaps identified

### 1. Designer ID reference

**What's missing:** There is no single file listing all designer IDs (Notion relation IDs) used in scripts.

**Why it matters:** Every `add-collection-item` inline script requires the correct `designer_id`. Currently you have to look it up from a previous script or query Notion.

**What to add:** A `DESIGNER_IDS.md` (or add a table to `COLLECTION_SKILLS.md`) mapping brand names → Notion relation IDs and → SKU codes.

Currently known IDs:
- Christian Dior: `33c5aada-5e92-44d7-9dcb-747e770a8acc`
- Louis Vuitton: (retrieve and add)
- Bertoni: (retrieve and add)

---

### 2. New drop workflow — end-to-end checklist

**What's missing:** A single-page checklist for "I just bought something, what are all the steps in order?"

**Why it matters:** Each skill is documented individually but there is no document that stitches them together in the correct sequence. Steps that get skipped most often are: re-hosting images (skipped because it feels optional) and running heritage after the fact.

**What to add:** A `NEW-DROP-CHECKLIST.md`:
1. Scrape and add to collection DB (`add-collection-item`)
2. Re-host images immediately (`rehost-images`) — do not skip
3. Run `heritage.py` for the new item
4. Run `heritage_audit.py` to verify
5. Generate SKU (`generate_skus.py`)
6. Tag "Why I own it" (`batch_tag_why_i_own_it.py`)
7. Verify shop page at `giada-shop.vercel.app/shop/<id>`
8. Queue OOTD stories (`lookbook.py`) when outfit photos are ready
9. Schedule to Substack (`substack.py`)

---

### 3. Authentication log / API key rotation

**What's missing:** A record of which API keys are in use, where they are configured (`.env`, Vercel env vars, GitHub secrets), and when they were last rotated.

**Why it matters:** When a key expires or is revoked (e.g. Notion token), there are multiple places it needs to be updated. Without a map of where each key lives, one location gets missed (the Vercel deployment was broken exactly this way).

**What to add:** An `AUTH.md` (private, not committed to GitHub) or a table in `SETUP.md`:

| Key | Where configured | Last updated |
|-----|-----------------|-------------|
| `NOTION_TOKEN` | `.env`, Vercel env | — |
| `ANTHROPIC_API_KEY` | `.env` | — |
| `GITHUB_TOKEN` | `.env` | — |

---

### 4. Image standards

**What's missing:** Documented standards for collection images — resolution, naming, folder structure on GitHub.

**Why it matters:** Inconsistent folder naming means images are hard to find and may conflict on upload. The current pattern `collection-images/<item-slug>/01.jpg` has not been formally documented.

**What to add:** A section in `rehost-images.md` (or `add-collection-item.md`) specifying:
- Folder: `collection-images/<brand-slug>-<item-slug>/`
- Naming: `01.jpg`, `02.jpg` ... `10.jpg` (zero-padded)
- Maximum: 10 images per item
- Format: JPEG (convert PNG if needed)
- GitHub repo: `giadaarchive/ootd-stories` → `raw.githubusercontent.com/giadaarchive/ootd-stories/main/`

---

### 5. Notion schema reference — property names and types

**What's missing:** A quick-reference table of all Notion property names, types, and IDs for the collection database — as used by the API (not as shown in the Notion UI).

**Why it matters:** API property names are case-sensitive and sometimes differ from display names. Every new script has to rediscover whether "Colour" is `rich_text` or `select`.

**What to add:** A `NOTION_SCHEMA.md` with a table like:

| Property (display) | API key | Type | Notes |
|-------------------|---------|------|-------|
| Title | `Second best` | `title` | Legacy name — don't rename |
| SKU | `SKU` | `rich_text` | — |
| Designer | `Designer` | `relation` | → Designer DB |
| Category | `Category` | `relation` | → Category DB |
| Material | `Material` | `rich_text` | Fallback: relation |
| Colour | `Colour` | `rich_text` | Fallback: relation |
| Why I own it | `Why I own it` | `multi_select` | Uses `tag_id_map.json` |

---

### 6. Backup procedure

**What's missing:** No documented process for backing up Notion data or the GitHub image store.

**Why it matters:** All collection data lives in Notion (no local DB). If the Notion workspace is accidentally deleted, or the GitHub repo is force-reset, images and metadata are gone.

**What to add:** Even a simple note in `SETUP.md`:
- Notion: export to HTML/CSV monthly (Notion Settings → Export)
- GitHub images: the `giadaarchive/ootd-stories` repo is the backup — do not force-reset or clean `collection-images/`

---

### 7. Shop — `SETUP.md`

**What's missing:** The `giadaarchive-shop` repo has no setup guide.

**Why it matters:** If the shop needs to be set up on a new machine (or rebuilt), there is no guide for: Node version, env vars, first deployment, `npx vercel link`.

**Partially addressed (2026-04-30):** `CLAUDE.md` now covers deployment rules, git author email requirement, image domains, and ISR config. Formal `SETUP.md` (first-time install steps) still missing.

**What to add:** `SETUP.md` in `giadaarchive-shop`:
- Node.js version (check `package.json` engines field)
- `npm install`
- Set env vars: `NOTION_TOKEN`, `NOTION_COLLECTION_DB`, `NOTION_OOTD_DB`
- `npx vercel link` (link to `giadaarchives-projects / giadaarchive-shop`)
- `npx vercel --prod`
- **Critical:** set `git config user.email "giadaarchive@proton.me"` locally before first commit

---

### 8. Behindthecultured — comment archive

**What's missing:** No stored archive of past comments with their performance data.

**Why it matters:** The weekly review process (documented in `skills/weekly-review.md`) depends on having a log to review. Without a running log, every review starts from scratch.

**What to add:** A `docs/reddit/comment-log.md` (or a Notion database) with columns: date, subreddit, thread, comment text, angle, replies, upvotes, on-brand (y/n).

---

### 9. Automation / cron opportunities

**What's missing:** No automated scanning or scheduling beyond manual script runs.

**Why it matters:** Several tasks have a natural cadence that could be automated:
- `heritage_audit.py` — could run weekly to catch items missing sections
- `generate_skus.py` — safe to run on a schedule; idempotent
- Reddit thread scanning — could surface opportunities automatically
- Substack scheduling state — currently a manual run; could be a cron job

**What to add:** An `AUTOMATION.md` noting which scripts are safe to automate, what trigger/cron schedule makes sense, and any risks (e.g. `heritage.py --force` is NOT safe to automate — it overwrites content).

---

### 10. Shop — analytics / what's performing

**What's missing:** No tracking of which shop pages get the most views or clicks.

**Why it matters:** Without data, there is no way to know which items attract attention, which editorial styles resonate, or whether the shop is driving any traffic back to Reddit/Substack.

**What to add:** Add Vercel Analytics (1 line in `layout.tsx`) and review monthly. Or add a simple UTM-tagged link from Substack posts to shop items.

---

## Delivered — 2026-04-30

- **AI outfit looks for shop items** — `generate_outfits.py` generates 3 styled images per item. Shop's "As Styled" section renders automatically when images exist on GitHub. See `skills/generate-outfits.md`.
- **Vercel git author fix** — shop repo now requires `giadaarchive@proton.me` as commit author. Documented in shop `CLAUDE.md`.
- **Cleaned up Vercel** — deleted `giada-shop` project (broken, superseded by `giadaarchive-shop`).
