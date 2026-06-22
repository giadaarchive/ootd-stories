# Post-Mortem: Bot stuck at "Identifying items..." — 2026-06-22

## Symptoms
Bot showed "🔍 Identifying items..." message but never progressed. User sent multiple photos with no further response.

## Root Cause
Three bot instances were running simultaneously (PIDs 35741, 41415, 41469). Each restart attempt added a new process without killing the old ones cleanly.

Telegram delivers each update to exactly one connection. With 3 competing polling connections:
- Instance A downloads the photo and stores the session in its memory
- Instance B or C might receive the callback button tap
- Instance B/C has no session for that user → silently fails or shows "Session expired"
- Instance A is waiting for a callback it will never receive

The AI (`run_matching`) was likely completing fine, but the follow-up message edits and callback handling were split across instances, so nothing reached the user.

## Timeline
- 2026-06-18 — First bot started (PID 35741)
- 2026-06-22 17:41 — Second bot started (PID 41415) without killing the first
- 2026-06-22 17:43 — Third bot started (PID 41469) without killing either
- 2026-06-22 — User reports stuck at identifying items

## Fix Applied
1. Killed all three instances
2. Started one clean instance
3. Added PID lock file (`outfit_bot.pid`) — second start now exits immediately with a clear error if another instance is already running
4. Stale PID files (from crashes) handled gracefully via `os.kill(pid, 0)` check

## Prevention
`pkill -f outfit_bot.py` before any manual restart. The PID lock will also catch accidental double-starts going forward.
