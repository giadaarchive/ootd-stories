# Skills Index — ootd-stories

One task, one file. Every skill links to the script that executes it and the README that explains the why.

**Repo:** `giadaarchive/ootd-stories`
**Scripts live in:** repo root (`.py` files)
**Reference docs live in:** repo root (`*_SKILLS.md` files)

---

## Collection Management

| Skill | Script | Trigger |
|-------|--------|---------|
| [Add item from online purchase](./add-collection-item.md) | write inline script | You bought something |
| [Re-host expired images](./rehost-images.md) | write inline script | Images not loading in Notion |
| [Fix a wrong entry](./fix-wrong-entry.md) | write inline script | Wrong item scraped |
| [Set up category/material codes](./setup-codes.md) | `setup_codes.py` | New category or material added |
| [Generate SKUs](./generate-skus.md) | `generate_skus.py` | New items added without SKUs |
| [Batch-tag Why I Own It](./batch-tags.md) | `batch_tag_why_i_own_it.py` | Items missing ownership tags |
| [Run wardrobe analytics](./wardrobe-analytics.md) | `_wardrobe_analytics.py` | Periodic wear/CPW review |

## Heritage & Documentation

| Skill | Script | Trigger |
|-------|--------|---------|
| [Write heritage notes](./heritage-notes.md) | `heritage.py` | New item added to collection |
| [Run heritage audit](./heritage-audit.md) | `heritage_audit.py` | After heritage.py has run |
| [Write brand heritage](./brand-heritage.md) | `brand_heritage.py` | New brand added, or brand page missing house history |
| [Archive from YouTube video](./wardrobe-archive.md) | `wardrobe_archive.py` | Video recorded about a piece |

## OOTD & Publishing

| Skill | Script | Trigger |
|-------|--------|---------|
| [Generate OOTD stories](./ootd-stories.md) | `lookbook.py` | New outfit photos added to Notion |
| [Schedule to Substack](./schedule-substack.md) | `substack.py` | OOTD story ready to publish |
| [Re-authenticate Substack session](./substack-login.md) | `setup_cookies.py` | `substack.py` fails with auth error |

## Purchase Research

| Skill | Script | Trigger |
|-------|--------|---------|
| [Shopping advisor — buy or skip](./shopping-advisor.md) | `shopping_advisor.py` | Considering a purchase |
| [Deinfluence tracker](./deinfluence-tracker.md) | `deinfluence_collector.py` | Log items you decided not to buy |
| [Tag a deinfluence entry](./deinfluence-tag.md) | `deinfluence_tag.py` | Apply why-yes/why-no tags to a logged item |

---

## Reference docs (database-level)

Read these before writing any script that touches Notion. They contain the exact property keys, IDs, and types needed — no API exploration required.

- [`NOTION_SCHEMA.md`](../NOTION_SCHEMA.md) — **API property names, types, database IDs for all databases** (read this first)
- [`DESIGNER_IDS.md`](../DESIGNER_IDS.md) — **Designer relation IDs + SKU codes + creative director timelines**
- [`COLLECTION_SKILLS.md`](../COLLECTION_SKILLS.md) — L's Collection of Amazing Pieces DB (narrative reference)
- [`OOTD_SKILLS.md`](../OOTD_SKILLS.md) — Lookbook / OOTD DB
- [`DEINFLUENCE_SKILLS.md`](../DEINFLUENCE_SKILLS.md) — Deinfluence tracker DB + tag vocabulary
- [`SHOPPING_SKILLS.md`](../SHOPPING_SKILLS.md) — Shopping advisor usage
- [`AUTHENTICATION_SKILLS.md`](../AUTHENTICATION_SKILLS.md) — Authenticating vintage and luxury pieces
- [`GEOGRAPHIC_SOURCING_SKILLS.md`](../GEOGRAPHIC_SOURCING_SKILLS.md) — Sourcing by geography
- [`LAUNDRY_SKILLS.md`](../LAUNDRY_SKILLS.md) — Garment care reference

---

## Mistakes & corrections

- [`../MISTAKES.md`](../MISTAKES.md) — What went wrong and how to fix it

## Setup

- [`../SETUP.md`](../SETUP.md) — First-time environment setup

## Gaps & improvements

- [`../GAPS.md`](../GAPS.md) — What's missing in the workflow documentation and what to build next
