# Laundry Science Deep Dive

A living knowledge base for garment care science. Not a static guide — a set of interconnected databases that grow as knowledge accumulates, experiments happen, and mistakes are made.

**Notion parent page:** `349ccd15cda1806b87b1ca41d041c666`

---

## Why databases, not a page

Static pages die. You add something once and never maintain it. Databases grow organically:

| Static page | Database structure |
|-------------|-------------------|
| Edit everything to add one entry | Add a row — instant update |
| No sorting or filtering | Filter: "Show all silk protocols" |
| No cross-linking | Click a product → see every incident it resolved |
| Dead within months | Date fields show the learning curve |
| Can't track evolution | Confidence levels update as knowledge improves |

---

## The six-database architecture

```
Laundry Science Deep Dive (parent page)
├── 1/ THE SCIENCE      — principles, chemistry, methodology
├── 2/ THE ARSENAL      — product reviews and ratings
├── 3/ THE EXPERIENCE   — personal incidents and mistakes
├── 4/ THE PROTOCOLS    — one row per fibre type (living document)
├── 5/ THE ACCIDENTS    — filtered view of Experience (failures only)
└── 6/ THE SOURCES      — experts, authors, communities consulted
```

---

## 1/ THE SCIENCE

**Notion DB:** `349ccd15cda18001998cfc9c9f593d90`

The foundational knowledge layer. One row per principle, system, or research piece. Grows as new science is learned.

### Properties

| Property | Type | Purpose |
|----------|------|---------|
| `Name` | title | Descriptive title in ALLCAPS — what the entry covers |
| `Domain` | select | `laundry` / `textile-care` / `fabric-science` / `stain-removal` |
| `Type` | select | `System` (complete protocol) / `Protocol` (specific procedure) / `Research` (external finding) / `Guide` (reference) |
| `Source` | rich_text | Who wrote it and where — Reddit handle, publication, YouTube channel |
| `URL` | url | Link to original source |
| `Agent_Use_Case` | rich_text | One-line instruction for when a lookup script should surface this entry |
| `Last Updated` | date | When the entry was last reviewed or revised |

### Page body structure

Each entry follows a consistent internal format:

```
## METADATA
- SOURCE: [author, platform, URL]
- TYPE: [System / Protocol / Research / Guide]
- DOMAIN: [domain tag]
- CONFIDENCE: [Certain / Probable / Disputed / Unverified]
- LAST_UPDATED: [date]

## CORE_DEFINITION
[One paragraph — what this entry is about]

## KEY_RULES
- DO / DO NOT / IF...THEN format
- Most important actionable rules first

## CONCEPTS
- Term — Definition [source if specific]

## REFERENCES
- [person/product/resource] — [role] — [how it connects to this entry]

## AGENT_INSTRUCTIONS
[When and how a lookup script should use this entry]
```

### How to add a new entry

1. Create a new row. Title in ALLCAPS — descriptive, searchable.
2. Set Domain and Type in the properties panel.
3. Add source and URL if external.
4. In the page body: follow the METADATA → CORE_DEFINITION → KEY_RULES → CONCEPTS → REFERENCES structure.
5. Set Agent_Use_Case to a one-line trigger sentence (e.g. "Use when advising on enzyme pretreatment for protein stains").
6. Set Last Updated to today.

### Current entries (25)

The existing 25 entries cover: Laundry 101 daily system, Spa Day enzymatic reset protocol, stain identification, fibre guides (cashmere, wool, cotton), product-specific protocols (citric acid rinse, oxygen bleach, lipase detergents), storage rules, and specialist topics (shoe cleaning, colour transfer, collar reshaping).

---

## 2/ THE ARSENAL

**Notion DB:** `349ccd15cda1803eaa5dc1b01506ab9e`

Product reviews. One row per product tested. Updates when a product is repurchased, discontinued, or superseded.

### Properties

| Property | Type | Purpose |
|----------|------|---------|
| `Name` | title | Product name as sold |
| `Brand` | rich_text | Manufacturer |
| `Type` | select | `Detergent` / `Booster` / `Pretreater` / `Rinse Aid` / `Stain Remover` / `Softener` / `Specialist` |
| `Use Case` | multi_select | `Enzyme-heavy` / `Silk & Wool` / `Colour Care` / `Whitening` / `Odour Control` / `Delicates` |
| `Rating` | select | `★★★★★` / `★★★★` / `★★★` / `★★` / `★` |
| `Repurchase` | checkbox | Would buy again? |
| `Price (SGD)` | rich_text | Current price and pack size |
| `Where to Buy` | rich_text | Don Don Donki / iHerb / Amazon / local |
| `Last Reviewed` | date | When this row was last updated |

### How to add a new product

