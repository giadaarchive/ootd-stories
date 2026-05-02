# CLAUDE.md — lookbook-stories (giadaarchive/ootd-stories)

## Git discipline

**Atomic commits.** Commit after every self-contained change — one fix, one feature,
one refactor. Never batch unrelated changes into one commit. Prefer 5 small commits
over 1 large one. Commit messages: imperative, lowercase, under 72 chars.

**Push reminder.** At the end of every session, tell the user how many unpushed commits
exist and remind them to run `git push origin main`. Do not leave work local.

A stop hook at `.claude/stop-hook.sh` auto-commits any uncommitted work when Claude
stops and prints the push reminder automatically.

## What this repo is
Scripts + docs for Lisa's personal fashion archive "Second Best". Notion-backed system. Not a product — a personal archive in maintenance mode (no new acquisitions).

## Key scripts
| Script | Purpose | Run as |
|---|---|---|
| `heritage.py` | Write 4-section heritage notes to Notion item pages | `python3 heritage.py --limit N` or `--force <page_id>` or `--model <alias>` |
| `heritage_audit.py` | Add Craft & Materials + Verification & Sources | `python3 heritage_audit.py --recent N` |
| `retitle.py` | Generate SEO-optimized editorial titles | `python3 retitle.py --recent N --dry-run` then without `--dry-run` |
| `lookbook.py` | Generate OOTD fashion stories from Notion | — |
| `generate_outfits.py` | Generate 3 AI outfit look images for a shop item | `python3 generate_outfits.py --page <notion_page_id>` |
| `llm.py` | Shared LLM client — routes Anthropic or OpenRouter | imported by other scripts |
| `house_codes/query_engine.py` | Andromeda: reactive runway query engine | `python3 house_codes/query_engine.py --stream "question"` |
| `house_codes/prewarm_aw2026.py` | Pre-warm AW2026 data for all major houses | `python3 house_codes/prewarm_aw2026.py --gender women` |

## Andromeda — fashion knowledge graph (`house_codes/`)

Reactive runway archive. Data is fetched on demand when a query requires it, cached in a JSON graph, never pre-built speculatively.

### Architecture
```
Query → interpret (Qwen) → pull from graph (local) → synthesize (Qwen) → answer
                                   ↓ if no data
                         fetch tag-walk → vision extract (Qwen-VL) → store codes → synthesize
```

### Key files
| File | Role |
|------|------|
| `query_engine.py` | Main entry point — interpret + ensure_coverage + pull + synthesize |
| `fetch_show.py` | Fetches tag-walk (session cookie) + YouTube (yt-dlp) |
| `vision_extract.py` | Batched vision extraction via Qwen2.5-VL-72B |
| `graph.py` | Read/write JSON knowledge graph (brands, seasons, instances) |
| `checker.py` | Taxonomy validator; `check_taxonomy_only()` for vision codes |
| `cache.py` | SHA256 disk cache — 7d URL, 14d LLM, 1d tag-walk, 30d answers |
| `models_config.json` | Model-to-task assignment (all OpenRouter, no Anthropic) |
| `data/` | `brands.json`, `seasons.json`, `instances.json` — the knowledge graph |

### Model allocation (all open-source via OpenRouter)
| Task | Model | Why |
|------|-------|-----|
| Question interpret | Qwen-2.5-72B | Structured JSON extraction, fast |
| Vision analysis | Qwen2.5-VL-72B | Runway image → colour/silhouette/fabric |
| Taxonomy checker | Llama-3.3-70B | Fast evidence validation |
| Cross-brand synthesis | Qwen-2.5-72B | Pattern reasoning, editorial answer |
| Answer cache | disk (30d TTL) | Zero tokens on repeat questions |

Anthropic (Claude) is NOT used in Andromeda pipelines. It is only present in heritage.py / lookbook.py for long-form creative writing where quality gap still justifies cost.

### Running Andromeda locally
```bash
# Query (streams status + answer)
python3 house_codes/query_engine.py --stream "What colours are trending for SS2026?"

# Pre-warm a full season
python3 house_codes/prewarm_aw2026.py --gender women

# Frontend (port 3131)
cd frontend && npm run dev
```

