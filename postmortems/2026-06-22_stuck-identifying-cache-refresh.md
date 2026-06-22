# Post-Mortem: Stuck at "Identifying items..." — cache refresh blocking — 2026-06-22

## Symptoms
Bot showed "🔍 Identifying items..." indefinitely. Claude AI was never called. No error message sent to user.

## Root Cause
`collection_cache.load()` found the cache stale (70h old, TTL is 12h) and called `refresh()` synchronously before returning. `refresh()` calls `_resolve_designer_names()` which makes one Notion API call per unique designer ID (95 designers) with a 0.35s sleep between each.

**Estimated blocking time: 95 × (network + 0.35s) ≈ 60–120 seconds**

This ran inside `asyncio.get_event_loop().run_in_executor()` in `_run_ai_and_review`, blocking that executor thread entirely. Claude vision was never called. The user saw "🔍 Identifying items..." forever.

## What Was Actually Happening
The bot WAS doing work — just the wrong work first. It was resolving designer names from Notion instead of identifying the outfit. The AI step never started.

## Fix Applied

### 1. Stale-while-revalidate in `collection_cache.load()`
If cache exists but is stale, return the stale data immediately and kick off a background `threading.Thread` to refresh. The bot responds in <1ms using cached data; fresh data arrives 60–120s later for the next request.

### 2. Persist designer name cache (`designer_cache.json`)
Designer names change rarely. `_resolve_designer_names()` now loads a persisted `designer_cache.json` and only fetches IDs it hasn't seen before. On next refresh: 0 new designers to resolve → refresh completes in seconds not minutes.

### 3. Pre-seeded designer cache
95 designer names extracted from existing collection_cache.json so the fix takes effect immediately without waiting for a clean refresh.

## Timeline
- 2026-06-19 19:21 — Collection cache last written (70h before incident)
- 2026-06-22 — User sends photo, cache stale, full blocking refresh triggered
- 2026-06-22 — Bot appears frozen at "Identifying items..." for 1-2 minutes (or until timeout)

## Prevention
Stale-while-revalidate means this can never block a user again. Even a 1-week-old cache returns in <1ms; fresh data appears in background.
