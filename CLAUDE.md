# CLAUDE.md — lookbook-stories (giadaarchive/ootd-stories)

## What this repo is
Scripts + docs for Lisa's personal fashion archive "Second Best". Notion-backed system. Not a product — a personal archive in maintenance mode (no new acquisitions).

## Key scripts
| Script | Purpose | Run as |
|---|---|---|
| `heritage.py` | Write 4-section heritage notes to Notion item pages | `python3 heritage.py --limit N` or `--force <page_id>` or `--model <alias>` |
| `heritage_audit.py` | Add Craft & Materials + Verification & Sources | `python3 heritage_audit.py --recent N` |
| `lookbook.py` | Generate OOTD fashion stories from Notion | — |
| `llm.py` | Shared LLM client — routes Anthropic or OpenRouter | imported by other scripts |

## Model aliases (llm.py)
`sonnet` · `haiku` · `opus` · `llama` · `deepseek` · `qwen` · `mistral` · `gemma`
Default: `claude-sonnet-4-6`

## Heritage script rules
- 4 sections only: About This Piece · Design Language · Craft & Materials · Historical Context
- NEVER include: retail prices, where to buy, authentication, ownership history, purchase details
- NEVER write "quiet luxury"
- Content is about THIS SPECIFIC PIECE — not generic house history

## Cron jobs (recreate each session — they die on restart)
```bash
python3 heritage.py --limit 100   # 2:03 AM daily
python3 heritage_audit.py --recent 100  # 2:08 AM daily
python3 heritage.py --limit 200   # 5:03 AM daily
python3 heritage_audit.py --recent 200  # 5:08 AM daily
```
Crons are in macOS crontab (`crontab -l`) — survive session restarts.
Logs: `/tmp/heritage_cron.log` and `/tmp/heritage_audit_cron.log`

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
