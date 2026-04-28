# Skill: Run Wardrobe Analytics

Generate a snapshot of collection wear data — cost per wear, unworn items, high-CPW outliers — from the Notion database.

**Script:** `_wardrobe_analytics.py`

---

## When to use

- Periodic review of wardrobe performance
- Before a destash or wardrobe edit — identify items not earning their place
- To answer "what have I not worn recently?" or "what has the worst CPW?"

---

## Process

```bash
python3 _wardrobe_analytics.py
```

The script queries `L's Collection of Amazing Pieces`, skips items marked as in-transit (most recently added), and outputs:
- Wear counts and CPW per item
- Items with zero or very low wear
- Items with high total cost but low wear frequency

---

## Output

Printed to terminal. No Notion writes — read-only script.

---

## Notes

- The script hardcodes `TODAY = date(2026, 4, 23)` — update this date constant before running to get accurate age calculations
- Items in the most-recently-added batch (~18 items) are excluded from analysis as "in transit"
- CPW is calculated from `Total Cost (SGD)` ÷ number of OOTD entries linking to that item
