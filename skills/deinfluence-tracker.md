# Skill: Deinfluence Tracker

Log an item you considered buying but decided not to. Capture the listing, translate the description, and record your reasons.

**Script:** `deinfluence_collector.py`
**Related reference:** [`DEINFLUENCE_SKILLS.md`](../DEINFLUENCE_SKILLS.md)
**Target DB:** `349ccd15cda18030876add491c9b992c`
**See also:** [`shopping-advisor.md`](./shopping-advisor.md)

---

## When to use

- You found something interesting but decided to pass
- You want to record *why* you didn't buy it, for future reference
- Building a log of your deinfluence decisions to spot patterns

---

## Supported sources

- Yahoo Japan auctions (`auctions.yahoo.co.jp`)
- Mercari Japan (`jp.mercari.com`)
- Fril (`item.fril.jp`)

---

## Process

### Basic — just log the listing

```bash
python3 deinfluence_collector.py <url>
```

### With reason — record why you skipped it

```bash
python3 deinfluence_collector.py <url> --reason "Already have equivalent in wardrobe — LV Neverfull covers this function"
```

---

## What gets created

A page in the Deinfluence Notion database with:
- Item title (translated to English by Claude)
- Images (up to 10)
- Full translated description
- Price
- Source URL
- "Why I didn't buy it" section (if `--reason` provided)

Page icon is set to the first image.

---

## Deinfluence vs. Collection

| Database | What it holds |
|----------|---------------|
| `L's Collection` | Items you own |
| `Deinfluence` | Items you considered but passed on |

The Deinfluence database is a decision journal, not an inventory. It is useful for:
- Noticing recurring temptations (same brand/category appearing repeatedly)
- Confirming you already own the equivalent
- Referencing "why I didn't buy X" when the same item comes up again

---

## Tag vocabulary

The Deinfluence database uses the same "why not" tags as the Collection's "What I'd change" tags. See `DEINFLUENCE_SKILLS.md` for the full list.

---

## Outputs

- New page in Deinfluence database
- Images, description, price, source URL populated
- "Why I didn't buy it" section if reason was provided
