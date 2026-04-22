# Second Best
> *The best things in life are free. The second best are very expensive.*
This is a personal archive. A working record of what exists, where it lives, how it is used, and how it is maintained. The collection is work of several lifetimes and an ongoing work in progress. The next chapter now includes stewardship: wear what you have, care for it properly, document the usage.
Second Best is everything: clothing, bags, shoes, jewellery, watches, eyewear, homeware, art, objects. If it was purchased and it matters, it is here.

---

## Philosophy
The truly best things — time, attention, loyalty, a good meal in good company — cannot be catalogued. What can be catalogued is the material layer: the objects that, when chosen well and maintained properly, support a life rather than complicate it.
Second Best is built on three principles:
- **Own less, know more.**  Every item has a record. Every record has a SKU. If you cannot find it in the database, it does not officially exist.
- **Wear what you have.**  The L’s Collection of Amazing Pieces is an inventory. The question is never “what should I buy?” but “what do I already own, and am I using it?”
- **Document the usage.**  The L’s Lookbook Style tracks every outfit worn. A garment with no wear history is a garment asking to be reconsidered.
> 🛑 Lisa is no longer acquiring. This README documents a system in maintenance mode, not growth mode.

---

## System Architecture
Second Best runs on Notion. It is a relational database system — six databases that talk to each other, each with a specific function.
```
WARDROBE ITEMS  <->  DESIGNER
      |                (brand codes, SKU prefixes)
   CATEGORY      <->  MATERIAL CATEGORY
      |                (fabric/composition codes)
    COLOUR
      |
   OOTD / LOOKBOOK
      (outfit records, editorial stories, Substack)
```

### Wardrobe Items
The spine of the system. Every physical object has one row. Key fields:
- SKU — unique identifier. Format: BRAND-CATEGORY-MATERIAL-YY-###
- Designer — relation to Designer database Designer Brands 
- Category — relation to Category database Category of Clothes and Untitled 
- Material Category — relation to Material Category database Second Best Materials  
- Colour — relation to Colour database Untitled 
- Year It's Made — year of manufacture, not purchase. Drives the YY in the L’s Collection of Amazing Pieces property 
- Date I bought/own — date of acquisition
- SGD — purchase price in Singapore dollars
- Retail Price (USD) — original retail if known, Otherwise look for it online for comparables
- CPW (SGD) — cost per wear, calculated automatically
- Season — multi-select: Spring / Summer / Autumn / Winter
- Storage Method — how To store the garment for longevity
- Wash Method — care instructions
- Thanks for the memories — checkbox marking items no longer in the collection 

### Designer
One row per brand. Holds the 3-letter brand code used in SKUs via the SKU Code field. Examples: Hermes = HER, Chanel = CHA, Louis Vuitton = LV, Unbranded = UNB.

### Category
Twelve categories, intentionally broad. Each holds a 3-letter SKU Code:
- Tops & Shirts = TOP
- Dresses = DRS
- Trousers & Shorts & Skirts = TRS
- Outerwear = OUT
- Jumpsuits & Rompers = JMP
- Bag = BAG
- Shoes = SHO
- Jewellery & Watches = JEW
- Scarf, Shawl, Stoles = SCF
- Eyewear = EYE
- Hat & Gloves = HAT
- Lingerie = LNG
These categories are the broad categories within them there are specific pieces in the pieces database Untitled. 

### Material Category
Fabric and composition types. Each holds a 3-letter SKU Code — for example SIL for silk, LEA for leather, MIX for mixed/unknown.

### Colour
Colour names used for filtering and visual organisation. Linked to the specific garment. When looking at the OOTD, the colour can be analysed easily. 

### OOTD / Lookbook
Outfit records. One row per day an outfit was worn. Links back to Wardrobe Items via the Items relation and drives the Substack publication.
- Worn — date
- Items — relation to Wardrobe Items (specific garments worn in this specific outfit)
- OOTD Story — AI-generated editorial caption
- Substack — status: No Post / Post to Substack / Posted

---

## The SKU System
Every item has a unique SKU. Format:
```
BRAND_CODE - CATEGORY_CODE - MATERIAL_CODE - YY - ###

Example: HER-BAG-LEA-98-001
(Hermes bag, leather, made 1998, first of its kind in the archive)
```
- BRAND_CODE — from Designer database, SKU Code field Designer Brands 
- CATEGORY_CODE — from Category database, SKU Code field Category of Clothes 
- MATERIAL_CODE — from Material Category database, SKU Code field Second Best Materials  
- YY — 2-digit year from Year It's Made (manufacture year, not purchase)
- ### — sequential number per brand + category + material + year combination
- UNB = unbranded. MTM = made to measure.
To generate or regenerate SKUs: run generate_skus.py. All codes are read from the database — nothing is hardcoded. UNB items are automatically redone when the script runs.

---

## Adding a New Item
> 📦 Lisa is not buying. But undocumented items surface, and gifts arrive.
1. Create a new row in Wardrobe Items
1. Fill: title, Designer (relation), Category (relation), Material Category (relation), Colour, Year It's Made, SGD, Season, Storage Method, Wash Method
1. Leave SKU blank — run generate_skus.py to assign it automatically
1. If the designer is new: add a row to the Designer database first with a 3-letter SKU Code
If the category or material is genuinely new — unlikely, the 12 categories are intentionally broad — add to the relevant database and run setup_codes.py first.

---

## Recreating the System
If Notion disappears, here is how to rebuild from scratch.

