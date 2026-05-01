# Second Best
> *The best things in life are free. The second best are very expensive.*

Personal archive system for Lisa's wardrobe collection. Scripts, documentation, and workflow tools.

**Images:** `main` branch — raw.githubusercontent.com permanent hosting for Notion
**Scripts & docs:** `scripts` branch — this branch

---

## Restoring on a new machine

```bash
# 1. Clone scripts only (main branch is images only — 572MB, don't clone it)
git clone -b scripts --single-branch https://github.com/giadaarchive/ootd-stories.git lookbook-stories
cd lookbook-stories

# 2. Install Python dependencies
pip3 install -r requirements.txt
pip3 install playwright
playwright install chromium

# 3. Create .env — copy this template and fill in values
cat > .env << 'EOF'
NOTION_TOKEN=secret_...
NOTION_DATABASE_ID=ad079964-9690-43ae-9fa8-5a4f3ca1a9ee
ANTHROPIC_API_KEY=sk-ant-...
GITHUB_TOKEN=ghp_...
GITHUB_REPO=giadaarchive/ootd-stories
DEINFLUENCE_DB_ID=349ccd15-cda1-8030-876a-dd491c9b992c
SUBSTACK_EMAIL=...
SUBSTACK_PASSWORD=...
SUBSTACK_TOTP_SECRET=...
EOF

# 4. Re-authenticate Substack (first run only)
python3 setup_cookies.py

# 5. Verify Notion connection
python3 -c "
import os, requests
from dotenv import load_dotenv; load_dotenv()
H = {'Authorization': f'Bearer {os.environ[\"NOTION_TOKEN\"]}', 'Notion-Version': '2022-06-28'}
r = requests.post('https://api.notion.com/v1/databases/ad079964969043ae9fa85a4f3ca1a9ee/query', headers=H, json={'page_size': 1})
print('OK' if r.status_code == 200 else f'FAIL: {r.status_code}')
"
```

---

## Where to find things

| What | File |
|------|------|
| Skills index — every task, one file | [`skills/INDEX.md`](skills/INDEX.md) |
| All Notion property keys and DB IDs | [`NOTION_SCHEMA.md`](NOTION_SCHEMA.md) |
| Designer IDs + SKU codes | [`DESIGNER_IDS.md`](DESIGNER_IDS.md) |
| First-time setup (detail) | [`SETUP.md`](SETUP.md) |
| Errors and how to fix them | [`MISTAKES.md`](MISTAKES.md) |
| Workflow gaps to address | [`GAPS.md`](GAPS.md) |

---

## System overview

### Repo architecture

```
Notion (source of truth)
    │
    ├── lookbook-stories (this repo)
    │       │
    │       ├── heritage.py / retitle.py / lookbook.py  → writes back to Notion
    │       ├── llm.py (Anthropic + OpenRouter) — shared LLM client
    │       │
    │       └── house_codes/   ──► Andromeda — reactive fashion knowledge graph
    │               │
    │               ├── query_engine.py   reactive query → fetch → extract → answer
    │               ├── graph.py          JSON flat-file knowledge graph
    │               ├── vision_extract.py runway look images → vision codes
    │               ├── fetch_show.py     tag-walk + YouTube fetchers (cached)
    │               └── data/             brands.json · seasons.json · instances.json
    │
    └── giadaarchive-shop ──► reads Notion at build time → renders shop pages on Vercel
            │
            └── images hosted here (main branch, raw.githubusercontent.com)
```

**Related repos:** `giadaarchive/shop` (Next.js storefront) · `giadaarchive/writelikeL` (voice/tone guide) · `giadaarchive/behindthecultured` (brand strategy)

---

## Andromeda — runway knowledge graph

Answers fashion questions from real runway data. Fetches on demand, caches in graph, never pre-builds speculatively.

```bash
# Ask a question (streams live brand status + answer)
python3 house_codes/query_engine.py --stream "What materials are trending for AW2026?"

# Web UI (port 3131)
cd frontend && npm run dev
```

**Model stack — 100% open-source (OpenRouter):**
- Qwen-2.5-72B → question interpretation + synthesis
- Qwen2.5-VL-72B → vision extraction from runway look images
- Llama-3.3-70B → taxonomy validation
- Disk cache (30d) → zero tokens on repeat questions

**Data:** `house_codes/data/` — flat JSON graph. Seeded with 14 brands, 27 seasons, 229 instances. Grows reactively as queries arrive.

### Notion databases wired together

```
WARDROBE ITEMS  ←→  DESIGNER          (brand codes, SKU prefixes)
      ↕              CATEGORY          (12 categories, SKU codes)
MATERIAL CATEGORY    COLOUR
      ↕
OOTD / LOOKBOOK  →  Substack (giadaarchive.substack.com)
```

Scripts handle: scraping new items, hosting images on GitHub, writing AI heritage notes, generating OOTD stories, scheduling Substack posts, tagging, SKU generation, wardrobe analytics.

---

## Key database IDs

| Database | ID |
|----------|----|
| L's Collection of Amazing Pieces | `ad079964-9690-43ae-9fa8-5a4f3ca1a9ee` |
| Deinfluence tracker | `349ccd15-cda1-8030-876a-dd491c9b992c` |
| Category | `2eaccd15-cda1-8056-a4f6-c42c62c33851` |
| Material Category | `d9f03692-7341-41b7-b5fa-917cd6b37530` |

Full schema with all property types: [`NOTION_SCHEMA.md`](NOTION_SCHEMA.md)

---

## SKU format

```
BRAND-CATEGORY-MATERIAL-YY-###
Example: LV-BAG-CNV-96-001
```

Run `python3 generate_skus.py` to assign SKUs to all new items. Run `python3 setup_codes.py` first if any category or material is missing a code.

---

## Publishing pipeline

```
Notion OOTD entry (photos + items worn)
    ↓  python3 lookbook.py
AI story written to Notion
    ↓  set Substack status → "Post to Substack"
    ↓  python3 substack.py
Scheduled on Substack — weekdays 9am SGT
```
