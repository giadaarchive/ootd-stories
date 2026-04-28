# Skill: Generate OOTD Stories

Scan the OOTD database, find entries without a story, read their outfit photos, and generate an editorial fashion narrative written into the `OOTD Story` property.

**Script:** `lookbook.py`
**Related reference:** [`OOTD_SKILLS.md`](../OOTD_SKILLS.md)
**Next step:** [`schedule-substack.md`](./schedule-substack.md)

---

## When to use

- After adding new OOTD entries with outfit photos to Notion
- Run regularly — the script is safe to run at any time; it only processes entries missing a story

---

## Prerequisites

- OOTD entry exists in the Notion database (`235ccd15cda18097be05ec7a19f9f39a`)
- At least one image is added directly to the page body (not inside a synced block)
- `.env` has `NOTION_TOKEN`, `NOTION_DATABASE_ID`, `ANTHROPIC_API_KEY`

---

## Process

### Step 1 — Add outfit photos to Notion

Upload photos directly to the OOTD page body. Drag images into the page. Do not place them inside synced blocks — the script reads top-level blocks only.

Up to 3 images per entry are sent to Claude for story generation.

### Step 2 — Run the script

```bash
python3 lookbook.py
```

The script processes all entries without a story, sorted most-recently-added first. It writes the story to the `OOTD Story` rich_text property.

### Step 3 — Review stories

Read the generated stories. If one is weak or misses the feel of the outfit, delete the `OOTD Story` content in Notion and re-run — the script will regenerate it.

---

## Story style rules

The editorial voice must stay consistent. These rules are baked into `lookbook.py`'s prompt and must be maintained if the prompt is ever edited:

- **Scene-first, not clothes-first.** Describe the feeling, the world, the character — not the garment.
- **No em dashes.** Restructure sentences instead. Maximum one per piece, strongly preferred none.
- **No contradiction structures.** Never "She is not X. She is Y." Build meaning through what the outfit *is*.
- **No self-reference.** Do not start with "I". Begin in scene.
- **8.5% probability** of opening with "Somewhere between..." (hardcoded random trigger).
- **British English.**

---

## Image handling

The script resizes images to max 1200px (longest side) before sending to Claude. This reduces token cost while keeping enough detail for the visual read. Images are not permanently stored — they are base64-encoded in memory for the API call only.

---

## Outputs

- `OOTD Story` field populated in Notion for each processed entry
- Stories are 3–4 paragraphs, atmospheric, editorial

---

## Common errors

| Error | Cause | Fix |
|-------|-------|-----|
| Entry shows 0 images | Photos are inside synced blocks | Move images to top-level blocks in Notion |
| Story generated but feels generic | Images are low resolution or show clothing flat, not worn | Use photos of the outfit being worn, not flat-lays |
| Rate limit error | Too many API calls in quick succession | Script auto-retries with backoff up to 5 times; if persistent, wait and re-run |
| `OOTD Story` not writing | Notion rich_text exceeds 2000 char limit per chunk | Script chunks at 2000 chars; if error persists check Notion API response |