### Step 1 — Create six databases
Wardrobe Items, Designer, Category, Material Category, Colour, OOTD

### Step 2 — Wire the relations
- Wardrobe Items → Designer (many-to-one)
- Wardrobe Items → Category (many-to-one)
- Wardrobe Items → Material Category (many-to-one)
- Wardrobe Items → Colour (many-to-many)
- OOTD → Wardrobe Items (many-to-many, via Items field)

### Step 3 — Add the formula fields
- CPW (SGD) = SGD divided by number of times worn (rollup count from OOTD)
- Age of Garment = today minus Year It's Made

### Step 4 — Repopulate lookup databases
- 12 Categories with their codes (see above)
- All designers with their 3-letter codes
- All material categories with their codes

### Step 5 — Run the scripts
```bash
python3 setup_codes.py    # writes codes to Category and Material databases
python3 generate_skus.py  # writes SKUs to all Wardrobe Items
```

### Step 6 — Restore OOTD stories
```bash
python3 lookbook.py       # regenerates AI captions (requires Anthropic API key)
python3 substack.py       # schedules posts to Substack
```

---

## Care & Storage — Singapore
> 🌧️ Singapore is 85-90% humidity and 30 degrees year-round. Moths operate on no seasonal schedule here. This section is wardrobe advice to where Lisa lives. 
- **Leather.**  Condition every 3-6 months. Singapore damp causes leather to crack from the inside before the surface shows damage. Use leather conditioner, not polish. Store in dust bags, not plastic.
- **Moths.**  Use cedar wood year-round. Moths are attracted to body oils, not just the fibre itself. Wash or dry-clean natural fibres before storage.
- **Humidity.**  Every storage space needs a dehumidifier or silica gel packs, refreshed monthly. Cedar blocks help but are not sufficient on their own.
- **Structured bags.**  Stuff with acid-free tissue to maintain shape. Store upright. Do not stack.
- **Silk.**  Store folded, never on wire hangers. Light degrades silk — keep in dark storage or garment bags.
- **Watches.**  Humidity affects mechanical movements. Store in a watch box with silica gel. Service every 3-5 years regardless of whether anything seems wrong.
The Storage Method and Wash Method fields in the database exist for a reason. Fill them.

---

## Navigation
- By brand: filter Wardrobe Items by Designer relation
- By category: filter by Category relation
- By date worn: open OOTD database, filter by Worn date
- Most-worn items: sort by CPW (SGD) ascending — lowest cost per wear = best value in actual use
- Unworn items: sort by Last Worn (rollup) ascending, nulls first
- Items for departure: filter Wardrobe Items where Thanks for the memories is ticked
- By SKU prefix: filter SKU contains the brand code, e.g. HER for all Hermes

---

## The Lookbook & Substack
Every outfit in the OOTD database generates an editorial caption via lookbook.py, which uses Claude. Captions are editorial, precise, and structurally varied — no two posts follow the same format.
Posts publish to giadaarchive.substack.com daily at 01:00 GMT via substack.py. Images are hosted at github.com/giadaarchive/ootd-stories (public repository).
To queue a post: set the Substack status on an OOTD entry to Post to Substack. The script picks it up on the next run.

---

## The Deinfluence Tracker

A parallel system for tracking what Lisa considered buying but ultimately said no to. The goal is not just to log individual rejections — it is to surface patterns in what attracts her and what stops her. The tags are the training data.

### Scripts

| Script | What it does |
|--------|-------------|
| `deinfluence_collector.py <URL>` | Scrapes a shop listing (Mercari, Yahoo Auctions, Rakuma/Fril), translates via Claude, creates a Notion entry with title, images, price, and source URL |
| `deinfluence_tag.py <URL>` | Reads "L's comments and thoughts" from a Notion entry, calls Claude to generate tags, writes to relation properties in the Tags DB |
| `deinfluence_tag.py --all` | Tags every untagged entry in the database |
| `deinfluence_tag_migration.py` | One-time setup: populates the Tags DB and Type DB, migrates old multi_select entries to proper relations, tags wardrobe entries |

### Database architecture

Three Notion databases work together:

- **Deinfluence DB** (`349ccd15cda18030876add491c9b992c`) — one row per item considered and rejected. Relations: `Why considering (Tags)` and `Why not (Tags)` → Tags DB.
- **Tags DB** (`34accd15cda1800a8548c5223ce17612`) — one row per tag slug. Back-relations show how many items carry each tag, enabling count-based pattern analysis.
- **Type DB** (`34accd15cda1805782cad566fce79ef2`) — categorises tags into semantic groups: branding, quality, identity, overlap, designer, etc.

The `tag_id_map.json` and `type_id_map.json` files in this repo map tag names to their Notion page IDs.

### What the data shows

Sort the Tags DB by count to read the patterns across the full decision history:

- **`size-wrong` is the most frequent dealbreaker.** Many items with strong pull factors fail solely on sizing — a sourcing constraint, not a preference failure.
- **"Why yes" is identity-driven, not trend-driven.** The dominant pull tags are `craftsmanship`, `timeless-silhouette`, `love-the-designer`, and `brand-legacy`. The attraction is to quality of making and alignment with a specific aesthetic philosophy.
- **Logo fatigue is a consistent blocker for heritage accessories**, even when other pull factors are strong.

See `DEINFLUENCE_SKILLS.md` for the full tag vocabulary, decision framework, and key distinctions.
---
> *Second Best. Everything else is commentary.*
