# Deinfluence Decision Skills

This file is the living knowledge base for Lisa's deinfluence fashion tracker. It documents the decision framework, vocabulary, and reasoning patterns that emerge as entries are added. It is used as context for AI tagging and for recognising trends across purchases considered and rejected.

---

## What this tracker is

A database of items Lisa considered buying but did not. The point is not just to track individual decisions — it is to surface *patterns* in what attracts her and what ultimately stops her. The tags are the training data. The richer and more consistent the vocabulary, the more the database can teach.

---

## The scripts

| Script | What it does |
|--------|-------------|
| `deinfluence_collector.py <URL>` | Scrapes a shop listing (Mercari, Yahoo Auctions, Rakuma/Fril, PayPay Flea Market), translates to English via Claude, creates a Notion entry with title, images, price, and source URL |
| `deinfluence_tag.py <URL>` | Reads "L's comments and thoughts" from a Notion entry and uses Claude to generate why-yes / why-no tags, written to relation properties |
| `deinfluence_tag.py --all` | Tags every entry in the database that has notes but no tags yet |
| `deinfluence_tag_migration.py` | One-time setup: populates the Tags DB and Type DB, migrates old multi_select tags to proper relations, tags wardrobe entries |

To tag a single entry with inline notes (without writing to Notion first):
```
python3 deinfluence_tag.py <notion_url> "your reasoning here"
```

---

## The Notion database system

### Deinfluence database
**Database ID:** `349ccd15cda18030876add491c9b992c`

| Property | Type | Purpose |
|----------|------|---------|
| Item - Third Best | title | English item name |
| URL | url | Source listing link |
| Price | rich_text | Listed price with currency |
| L's comments and thoughts | rich_text | Lisa's freeform reasoning — input for tagging |
| Why considering (Tags) | relation → Tags DB | Pull factors — what made it tempting |
| Why not (Tags) | relation → Tags DB | Dealbreakers — what stopped the purchase |

### Tags database
**Database ID:** `34accd15cda1800a8548c5223ce17612`

One row per tag. Each tag has:
- `Name` — the tag slug (e.g. `craftsmanship`, `size-wrong`)
- `Type` — relation to the Type database (categorises the tag)
- Two-way relation columns populated by the deinfluence and wardrobe databases

The Tags DB is the analytical engine. Because it is a proper relational database with back-relations, each tag row shows a count of how many items carry that tag. This makes pattern analysis possible at the vocabulary level, not the item level.

### Type database
**Database ID:** `34accd15cda1805782cad566fce79ef2`

Categorises tags into semantic groups: `branding`, `quality`, `construction`, `material`, `value`, `overlap`, `identity`, `designer`, `silhouette`, `unique`, `occasion`, `size`, `emotion`, `colour`.

### How to read the patterns

Open the Tags DB. The formula count columns show which tags are accumulating across decisions. This is the primary analytical view — not filtering individual items, but asking: across everything Lisa has considered and rejected, which reasons are most frequent? Sort by count descending.

The two analytical streams are separate by design:
- **Why considering** (pull) — what draws her in
- **Why not** (dealbreaker) — what stops the purchase

These are not opposites. An item can score high on both — drawn in by `craftsmanship` and `love-the-designer`, blocked by `size-wrong`. The interesting items are the ones with strong pull scores that still didn't make it.

---

## Tag vocabulary

### Why I was considering (pull factors)

| Tag | Type | Meaning |
|-----|------|---------|
| `vintage-provenance` | unique | The item has a documented era, date, or origin story that adds value |
| `investment-piece` | value | Likely to hold or gain value; justifiable as a long-term buy |
| `natural-patina` | construction | Aged leather, wear, or material character that can't be faked |
| `travel-worthy` | occasion | Elevated enough to bring on a trip; not for everyday use |
| `craftsmanship` | quality | Quality of construction, materials, or making that stands out |
| `rare-find` | unique | Hard to source; unlikely to appear again |
| `brand-legacy` | designer | Drawn to the brand's history and heritage as an institution |
| `love-the-designer` | designer | Drawn specifically to the creative director or designer as a person and their vision — not the brand as a commercial entity, but the individual behind it (e.g. Lemaire as designer-owner) |
| `brand-discovery` | designer | Want to learn more about this brand; not yet familiar, this is a gateway piece |
| `versatile` | identity | Works across many contexts in the wardrobe |
| `timeless-silhouette` | identity | The shape or cut is not trend-dependent |
| `pattern-integrity` | construction | The print or pattern is handled with exceptional care in construction — matching, placement, balance |
| `colour` | colour | The specific colour is a primary draw — positive pull from the colour itself |
| `sentimental` | emotion | Emotional attachment or personal story tied to this item or its origin |
| `gifted` | emotion | Bought as a gift, or received as one |

### Why ultimately no (dealbreakers)

#### Logo / branding
| Tag | Type | Meaning |
|-----|------|---------|
| `visible-logo` | branding | The logo is prominent and unavoidable |
| `loud-branding` | branding | The brand identity is loud in a way that feels performative |
| `logo-fatigue` | branding | General tiredness with recognisable brand signalling |

