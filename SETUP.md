# Setup — ootd-stories

First-time environment setup for the `giadaarchive/ootd-stories` repo.

---

## Prerequisites

- Python 3.10+
- Node.js (for Playwright browser install)
- A Notion integration token with access to the collection and OOTD databases
- An Anthropic API key
- A GitHub personal access token with `repo` and `contents:write` scope

---

## 1. Clone the repo

```bash
git clone https://github.com/giadaarchive/ootd-stories.git
cd ootd-stories
```

---

## 2. Install Python dependencies

```bash
pip3 install -r requirements.txt
```

Dependencies: `anthropic`, `requests`, `python-dotenv`, `Pillow`, `pyotp`

---

## 3. Install Playwright browsers

Required for scraping Yahoo Japan auction pages:

```bash
pip3 install playwright
playwright install chromium
```

---

## 4. Create .env file

```bash
cp .env.example .env   # if .env.example exists, otherwise create from scratch
```

Required variables:

```env
NOTION_TOKEN=secret_...           # Notion integration token
ANTHROPIC_API_KEY=sk-ant-...      # Anthropic API key
GITHUB_TOKEN=ghp_...              # GitHub PAT with repo scope
GITHUB_REPO=giadaarchive/ootd-stories
NOTION_COLLECTION_DB=ad079964969043ae9fa85a4f3ca1a9ee
NOTION_OOTD_DB=<ootd-database-id>
```

---

## 5. Verify JSON support files

These files must be present in the repo root:

| File | Purpose |
|------|---------|
| `tag_id_map.json` | Maps tag slugs to Notion multi-select option IDs |
| `type_id_map.json` | Maps type slugs to Notion relation IDs |

If they are missing, query Notion to rebuild them:
```bash
python3 build_tag_map.py   # if this script exists
```
Otherwise, copy from a working install.

---

## 6. Test the setup

```bash
# Should print collection items — confirms Notion token and DB ID are correct
python3 -c "
import os, requests
from dotenv import load_dotenv; load_dotenv()
H = {'Authorization': f'Bearer {os.environ[\"NOTION_TOKEN\"]}', 'Notion-Version': '2022-06-28'}
r = requests.post('https://api.notion.com/v1/databases/ad079964969043ae9fa85a4f3ca1a9ee/query', headers=H, json={'page_size': 1})
print(r.status_code, r.json().get('results', [{}])[0].get('id', 'no results'))
"
```

---

## 7. Key database IDs

| Database | ID |
|---------|-----|
| L's Collection of Amazing Pieces | `ad079964969043ae9fa85a4f3ca1a9ee` |
| Deinfluence tracker | `349ccd15cda18030876add491c9b992c` |
| OOTD / Lookbook | (in `.env` as `NOTION_OOTD_DB`) |

---

## 8. Skills reference

See [`skills/INDEX.md`](./skills/INDEX.md) for the full list of tasks and scripts.

---

## Common setup errors

| Error | Cause | Fix |
|-------|-------|-----|
| `401 Unauthorized` from Notion | Wrong token or token not shared with database | Check `.env`, confirm integration is shared with the database in Notion settings |
| `ModuleNotFoundError: playwright` | Playwright not installed | `pip3 install playwright && playwright install chromium` |
| `KeyError: tag_id_map` | `tag_id_map.json` missing | Copy from another working install or rebuild |
| `404` when querying OOTD DB | Wrong DB ID in `.env` | Open the OOTD database in Notion, copy URL ID, update `NOTION_OOTD_DB` |
