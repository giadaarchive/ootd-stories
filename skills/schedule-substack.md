# Skill: Schedule OOTD Post to Substack

Pick up OOTD entries marked `Post to Substack`, schedule them to publish at 9am SGT on weekdays, upload images to GitHub, and update the Notion status to `Posted`.

**Script:** `substack.py`
**Related reference:** [`OOTD_SKILLS.md`](../OOTD_SKILLS.md)
**See also:** [`ootd-stories.md`](./ootd-stories.md)

---

## When to use

- After generating OOTD stories with `lookbook.py`
- When you want to publish outfit content to the Substack newsletter
- Run manually or on a schedule (cron job)

---

## Prerequisites

- OOTD entry has an `OOTD Story` written (non-empty)
- OOTD entry has images in the page body
- `Substack` status property is set to `Post to Substack`
- `.env` has `SUBSTACK_EMAIL`, `SUBSTACK_PASSWORD`, `GITHUB_TOKEN`, `GITHUB_REPO`

---

## Process

### Step 1 — Mark entries for publishing

In Notion (OOTD database), set the `Substack` status of the entries you want to publish to **`Post to Substack`**.

Only entries with a completed `OOTD Story` and at least one image will publish successfully.

### Step 2 — Run the script

```bash
python3 substack.py
```

For each entry marked `Post to Substack`, the script:
1. Reads the `OOTD Story` text from Notion
2. Reads images from the page body
3. Uploads images to `giadaarchive/ootd-stories` GitHub repo (for permanent URLs)
4. Schedules the post to Substack via the Substack API
5. Updates the Notion `Substack` status to **`Posted`**
6. Saves the next scheduled slot to `.substack_schedule_state.json`

### Step 3 — Verify

Check Substack's draft/scheduled queue to confirm the post is scheduled. The Notion entry should show `Posted` status.

---

## Scheduling logic

Posts are scheduled to publish at **9:00 AM Singapore time (SGT, UTC+8)** on weekdays only (Monday–Friday).

The script tracks the last scheduled slot in `.substack_schedule_state.json` and advances to the next available weekday slot. Running the script multiple times schedules entries in sequence — each one takes the next available weekday morning.

**Example sequence:**
- Entry 1 → Monday 9am
- Entry 2 → Tuesday 9am
- Entry 3 → Wednesday 9am

If you run on a Wednesday, the first entry schedules for Thursday 9am (the next weekday morning not yet taken).

---

## Bulk status fix

If entries have been scheduled to Substack but the Notion status was not updated (bug or script interruption), fix them manually via the API:

```python
import os, requests
from dotenv import load_dotenv
load_dotenv()

H = {"Authorization": f"Bearer {os.environ['NOTION_TOKEN']}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
PAGE_IDS = ["PASTE_PAGE_IDS_HERE"]

for pid in PAGE_IDS:
    requests.patch(f"https://api.notion.com/v1/pages/{pid}", headers=H,
        json={"properties": {"Substack": {"status": {"name": "Posted"}}}})
    print(f"Updated {pid}")
```

---

## Image hosting

Substack requires externally hosted images. The script uploads outfit images to GitHub (`giadaarchive/ootd-stories`, `images/` folder) and uses the raw.githubusercontent.com URLs in the post body.

---

## Outputs

- Post scheduled on Substack at 9am SGT on the next available weekday
- `Substack` property on the Notion entry updated to `Posted`
- Images permanently hosted on GitHub

---

## Common errors

| Error | Cause | Fix |
|-------|-------|-----|
| Entry skipped — no story | `OOTD Story` field empty | Run `lookbook.py` first to generate the story |
| Entry skipped — no images | Images are inside synced blocks (not top-level) | Move images to top-level blocks in Notion, then re-run |
| Status not updated to Posted | Script crashed after scheduling but before PATCH | Use the bulk status fix snippet above |
| Substack auth failure | Password changed or session expired | Update `SUBSTACK_EMAIL`/`SUBSTACK_PASSWORD` in `.env` |
