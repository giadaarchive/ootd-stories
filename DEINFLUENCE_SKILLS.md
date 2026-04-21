# Deinfluence Decision Skills

This file is the living knowledge base for Lisa's deinfluence fashion tracker. It documents the decision framework, vocabulary, and reasoning patterns that emerge as entries are added. It is used as context for AI tagging and for recognising trends across purchases considered and rejected.

---

## What this tracker is

A database of items Lisa considered buying but did not. The point is not just to track individual decisions — it is to surface *patterns* in what attracts her and what ultimately stops her. The tags are the training data. The richer and more consistent the vocabulary, the more the database can teach.

---

## The three scripts

| Script | What it does |
|--------|-------------|
| `deinfluence_collector.py <URL>` | Scrapes a shop listing (Mercari, Yahoo Auctions, Rakuma/Fril, PayPay Flea Market), translates to English via Claude, creates a Notion entry with title, images, price, and source URL |
| `deinfluence_tag.py <URL>` | Reads "L's comments and thoughts" from a Notion entry and uses Claude to generate why-yes / why-no multi-select tags |
| `deinfluence_tag.py --all` | Tags every entry in the database that has notes but no tags yet |

To tag a single entry with inline notes (without writing to Notion first):
```
python3 deinfluence_tag.py <notion_url> "your reasoning here"
```

---

## The Notion database

**Database ID:** `349ccd15cda18030876add491c9b992c`
**Parent page:** Deinfluence — What it is not

| Property | Type | Purpose |
|----------|------|---------|
| Item - Third Best | title | English item name |
| URL | url | Source listing link |
| Price | rich_text | Listed price with currency |
| Colour | multi_select | Item's actual colour(s) |
| L's comments and thoughts | rich_text | Lisa's freeform reasoning — this is the input for tagging |
| Why i was considering | multi_select | Pull factors — what made it tempting |
| Why ultimately no | multi_select | Dealbreakers — what stopped the purchase |

---

## Tag vocabulary

### Why I was considering (pull factors)

| Tag | Meaning |
|-----|---------|
| `vintage-provenance` | The item has a documented era, date, or origin story that adds value |
| `investment-piece` | Likely to hold or gain value; justifiable as a long-term buy |
| `natural-patina` | Aged leather, wear, or material character that can't be faked |
| `travel-worthy` | Elevated enough to bring on a trip; not for everyday use |
| `craftsmanship` | Quality of construction, materials, or making that stands out |
| `rare-find` | Hard to source; unlikely to appear again |
| `brand-legacy` | Drawn to the brand's history and heritage as an institution |
| `love-the-designer` | Drawn specifically to the creative director or designer as a person and their vision — not the brand as a commercial entity, but the individual behind it (e.g. Lemaire as designer-owner) |
| `brand-discovery` | Want to learn more about this brand; not yet familiar, this is a gateway piece |
| `versatile` | Works across many contexts in the wardrobe |
| `timeless-silhouette` | The shape or cut is not trend-dependent |

### Why ultimately no (dealbreakers)

#### Logo / branding
| Tag | Meaning |
|-----|---------|
| `visible-logo` | The logo is prominent and unavoidable |
| `loud-branding` | The brand identity is loud in a way that feels performative |
| `logo-fatigue` | General tiredness with recognisable brand signalling |

#### Wardrobe fit
| Tag | Meaning |
|-----|---------|
| `have-equivalent-in-wardrobe` | Already own something functionally and aesthetically equivalent — this would be a direct duplicate |
| `have-better` | Already own something that outperforms this — this would be a downgrade |
| `doesnt-fit-my-wardrobe` | The item has no natural home in the existing wardrobe; nothing to wear it with |
| `doesnt-fit-my-style` | Aesthetically appealing and well-made but not who Lisa is — the item belongs to a different person's story |
| `wrong-fabric-for-use-case` | The material doesn't suit the way she'd actually wear or use it |

#### Item issues
| Tag | Meaning |
|-----|---------|
| `price` | The price is the primary blocker |
| `condition` | The item's physical condition is worse than acceptable |
| `size-wrong` | The sizing doesn't work |
| `wrong-colour` | The colour doesn't work for the wardrobe or doesn't suit |
| `misleading-material-claim` | The listing misrepresented the fabric or material |

#### Design / aesthetic issues
| Tag | Meaning |
|-----|---------|
| `too-common-silhouette` | The shape is generic; nothing distinctive about it |
| `derivative-design` | The design is imitative of something better; lacks its own point of view |

---

## Decision framework: key distinctions

### The three core "no" reasons for wardrobe conflicts

These three are very different and should not be collapsed:

1. **`have-equivalent-in-wardrobe`** — "I already own this." The gap in the wardrobe this would fill is already filled. Buying it would create a duplicate.

2. **`have-better`** — "I own something that beats this." This item would be a lateral or downward move. The money is better spent elsewhere.

3. **`doesnt-fit-my-style`** — "I am drawn to it but it is not who I am." The item is beautiful and well-made, but it belongs to a different aesthetic identity. The attraction is intellectual or aspirational, not personal.

### Brand vs. designer

- **`brand-legacy`** = institutional pull — the house, the heritage, the archive. Could be any designer era.
- **`love-the-designer`** = personal pull — a specific creative person whose vision Lisa wants to support and collect. The brand is almost incidental. Example: Christophe Lemaire, where the designer IS the brand, is the owner, and his aesthetic sensibility is the reason to collect.

### Style vs. wardrobe

- **`doesnt-fit-my-wardrobe`** = practical gap — there is literally nothing to wear it with, no occasion, no context.
- **`doesnt-fit-my-style`** = identity gap — the item is appealing but it's not her. This is about self-knowledge, not logistics.

---

## Emerging patterns (update as data grows)

*Add observations here as the database grows — e.g. "logo is the #1 no reason for luxury accessories" or "Andrew GN appears frequently in the considering column — warrants its own collection strategy."*

- Logo/branding tags (`visible-logo`, `loud-branding`, `logo-fatigue`) are recurring no-reasons for heritage luxury accessories
- `love-the-designer` first applied to Lemaire — track which designers accumulate this tag
- Andrew GN appears frequently as a brand being actively explored

---

## How to keep this file current

When new tag vocabulary is added or definitions are refined, update this file and push to GitHub. The file lives at `giadaarchive/ootd-stories/DEINFLUENCE_SKILLS.md`.