### Tag-walk session cookie
Set `TWFOSID_TAGWALK` in `.env` — get from Chrome DevTools → Application → Cookies → tag-walk.com → TWFOSID. Expires periodically; refresh when 401s appear.

## Title formula (retitle.py)
`[Brand] [Model Name] [Item Type] — [Material], [Colour], [Era if notable]`
- Brand first, correct accents (Hermès not Hermes), max 80 chars
- Strip: Japanese resale boilerplate, ALL CAPS, duplicate brand names, condition grades, personal notes
- See `RETITLE.md` and `skills/retitle.md` for full rules and examples

## Model aliases (llm.py)
`sonnet` · `haiku` · `opus` · `llama` · `deepseek` · `qwen` · `mistral` · `gemma`
Default: `claude-sonnet-4-6`

## Heritage script rules
- 4 sections only: About This Piece · Design Language · Craft & Materials · Historical Context
- NEVER include: retail prices, where to buy, authentication, ownership history, purchase details
- NEVER write "quiet luxury"
- Content is about THIS SPECIFIC PIECE — not generic house history

## Page body — what is allowed vs banned

**Allowed on a collection item page body:**
- Images (rehosted to `giadaarchive/collection-images` public repo)
- Heritage & House Notes section (4 sections, written by `heritage.py`)

**Banned — never write these blocks to a Notion page:**
- `Description` heading or any paragraph with raw listing text
- Condition language: "excellent used condition", "美品", "Rank B/S/A", "signs of use"
- Auction context: "listed on Yahoo Japan", "auction has ended", "listed under women's tops category"
- Japanese resale boilerplate: dimensions in W/H/D, weight in grams, management numbers
- Field labels: "Manufacturer:", "Accessories: None", "Design:", "Color (pattern) system:"
- Disclaimers: "color may differ from photo", "also sold in-store", "may already be sold"
- Any Japanese resale site formatting or language

The listing text is used ONLY as input context for heritage.py — it is never written to the page.

## Cron jobs (macOS crontab — survive session restarts)
```
3 8 * * *   heritage.py --limit 100        # 8:03 AM SGT
8 8 * * *   heritage_audit.py --recent 100 # 8:08 AM SGT
30 8 * * *  retitle.py --recent 50         # 8:30 AM SGT
3 11 * * *  heritage.py --limit 200        # 11:03 AM SGT
8 11 * * *  heritage_audit.py --recent 200 # 11:08 AM SGT
```
All run AFTER the Anthropic API resets at 00:00 UTC = 08:00 SGT.
Logs: `/tmp/heritage_cron.log`, `/tmp/heritage_audit_cron.log`, `/tmp/retitle_cron.log`

## Checkpoint
`heritage_checkpoint.json` — tracks position for `--limit` runs (newest → oldest).
If checkpoint is exhausted (0 written, 0 skipped): `rm heritage_checkpoint.json` then rerun.

## Notion databases
- Collection DB: `ad079964969043ae9fa85a4f3ca1a9ee`
- Deinfluence DB: `349ccd15-cda1-8030-876a-dd491c9b992c`

## Target designers (heritage.py default run)
Hermès · Christian Dior · Chanel · Salvatore Ferragamo · Burberry · Louis Vuitton
`--force <page_id>` works for ANY brand.

## Skills files
`skills/` directory — task-specific how-to guides. Read before acting on collection items.
Key skills: `heritage-notes.md` · `add-collection-item.md` · `heritage-audit.md`

## Image hosting
Raw images on `main` branch → `raw.githubusercontent.com` permanent URLs for Notion.
Do NOT clone main branch locally (572MB). Scripts branch only.

## Content rules (apply to all generated copy)
- Positive framing only — say what something IS, not what it isn't
- No sycophantic openers ("great question", "you're on to something")
- Telegraphic style in replies to Lisa — full sentences in generated Notion content

## MISTAKES.md
Read before making structural Notion changes. Documents past errors (duplicate headings, wrong block types, etc).
