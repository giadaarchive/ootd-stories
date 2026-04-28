# Skill: Set Up Category and Material SKU Codes

Assign 3-letter SKU codes to every entry in the Category and Material Category databases. Required before `generate_skus.py` can produce complete SKUs.

**Script:** `setup_codes.py`
**Run before:** `generate_skus.py`

---

## When to use

- First-time setup
- After a new category or material is added to the Notion databases
- If SKUs are generating with `OTH` or `MIX` placeholders instead of real codes

---

## Process

```bash
python3 setup_codes.py
```

The script:
1. Queries the Category database — shows current names and any existing codes
2. Suggests 3-letter codes (e.g. `TOP` for Tops & Shirts, `BAG` for Bag)
3. Asks for confirmation or lets you edit before writing
4. Repeats for the Material Category database

---

## Category codes (current)

| Category | Code |
|----------|------|
| Tops & Shirts | `TOP` |
| Bag | `BAG` |
| Shoes | `SHO` |
| Outerwear | `OUT` |
| Dresses | `DRS` |
| Trousers & Shorts & Skirts | `TRS` |
| Jewellery & Watches | `JEW` |
| Scarf, Shawl, Stoles | `SCF` |
| Eyewear | `EYE` |
| Jumpsuits & Rompers | `JMP` |
| Lingerie | `LNG` |
| Hat & Gloves | `HAT` |

---

## Database IDs (hardcoded in script)

| Database | ID |
|----------|----|
| Category | `2eaccd15cda18056a4f6c42c62c33851` |
| Material Category | `d9f03692734141b7b5fa917cd6b37530` |

---

## After running

Run `generate_skus.py` to assign SKUs to collection items using the newly written codes.

---

## Outputs

- `SKU Code` property written to all Category database entries
- `SKU Code` property written to all Material Category database entries
