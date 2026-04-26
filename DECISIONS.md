# OOTD Lookbook Generator — Decisions Log

## April 2026

### Image handling: dimension-based resize
Changed from byte-size cap to dimension-based resize using PIL `thumbnail()`.

- **Before**: loop compressing JPEG quality until file size < 4MB — fragile, broke on large images
- **After**: `MAX_DIMENSION = 1200` — resize longest side to 1200px before encoding
- **Why dimension not bytes**: Claude tokens are billed by 512px tile grid, not file size. 1200px ≈ 6 tiles vs 32 tiles for 4K. ~5× cheaper per image with no quality loss for fashion editorial use.

### OOTD story prompt — "Somewhere Between" variant
8.5% probability of using a prompt variant that opens with the exact words "Somewhere between".

- The base prompt produces consistent editorial voice
- The variant adds organic variation without disrupting the overall tone
- 8.5% is intentional: frequent enough to appear naturally, rare enough to feel distinctive
- Implemented via `get_prompt()` using `random.random() < 0.085`

### Story generation — skip logic
The script only generates stories for entries where the `OOTD Story` rich_text property is empty.
This is intentional — stories are permanent editorial decisions. The script runs idempotently.

### Rate limit handling
5 retries with exponential backoff (60s, 120s, 180s, 240s, 300s) on Claude API rate limit errors.

---

## Notion Database

| Database | ID |
|---|---|
| L's Lookbook Style | `235ccd15-cda1-8097-be05-ec7a19f9f39a` |

Environment: `.env` at `/Users/lisa/lookbook-stories/.env`
Required vars: `NOTION_TOKEN`, `NOTION_DATABASE_ID`, `ANTHROPIC_API_KEY`
