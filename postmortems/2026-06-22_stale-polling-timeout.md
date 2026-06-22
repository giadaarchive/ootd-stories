# Post-Mortem: Bot unresponsive 2026-06-22

## Symptoms
Bot process alive (PID 35741, started Thu 2026-06-18) but not replying to photos sent on 2026-06-22. User sent multiple images with no response.

## Root Causes

### 1. Stale Telegram polling connection (primary)
The bot ran for 4 days without restart. python-telegram-bot's long-polling connection went stale — the process was alive but no longer receiving updates from Telegram's servers. This is a known issue with long-running PTB processes over unreliable connections.

**Fix:** Restart bot. Long-term: add a watchdog cron or systemd/launchd service to auto-restart on crash.

### 2. `TimedOut` on photo download (secondary)
Log showed `telegram.error.TimedOut` during `_download_photo` on a previous run. No retry logic existed — a single CDN timeout killed the in-flight session with no recovery.

**Fix:** Added `_download_with_retry()` — 3 attempts with 2s/4s/6s backoff before raising.

### 3. `NoneType: None` errors flooding stderr (noise)
PTB internal polling errors with `context.error = None` were being logged as full "Unhandled exception" entries, making real errors hard to spot.

**Fix:** Error handler now returns early when `context.error is None`.

## Timeline
- 2026-06-18 21:50 — Bot started, first successful OOTD logged
- 2026-06-22 — User sends photos, no reply
- 2026-06-22 — Process found alive, log shows stale polling + past TimedOut errors

## Changes Made
- `outfit_bot.py`: `_download_with_retry()`, updated error handler with null guard + post-mortem writer
- `postmortems/` directory created for future incident tracking
