# Skill: Run Heritage Audit

After `heritage.py` has written heritage notes, run the audit to add a **Craft & Materials** section (if missing) and a **Verification & Sources** section with fact-checked claims and reference URLs.

**Script:** `heritage_audit.py`
**Prerequisite:** [`heritage-notes.md`](./heritage-notes.md) must have run first

---

## When to use

- After `heritage.py` has run on an item
- When you want to fact-check the heritage content and add source references
- When an item has heritage notes but no `Craft & Materials` detail (written by an older version of `heritage.py`)

---

## What it adds

| Section | Content |
|---------|---------|
| **Craft & Materials** | Added only if missing. Leather type, tanning method, stitching, thread, hardware, lining, construction approach. |
| **Verification & Sources** | Always added. 5–10 specific claims fact-checked with ✓ Confirmed / ~ Approximate / ? Uncertain, plus a reference URL for each. Also lists 2–3 gaps requiring physical inspection. |

The audit skips any page that already has a `Verification & Sources` section.

---

## Process

### Step 1 — Ensure heritage.py has already run

The audit reads the existing Design Language and This Piece sections. If they are empty, the audit produces weak output.

### Step 2 — Run the audit

```bash
python3 heritage_audit.py
```

This processes all items in `TARGET_DESIGNERS` that have heritage content but no Verification & Sources section.

There is no `--force` flag on `heritage_audit.py`. To re-run an audit on a specific item, manually delete the `Verification & Sources` section from the Notion page first, then re-run.

---

## TARGET_DESIGNERS

Same as `heritage.py`:

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

---

## Outputs

- `Craft & Materials` section (if previously missing)
- `Verification & Sources` section with bullet-point fact-check + source URLs + further research list

---

## Common errors

| Error | Cause | Fix |
|-------|-------|-----|
| `JSON parse error` | Claude returned malformed JSON (long content, cut off) | Re-run — transient API issue |
| Audit produces generic sources | Heritage notes were house-centric, not piece-specific | Re-run `heritage.py --force` first, then re-audit |
| Section missing after run | `max_tokens=1800` hit for complex items | Manually check if JSON was truncated; re-run |