#### Wardrobe conflicts
| Tag | Type | Meaning |
|-----|------|---------|
| `have-equivalent-in-wardrobe` | overlap | Already own something functionally and aesthetically equivalent — this would be a direct duplicate |
| `have-better-in-wardrobe` | overlap | Already own something that outperforms this — this would be a downgrade |
| `doesnt-fit-my-wardrobe` | identity | The item has no natural home in the existing wardrobe; nothing to wear it with |
| `doesnt-fit-my-style` | identity | Aesthetically appealing and well-made but not who Lisa is — the item belongs to a different person's story |
| `wrong-fabric-for-use-case` | material | The material doesn't suit the way she'd actually wear or use it |

#### Item issues
| Tag | Type | Meaning |
|-----|------|---------|
| `price` | value | The price is the primary blocker |
| `condition` | quality | The item's physical condition is worse than acceptable |
| `size-wrong` | size | The sizing doesn't work |
| `wrong-colour` | material | The colour doesn't work for the wardrobe or doesn't suit |
| `misleading-material-claim` | quality | The listing misrepresented the fabric or material |

#### Design issues
| Tag | Type | Meaning |
|-----|------|---------|
| `too-common-silhouette` | silhouette | The shape is generic; nothing distinctive about it |
| `derivative-design` | silhouette | The design is imitative of something better; lacks its own point of view |

---

## Decision framework: key distinctions

### The three core "no" reasons for wardrobe conflicts

These three are very different and should not be collapsed:

1. **`have-equivalent-in-wardrobe`** — "I already own this." The gap in the wardrobe this would fill is already filled. Buying it would create a direct duplicate.

2. **`have-better-in-wardrobe`** — "I own something that beats this." This item would be a lateral or downward move. The money is better spent elsewhere.

3. **`doesnt-fit-my-style`** — "I am drawn to it but it is not who I am." The item is beautiful and well-made, but it belongs to a different aesthetic identity. The attraction is intellectual or aspirational, not personal.

### Brand vs. designer

- **`brand-legacy`** = institutional pull — the house, the heritage, the archive. Could be any designer era.
- **`love-the-designer`** = personal pull — a specific creative person whose vision Lisa wants to support and collect. The brand is almost incidental. Example: Christophe Lemaire, where the designer IS the brand, is the owner, and his aesthetic sensibility is the reason to collect.

### Style vs. wardrobe

- **`doesnt-fit-my-wardrobe`** = practical gap — there is literally nothing to wear it with, no occasion, no context.
- **`doesnt-fit-my-style`** = identity gap — the item is appealing but it's not her. This is about self-knowledge, not logistics.

### Reading logo reasoning from casual language

The three logo tags are often all relevant at once. Do not skip them because the owner uses informal language. Map it:

| What Lisa says | What tag to apply |
|---------------|-----------------|
| "very loud logos", "too much branding", "logo-forward" | `loud-branding` |
| "I'm not a logo person", "I don't like paying for logos", "logos make me uncomfortable", "I don't want to pay for the logo" | `logo-fatigue` |
| The logo on this specific item is prominent, monogram all-over, or unavoidable | `visible-logo` |

These three can and should be applied together when notes mention logos. Example: *"it has very loud logos and I'm not a logo person, I'm not willing to pay money for a logo"* → all three logo tags.

A common failure mode is applying only the functional blockers (`doesnt-fit-my-wardrobe`, `doesnt-fit-my-style`) while missing the logo reason that the owner stated explicitly as the primary driver. When logo language appears, it is almost always the lead reason, not a footnote.

---

## Emerging patterns

The Tags DB count columns are the primary analytical tool. Sort by tag count to surface patterns across the full database — not at the item level, but at the vocabulary level.

### Why she says no — dominant patterns

**`size-wrong` is the most frequent dealbreaker by count.** Many otherwise desirable items (strong pull tags, clear yes reasons) fail solely because the sizing doesn't work. This is not a preference failure — it is a sourcing constraint. The implication: when evaluating items, check the size before investing time in the rest of the analysis.

Secondary no patterns: `have-better-in-wardrobe` and `doesnt-fit-my-wardrobe` appear frequently together, suggesting the wardrobe is mature — there are few gaps, and new items face high competition from what already exists.

### Why she says yes — dominant patterns

**"Why yes" decisions are identity-driven, not trend-driven.** The most frequent pull tags are `craftsmanship`, `timeless-silhouette`, `love-the-designer`, and `brand-legacy` — not `colour` or `versatile`. This is a consistent signal: the attraction is to quality of making and alignment with a specific aesthetic philosophy, not to current trends or practical wardrobe logic.

**Classic cuts as a framework.** The recurrence of `timeless-silhouette` across many categories (bags, jackets, skirts, knits) reflects a coherent collecting philosophy: the silhouette must be non-trend-dependent. Items that would look dated within three years rarely pass the pull threshold.

**Designer attachment is personal, not commercial.** `love-the-designer` appears most often for Lemaire, Andrew GN, and certain Hermès creative director eras. The pull is toward the individual vision, not the brand machine.

### Logo fatigue is a consistent blocker for heritage accessories

`visible-logo`, `loud-branding`, and `logo-fatigue` appear as no-reasons for luxury accessories even when the pull factors are strong. This explains why Hermès items with subtle branding pass while Louis Vuitton monogram items do not.

---

## How to keep this file current

When new tag vocabulary is added or definitions are refined, update this file and push to GitHub. The file lives at `giadaarchive/ootd-stories/DEINFLUENCE_SKILLS.md`.

The tag_id_map.json and type_id_map.json files in the same repository contain the Notion page IDs for every tag and type — required by the tagging scripts.
