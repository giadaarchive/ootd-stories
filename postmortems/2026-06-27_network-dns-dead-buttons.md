# Post-Mortem: NetworkError — DNS failure → dead inline keyboard buttons — 2026-06-27

## Symptoms
- User sent 3 photos; bot appeared to process the first (AI matching ran to completion)
- Bot sent no reply — no item cards appeared
- Telegram showed previous messages with inline keyboard buttons that could not be clicked
- Bot process was alive (PID 58606) but unresponsive to new photos and callbacks

## Root Cause
DNS resolution failure (`[Errno 8] nodename nor servname provided, or not known`) when the
bot tried to send the first item-review card back to Telegram after AI matching completed.

The handler raised NetworkError inside an async task. PTB caught it in `error_handler`.
But because the `reply_text()` call failed, **no message with buttons was ever sent** — yet
the bot's in-memory session was left in a partially-initialised state (results stored,
first item never shown). When photos 2 and 3 arrived they were appended to this broken
session rather than starting fresh.

Separately: any *old* Telegram messages that already had inline keyboards were unclickable
because the bot's session state no longer matched what those buttons expected.

## Secondary Bug (fixed this session)
`error_handler` called `traceback.format_exc()` which captures the **current thread's**
exception state — always empty in async PTB handlers. Result: every post-mortem showed
`NoneType: None` as the stack trace instead of the real error.

## What Was Actually Happening
- AI matching: ✅ completed (5 match calls, tokens consumed)
- `_show_next_item` → `message.reply_text(...)` → NetworkError ❌
- Session left in limbo: `results` populated, `decisions` all None, no card ever sent
- Subsequent photos appended to the broken session
- PTB polling auto-recovered from DNS but the session never recovered

## Fixes Applied

### 1. Real traceback capture in `error_handler`
```python
# Before (broken):
tb = traceback.format_exc()   # always "NoneType: None" in async

# After:
tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
```

### 2. NetworkError added to known-cause library in `_write_postmortem`
Future NetworkError post-mortems will include the correct cause and fix instructions.

### 3. Bot restarted to clear broken session
User must resend the photo. PTB polling reconnects automatically after DNS recovers.

## Timeline
- ~16:11 SGT — User sends first photo
- ~16:11 SGT — AI matching completes (all 5 match calls)
- ~16:11 SGT — `reply_text()` raises NetworkError (DNS down)
- ~16:11 SGT — Photos 2 & 3 appended to broken session
- ~16:11 SGT — Post-mortem written (with empty traceback — secondary bug)
- 2026-06-27 ~17:xx SGT — Bot restarted; fixes committed

## Prevention
The DNS error itself is environmental (Mac sleep / VPN). Mitigation options:
- **Retry reply_text once** on NetworkError before giving up (prevents ghost sessions)
- **Session cleanup**: if `_show_next_item` fails, pop the session so next photo starts fresh
- Both are worth adding if this recurs more than once per week

## Pattern (see also)
- `2026-06-22_stale-polling-timeout.md` — polling went stale after 4 days
- `2026-06-22_multiple-instances-stuck-identifying.md` — 3 instances fighting over updates
