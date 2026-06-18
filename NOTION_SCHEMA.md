# Notion Schema Reference

API property names, types, and IDs for all databases. Property names are case-sensitive and must match exactly.

**Why this exists:** The Notion UI display name and the API property key are sometimes different. Every script must use the API key, not the display name.

---

## L's Collection of Amazing Pieces

**Database ID:** `ad079964-9690-43ae-9fa8-5a4f3ca1a9ee`

### Identity

| API Key | Type | Notes |
|---------|------|-------|
| `Second best` | `title` | The item name. Legacy key — do NOT rename |
| `Old Title` | `rich_text` | Previous name, kept for search |
| `SKU` | `rich_text` | Format: `BRAND-CAT-MAT-YY-###`. See `DESIGNER_IDS.md` |
| `Category` | `select` | `Basic` / `Basic wow` / `Wow` — how special the piece is |
| `Designer` | `relation` | → Designer database. Use `{"relation": [{"id": "DESIGNER_ID"}]}` |
| `Material Category` | `relation` | → Material Category database |
| `Colour` | `rich_text` | Plain text colour description |
| `Colour Detail` | `rich_text` | More specific colour note |

### Financial

| API Key | Type | Notes |
|---------|------|-------|
| `SGD` | `number` | Purchase price in SGD |
| `Retail Price (USD)` | `number` | Original retail if known |
| `Additional Costs` | `number` | Repairs, alterations in SGD |
| `Total Cost (SGD)` | `formula` | SGD + Additional Costs |
| `USD` | `formula` | SGD → USD |
| `Savings` | `formula` | Retail minus paid |
| `CPW (SGD)` | `formula` | Cost per wear |

### Time

| API Key | Type | Notes |
|---------|------|-------|
| `Year It's Made (first hand)` | `date` | Year of manufacture — drives YY in SKU |
| `Date I bought/own` | `date` | Acquisition date |
| `Added` | `created_time` | Auto-set by Notion |
| `Last Worn` | `rollup` | Most recent OOTD link |

### Dimensions & condition

| API Key | Type | Notes |
|---------|------|-------|
| `Dimensions` | `rich_text` | Single plain string: `"M / bust 39cm, length 48cm"` |
| `Condition` | `select` | Values: `S` (salon/new), `A` (excellent), `B` (good), `C` (fair) |

### Care

| API Key | Type | Values |
|---------|------|--------|
| `Wash Method` | `multi_select` | `Spot clean`, `Dry clean`, `Machine wash`, `Handwash` |
| `Wash Temperature` | `multi_select` | `Cold`, `20ºC`, `30ºC`, `40ºC`, `60ºC` |
| `Drying` | `select` | `Line dry`, `Lay flat to dry`, `Dryer` |
| `Storage Method` | `multi_select` | `Cedar box`, `Drawer`, `Hanger` |
| `Ironing` | `multi_select` | `Do not iron`, `Steam`, `Press cloth required`, `Medium` |
| `Season` | `multi_select` | `Spring`, `Summer`, `Autumn`, `Winter` |

### Tags (relations)

| API Key | Type | Notes |
|---------|------|-------|
| `Why I own it (Tags)` | `relation` | → Tags DB. Use IDs from `tag_id_map.json` |
| `What I'd change (Tags)` | `relation` | → Tags DB. Negative/change tags |
| `Why I own it` | `multi_select` | Flat multi-select version. Slugs must match `tag_id_map.json` |

### Status

| API Key | Type | Values |
|---------|------|--------|
| `Favourite` | `checkbox` | |
| `To Wear/Style` | `checkbox` | |
| `with/for mum` | `checkbox` | |
| `Thanks for the memories` | `checkbox` | Marks items leaving collection |

### Connections

| API Key | Type | Notes |
|---------|------|-------|
| `How L Styles` | `relation` | → OOTD database |
| `Fits` | `formula` | Wear count |
| `Archival Recorded/shared` | `date` | Date video was recorded or published |
| `Substack` | `status` | `Post to Substack` → `Posted` |

---

## Deinfluence Database

**Database ID:** `349ccd15-cda1-8030-876a-dd491c9b992c`

| API Key | Type | Notes |
|---------|------|-------|
| `Name` | `title` | English title: `Brand Item-type Key-detail` |
| `Source URL` | `url` | Original listing URL |
| `Price` | `number` | Listed price |
| `Why I was considering` | `multi_select` | Pull-factor tags. See `DEINFLUENCE_SKILLS.md` |
| `Why ultimately no` | `multi_select` | Push-factor tags |
| `L's comments and thoughts` | `rich_text` | Free-text notes — input for `deinfluence_tag.py` |

---

## OOTD / Lookbook Database

**Database ID:** stored in `NOTION_OOTD_DB` env var

| API Key | Type | Notes |
|---------|------|-------|
| `Name` | `title` | Date-based name |
| `Substack` | `status` | `Post to Substack` → `Posted` |
| `OOTD Story` | `rich_text` | Generated story text |
| `Items` | `relation` | → Collection database (actual API key, not "Items Worn") |

---

## Designer Database

**Database ID:** `079fa275-238c-4427-94b5-2c0b0f485bf9`

| API Key | Type | Notes |
|---------|------|-------|
| `Name` | `title` | Designer name |
| `SKU Code` | `rich_text` | 2–3 letter code used in SKU generation |

---

## Category Database

**Database ID:** `2eaccd15-cda1-8056-a4f6-c42c62c33851`

| API Key | Type | Notes |
|---------|------|-------|
| `Name` | `title` | Category display name |
| `SKU Code` | `rich_text` | 3-letter code. Run `setup_codes.py` to assign |

---

## Material Category Database

**Database ID:** `d9f03692-7341-41b7-b5fa-917cd6b37530`

| API Key | Type | Notes |
|---------|------|-------|
| `Name` | `title` | Material name |
| `SKU Code` | `rich_text` | 3-letter code. Run `setup_codes.py` to assign |

---

## Common mistakes

- **Wrong property key:** API rejects `"Title"` — correct key is `"Second best"`
- **Dimensions as dict:** Claude sometimes returns `{"labelled_size": "M"}` — the prompt must say "single plain string"
- **Multi-select vs relation tags:** `Why I own it` has both a `multi_select` property AND a `relation` property. The scripts use the multi-select version with slugs from `tag_id_map.json`
- **Status property:** Use `{"status": {"name": "Posted"}}` — not `select`, not `rich_text`