Row per product, reviewed after at least 3 uses. Update Repurchase checkbox each time you reorder or decide to replace.

---

## 3/ THE EXPERIENCE

**Notion DB:** `349ccd15cda18048b0def3f24c059c7e`

Personal incident log. One row per incident. Never delete — failures are as instructive as successes. Numbers accumulate: Lemaire shirt #001, #002 shows the learning curve.

### Properties

| Property | Type | Purpose |
|----------|------|---------|
| `Name` | title | `[Garment description] #[incident number] — [brief description]` e.g. "Lemaire shirt #001 — collar sweat stain" |
| `Date` | date | When the incident occurred |
| `Incident Type` | select | `Stain` / `Shrinkage` / `Colour Transfer` / `Pilling` / `Odour` / `Damage` / `Other` |
| `Severity` | select | `Minor` / `Moderate` / `Severe` / `Irreversible` |
| `Resolution` | select | `Resolved` / `Partial` / `Failed` / `Ongoing` |
| `Lesson Learned` | rich_text | One sentence — what this incident taught |
| `Person of Authority` | rich_text | Expert consulted, if any |
| `Source` | rich_text | Protocol used, product applied, or guide followed |

### Page body

Each incident: before/after photos if available, full description of what happened, what was tried, what worked, what didn't, and what to do differently.

---

## 4/ THE PROTOCOLS

**Notion DB:** `349ccd15cda180e5b0aee5a68e9beb98` *(updated schema — see below)*

One row per fibre or material type. This is the living care reference — not a static chart, but a row that gets updated as knowledge improves.

### Properties

| Property | Type | Purpose |
|----------|------|---------|
| `Name` | title | Fibre or material type (e.g. `Mulberry Silk`, `Cashmere`, `Virgin Wool`, `Vicuña`) |
| `Fibre Category` | select | `Natural` / `Semi-synthetic` / `Synthetic` |
| `Wash Method` | select | `Handwash only` / `Machine — delicate` / `Dry clean` / `Spot clean only` |
| `Temperature` | select | `Cold` / `20ºC` / `30ºC` / `Hand temperature` |
| `Drying` | select | `Lay flat` / `Line dry in shade` / `Do not wring` |
| `Ironing` | select | `Do not iron` / `Steam only` / `Low heat + press cloth` / `Medium heat` |
| `Storage` | select | `Cedar box` / `Breathable bag` / `Acid-free tissue` / `Hanging` |
| `Key Caution` | rich_text | The one thing that destroys this fibre if ignored |
| `Singapore Note` | rich_text | Local-specific adjustments (humidity, heat, pest pressure) |
| `Last Updated` | date | |

### Priority fibres to populate first

Cashmere → Mulberry Silk → Tussah Silk → Vicuña → Merino Wool → Virgin Wool → Sea Island Cotton → Linen → Leather (smooth) → Suede

---

## 5/ THE ACCIDENTS

Not a separate database — a filtered view of THE EXPERIENCE where `Resolution` = `Failed` or `Irreversible`. Create this as a linked view within the parent page filtered to show only failures.

---

## 6/ THE SOURCES

A lightweight reference database for experts, communities, and authoritative voices cited across THE SCIENCE.

| Property | Type | Purpose |
|----------|------|---------|
| `Name` | title | Person, community, or publication |
| `Type` | select | `Reddit` / `YouTube` / `Book` / `Expert / Practitioner` / `Brand` |
| `Handle / URL` | url | Link to their primary resource |
| `Credibility` | select | `High` / `Medium` / `Unverified` |
| `Speciality` | rich_text | What they are expert in |

---

## Singapore-specific context

- **Water hardness:** Singapore tap water is moderately hard. Enzyme detergents designed for soft water may underperform — check the Lipase List for hard-water-compatible options.
- **Humidity:** 85–95% year-round. Natural fibres (wool, cashmere, silk) need active moisture control in storage. Cedar blocks alone are insufficient — use silica gel packs refreshed monthly.
- **Moths:** Year-round threat (no cold season to break cycles). Wash or dry-clean before storage; moths target body oils, not just the fibre.
- **Local suppliers:** Don Don Donki for Perwoll and specialist detergents. iHerb for US products not available locally (Tide Rescue, enzyme boosters). Record alternatives in THE ARSENAL when primary sources are out of stock.

---

## The lookup script (future)

The goal is a CLI tool:
```bash
python3 laundry_lookup.py "mulberry silk stain"
python3 laundry_lookup.py "cashmere protocol"
python3 laundry_lookup.py "spa day"
```

The script queries THE SCIENCE by fibre keyword or topic, surfaces the most relevant entries (by `Agent_Use_Case` match), and returns the `KEY_RULES` and `CONCEPTS` sections. THE PROTOCOLS provides a fast care card. THE ARSENAL recommends products.
