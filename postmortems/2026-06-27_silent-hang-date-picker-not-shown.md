# Post-Mortem: Silent hang — date picker never shown after NetworkError — 2026-06-27

## Symptoms
- User sends photo → bot appears to do nothing (no reply at all)
- Bot process alive, no error in log
- Previous session's log only showed `[photo] single from user 64247935` with nothing after

## Root Cause (confirmed by trace logging)

Every photo sent via Telegram has its EXIF stripped. The bot's flow is:

```
photo received → download → check EXIF → none → store in _pending → reply with date picker
```

The previous NetworkError (DNS drop) hit `update.message.reply_text(...)` — the very first
network call inside `_process_images`. The date picker was **never sent**. But `_pending`
already had the images stored. The handler died silently with no visible error, no message
to the user.

After bot restart: new photo → new date picker shown → user tapped date → AI ran fine.
The bot was "broken" only for that one photo. Resending fixed it.

## Why it looked worse than it was
- No logging inside `_process_images`, so the log ended at `[photo] single from user`
- `_pending` dict was populated but no message shown → appeared frozen
- Old expired buttons from previous crash sessions were still visible in chat → user tried
  tapping those (dead) before the new date picker appeared below them

## What the log now shows (working session)
```
[photo] single from user 64247935
[process] start user=64247935 n=1 hash=6f32fcd5
[process] exif_date=None
[process] no EXIF — showing date picker
[setdate] callback user=64247935 data='setdate:2026-06-24'
[ai] _run_ai_and_review start user=64247935 date=2026-06-24
  [cache] stale (30h old) — using cached data, refreshing in background
  Identify tokens: 1907 in / 241 out
  Match tokens: ... (5 match calls)
  [memory] saved 4 decisions to corrections DB
```

## Fixes Applied

### 1. Trace logging throughout `_process_images` and `_run_ai_and_review`
Every step now logs: `[process] exif_date=...`, `[process] no EXIF — showing date picker`,
`[ai] _run_ai_and_review start ...`, `[setdate] callback ...`
Silent hangs will now be immediately visible in the log.

### 2. `_safe_reply` used everywhere in `_process_images`
All `reply_text` calls in `_process_images` now retry once on NetworkError.

### 3. `_pending` cleared if date picker fails twice
If both `_safe_reply` attempts fail sending the date picker, `_pending` is cleared.
Next photo from user starts completely fresh instead of being appended to a ghost pending.

### 4. `handle_photo` wraps inner logic in try/except
Any uncaught exception in the photo handler now: logs with full stack trace AND sends
`⚠️ Error processing photo: ...` to the user so they know to resend.

## Pattern (see also)
- `2026-06-27_network-dns-dead-buttons.md` — same DNS failure, different failure point
- Root cause is always the same: Mac network drop (sleep/VPN) kills mid-handler calls
- Fix is always: retry once, clear state if both fail, log verbosely
