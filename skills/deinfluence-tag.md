# Skill: Tag a Deinfluence Entry

Apply "Why I was considering" and "Why ultimately no" tags to a Deinfluence database entry, using Claude to read your personal notes and map them to the approved tag vocabulary.

**Script:** `deinfluence_tag.py`
**Related reference:** [`DEINFLUENCE_SKILLS.md`](../DEINFLUENCE_SKILLS.md)
**See also:** [`deinfluence-tracker.md`](./deinfluence-tracker.md)

---

## When to use

- After logging an item with `deinfluence_collector.py` — add tags to explain the decision
- When you've written notes in the `L's comments and thoughts` field and want them converted to structured tags
- Batch-tagging all untagged deinfluence entries

---

## Process

### Tag a single entry

```bash
python3 deinfluence_tag.py <notion_page_url_or_id>
```

Reads the `L's comments and thoughts` field from the page and infers tags.

### Tag with inline notes (skip what's in Notion)

```bash
python3 deinfluence_tag.py <page_id> "I love the patina but the logo is too much for me"
```

### Batch-tag all untagged entries

```bash
python3 deinfluence_tag.py --all
```

Only processes entries that have notes but no tags yet.

---

## Tag vocabulary

### Why I was considering (pull factors)

`vintage-provenance` · `investment-piece` · `natural-patina` · `travel-worthy` · `craftsmanship` · `rare-find` · `brand-legacy` · `versatile` · `timeless-silhouette` · `love-the-designer` · `brand-discovery` · `pattern-integrity` · `colour` · `sentimental` · `gifted`

### Why ultimately no (push factors)

`visible-logo` · `loud-branding` · `logo-fatigue` · `price` · `condition` · `size-wrong` · `wrong-colour` · `wrong-fabric-for-use-case` · `misleading-material-claim` · `too-common-silhouette` · `derivative-design` · `doesnt-fit-my-wardrobe` · `doesnt-fit-my-style` · `have-equivalent-in-wardrobe` · `have-better-in-wardrobe`

**Key distinction:**
- `have-equivalent-in-wardrobe` — already own something doing the same job, would be a duplicate
- `have-better-in-wardrobe` — already own something that outperforms this — would be a downgrade
- `doesnt-fit-my-wardrobe` — no natural home, nothing to pair with (practical gap)

---

## Outputs

- `Why I was considering` multi-select property written to the Notion page
- `Why ultimately no` multi-select property written to the Notion page
