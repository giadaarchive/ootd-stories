# Geographic Sourcing

A research database for understanding where fabric and fibre comes from — the mills, the regions, the history, and the quality markers. The goal is not just to collect information but to make it queryable: when evaluating a garment, you should be able to pull up the mill, understand its ownership history, and know what quality benchmarks that origin implies.

**Notion parent page:** `349ccd15cda1802c85abc926cb72fb79`

---

## What this is for

The silhouette, the cut, the designer — those are one layer. The deeper layer is the material: where was this fibre grown, who processed it, what mill wove it, and what does that origin mean for quality and longevity?

This database serves three uses:
1. **Garment evaluation** — when buying or appraising a piece, query by fibre or mill to understand what you're holding
2. **Travel planning** — flag mills worth visiting when travelling through a region
3. **Living research** — append new mills, notes from experts, and lessons from handling as knowledge grows

---

## The current content

The parent page currently holds two research tables as freeform page content:

**Table 1 — Oldest Mills by founding date** (8 mills: Chiso, VBC, Piacenza, Fox Brothers, Thomas Mason, Johnstons of Elgin, Abraham Moon, Dormeuil)

**Table 2 — Fibre-by-house reference** (12 entries across Silk, Wool, Cashmere, Linen, Cotton, Vicuña, Kashmir — with founding year, ownership status, and acquisition history)

Plus narrative notes on: why the "oldest mill" framing is Western-centric, Japan as the exception with its shinise culture, the absence of ancient vicuña houses (near-extinction in the 20th century), and Baby Cashmere as effectively a Loro Piana invention from the 1990s.

This content needs to migrate into queryable database rows.

---

## Proposed database architecture

```
Geographic Sourcing (parent page)
├── MILLS DB        — one row per mill / producer house
├── FIBRES DB       — one row per fibre type (the material encyclopedia)
└── REGIONS DB      — one row per producing region (geography layer)
```

### MILLS DB

One row per mill or production house. The core database.

| Property | Type | Purpose |
|----------|------|---------|
| `Name` | title | Mill / house name |
| `Country` | select | Country of operation |
| `Region` | rich_text | Specific region within country (e.g. Biella, Elgin, Kyoto) |
| `Fibre Speciality` | multi_select | Primary fibres produced |
| `Founded` | number | Year founded |
| `Ownership` | select | `Family-owned` / `Independent` / `Acquired by conglomerate` / `Part of group` |
| `Acquired By` | rich_text | Parent company and year if acquired |
| `Quality Tier` | select | `Reference standard` / `Premium` / `Good` / `Unknown` |
| `Visit-worthy` | checkbox | Worth visiting when in the region |
| `Visited` | checkbox | Has been visited |
| `Visit Notes` | rich_text | What to know before visiting — by appointment, public access, etc. |
| `Context` | rich_text | Ownership history, what makes them notable, relationship to designers |
| `Source` | rich_text | Where this information came from |
| `Last Updated` | date | |

### FIBRES DB

One row per fibre type. The material encyclopedia.

| Property | Type | Purpose |
|----------|------|---------|
| `Name` | title | Fibre name (e.g. `Mulberry Silk`, `Vicuña`, `Merino Wool (NZ)`) |
| `Fibre Family` | select | `Silk` / `Wool` / `Cashmere` / `Cotton` / `Linen` / `Specialty` |
| `Origin Geography` | rich_text | Where it comes from — key producing regions |
| `Key Producers` | rich_text | Mills / houses known for this fibre |
| `Quality Grades` | rich_text | How quality is tiered and what to look for |
| `What Best Quality Looks Like` | rich_text | Handle, drape, lustre, weight — physical markers |
| `Ethical / Sourcing Notes` | rich_text | Animal welfare, sustainability, certification bodies |
| `Care Difficulty` | select | `Simple` / `Moderate` / `Expert only` |
| `Link to Protocol` | relation | → THE PROTOCOLS in Laundry Science |
| `Lisa's Notes` | rich_text | Personal observations from handling |

### REGIONS DB

One row per producing region. Useful when planning travel or understanding why a geography dominates a fibre.

| Property | Type | Purpose |
|----------|------|---------|
| `Name` | title | Region name (e.g. `Biella, Italy`, `Elgin, Scotland`, `Suzhou, China`) |
| `Country` | select | |
| `Fibre Speciality` | multi_select | What this region is known for |
| `Why This Region` | rich_text | Climate, water, craft tradition, historical reasons |
| `Key Mills Here` | relation | → MILLS DB |
| `Travel Notes` | rich_text | When to visit, what to see, logistics |
| `Visited` | checkbox | |

---

## Priority fibres to document first

Given the collection focus on natural fibres and the upcoming New Zealand trip:

1. **Merino Wool (New Zealand)** — Smartwool, Canterbury, Zque certification, the difference between standard and ultrafine merino; key NZ stations and mills worth visiting
2. **Vicuña** — near-extinction history, Inca chakku harvesting revival, Michell & Cía (Peru) as primary processor, why it's the most expensive fibre in the world
3. **Cashmere** — Inner Mongolia vs. Kashmir pashmina vs. Scottish mills (Johnstons of Elgin); grade differences (A/B/C), dehairing process, baby cashmere as Loro Piana invention
4. **Mulberry Silk** — Japan (Nishijin, Kyoto) vs. China (Suzhou/Hangzhou) vs. Indian silk; grade 6A as reference standard; how to test by feel
5. **Tussah Silk** — wild silk vs. cultivated; coarser handle, more character; different lustre and texture profile from mulberry
6. **Sea Island Cotton** — where it actually comes from now (Barbados, St. Kitts, Caribbean); Supima vs. Pima vs. Sea Island distinctions; the Egyptian cotton problem (mislabelling)
7. **Wool (general)** — Super 100s to 200s grade system; when higher Super number is actually worse for everyday wear; Fox Brothers and Abraham Moon as reference houses

---

## New Zealand travel notes (placeholder — fill in before trip)

Key things to research before visiting NZ:
- Wool farms open to visitors (South Island vs. North Island)
- New Zealand Merino Company (ZQ certification programme)
- Icebreaker's partnership structure with NZ farmers
- Southern Hemisphere wool season (shearing in spring = September–November)
- Distinction between strong wool (carpet) and fine/superfine merino (apparel)
- Any mills in Christchurch or Wellington area open for visits

---

## The query script (future)

```bash
python3 geo_lookup.py "merino wool"       # returns fibre profile + key mills + NZ specifics
python3 geo_lookup.py "Johnstons of Elgin" # returns mill profile + fibres + visit info
python3 geo_lookup.py "Biella"            # returns all mills in that region
```

Also: a research scraper that takes a mill name and searches for ownership changes, brand news, and quality journalism — surfacing current information rather than relying on static entries.
