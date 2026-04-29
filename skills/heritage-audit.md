# Skill: Run Heritage Audit

After `heritage.py` has written the six-layer heritage notes, run the audit to add a **Craft & Materials** section (if missing from older entries) and a **Verification & Sources** section with fact-checked claims and reference URLs.

**Script:** `heritage_audit.py`
**Prerequisite:** `heritage.py` must have run on the item first

---

## When to use

- After `heritage.py` has written heritage notes on a batch of items
- When items have heritage notes but no `Verification & Sources` section
- Runs automatically via daily cron at 2:08 AM and 5:08 AM SGT

---

## What it adds

| Section | Content |
|---|---|
| **Craft & Materials** | Added only if missing (written by old heritage.py format). Leather type, tanning method, stitching, thread, hardware, lining, construction approach. |
| **Verification & Sources** | Always added. 5–10 specific claims fact-checked with ✓ Confirmed / ~ Approximate / ? Uncertain, plus a reference URL for each. Lists 2–3 gaps requiring physical inspection. |

Skips any page that already has a `Verification & Sources` section.

---

## Usage

### Audit the N most recently added items (all brands)

```bash
python3 heritage_audit.py --recent 100
```

Processes the 100 most recently created collection items, regardless of brand. Fetches the brand name from Notion for items not in TARGET_DESIGNERS. Skips items without heritage notes or already audited.

### Audit all TARGET_DESIGNER items (default)

```bash
python3 heritage_audit.py
```

Processes all items from Hermès, Dior, Chanel, Ferragamo, Burberry, Louis Vuitton that have heritage notes but no Verification & Sources section.

---

## TARGET_DESIGNERS (default mode only)

```python
TARGET_DESIGNERS = {
    "Hermès":               "2b9ccd15-cda1-80fe-9888-dabde81bb8b1",
    "Christian Dior":       "33c5aada-5e92-44d7-9dcb-747e770a8acc",
    "Chanel":               "10fccd15-cda1-8031-9e26-c0c3b6bb99d3",
    "Salvatore Ferragamo":  "2b9ccd15-cda1-80f6-a3ed-edb298b97a02",
    "Burberry":             "10fccd15-cda1-808f-b12a-d13411d7b58d",
    "Louis Vuitton":        "10fccd15-cda1-80b7-bd9f-d0abc8bfd469",
}
```

`--recent N` covers all brands, not just these six.

---

## Re-auditing a specific item

No `--force` flag. To re-run the audit on a specific item: manually delete the `Verification & Sources` section from the Notion page, then re-run.

---

## Common errors

| Error | Cause | Fix |
|---|---|---|
| `JSON parse error` | Claude returned malformed JSON | Re-run — transient API issue |
| Audit produces generic sources | Heritage notes were house-generic, not piece-specific | Re-run `heritage.py --force <page_id>` first, then re-audit |
| Section missing after run | `max_tokens=1800` hit for complex items | Re-run — check for truncated JSON |
