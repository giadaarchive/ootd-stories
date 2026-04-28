# Skill: Archive Item from YouTube Video

Extract the story, care instructions, and ownership tags from a recorded YouTube video about a wardrobe piece, and write them back to the Notion item page.

**Script:** `wardrobe_archive.py`
**Related reference:** [`COLLECTION_SKILLS.md`](../COLLECTION_SKILLS.md)

---

## When to use

After recording and publishing (or scheduling) a YouTube video about a specific item — talking through what it is, why you have it, and how to care for it.

---

## Prerequisites

- YouTube video is published or unlisted (must have a transcript available)
- Notion item page already exists
- `.env` has `NOTION_TOKEN`, `ANTHROPIC_API_KEY`
- `youtube-transcript-api` installed: `pip3 install youtube-transcript-api`
- `tag_id_map.json` present in the repo root

---

## Process

### Step 1 — Get the Notion page ID

From the Notion URL: `https://www.notion.so/lisajyt/TITLE-<PAGE_ID>`

The page ID is the 32-character hex string at the end.

### Step 2 — Get the YouTube URL

```
https://www.youtube.com/watch?v=VIDEO_ID
```

### Step 3 — Run the script

```bash
python3 wardrobe_archive.py <notion_page_url_or_id> <youtube_url>
```

Example:
```bash
python3 wardrobe_archive.py https://www.notion.so/lisajyt/Hermes-Destin-Loafer-322ccd15... https://www.youtube.com/watch?v=oynop22uTMA
```

### Step 4 — Review what was written

The script writes back to Notion:
- **The Story** — a 2-4 paragraph narrative in third person, written into the Owners and Stories table
- **Care properties** — Wash Method, Wash Temperature, Drying, Storage, Ironing, Season (only what was explicitly mentioned in the video)
- **Why I own it tags** — matched from the approved tag vocabulary
- **What I'd change tags** — matched from the approved tag vocabulary

Open the Notion page and verify the story is accurate. The script only uses what was said in the video — it does not invent details.

---

## Tag vocabulary

Tags are sourced from `tag_id_map.json` which maps slug → Notion page ID. The approved "Why I own it" and "What I'd change" slugs are defined in `DEINFLUENCE_SKILLS.md`.

If a video mentions a reason for ownership that doesn't match any existing tag, it is silently skipped. Add new tags to the Tags database in Notion and regenerate `tag_id_map.json` if needed.

---

## Outputs

- Story written to the Owners and Stories table on the Notion item page
- Care properties set on the Notion item
- Tags linked (relation) on the Notion item

---

## Common errors

| Error | Cause | Fix |
|-------|-------|-----|
| `TranscriptsDisabled` | Video has no auto-generated or manual transcript | Add manual captions to the YouTube video, then re-run |
| Story is thin / generic | Video transcript was very short or unclear | Script only writes what was said — longer, more detailed videos produce richer output |
| Tags not applied | `tag_id_map.json` missing or empty | Re-run `setup_codes.py` to regenerate the tag map |
