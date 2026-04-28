# Designer IDs — Notion Relation Reference

The Notion ID used to link a collection item to its designer. Required when creating new entries via the API (`"Designer": {"relation": [{"id": "PASTE_ID_HERE"}]}`).

**Designer database:** `18accd15-cda1-80ae-b0ec-e6bd60e4c4ed` *(query to confirm)*

---

## Supported designers

| Designer | Notion Relation ID | SKU Code |
|----------|-------------------|---------|
| Hermès | `2b9ccd15-cda1-80fe-9888-dabde81bb8b1` | `HER` |
| Christian Dior | `33c5aada-5e92-44d7-9dcb-747e770a8acc` | `DIO` |
| Chanel | `10fccd15-cda1-8031-9e26-c0c3b6bb99d3` | `CHA` |
| Salvatore Ferragamo | `2b9ccd15-cda1-80f6-a3ed-edb298b97a02` | `FER` |
| Burberry | `10fccd15-cda1-808f-b12a-d13411d7b58d` | `BUR` |
| Louis Vuitton | `10fccd15-cda1-80b7-bd9f-d0abc8bfd469` | `LV` |

For designers not in this list: look up their page ID by querying the Designer database, then add them here.

```python
# Quick lookup — run from lookbook-stories with .env loaded
import os, requests
from dotenv import load_dotenv; load_dotenv()
H = {"Authorization": f"Bearer {os.environ['NOTION_TOKEN']}", "Notion-Version": "2022-06-28"}
r = requests.post("https://api.notion.com/v1/databases/18accd15cda180aeb0ece6bd60e4c4ed/query", headers=H, json={"page_size": 100})
for p in r.json()["results"]:
    name = p["properties"].get("Name", {}).get("title", [{}])[0].get("plain_text", "")
    sku = p["properties"].get("SKU Code", {}).get("rich_text", [{}])[0].get("plain_text", "")
    print(f"{name:<30} {p['id']}   SKU: {sku}")
```

---

## Category codes

| Category | SKU Code | DB ID |
|----------|---------|-------|
| Tops & Shirts | `TOP` | |
| Bag | `BAG` | |
| Shoes | `SHO` | |
| Outerwear | `OUT` | |
| Dresses | `DRS` | |
| Trousers & Shorts & Skirts | `TRS` | |
| Jewellery & Watches | `JEW` | |
| Scarf, Shawl, Stoles | `SCF` | |
| Eyewear | `EYE` | |
| Jumpsuits & Rompers | `JMP` | |
| Lingerie | `LNG` | |
| Hat & Gloves | `HAT` | |

**Category database ID:** `2eaccd15cda18056a4f6c42c62c33851`

---

## Material codes (examples)

| Material | SKU Code |
|----------|---------|
| Wool | `WOL` |
| Leather | `LEA` |
| Canvas (coated) | `CNV` |
| Silk | `SLK` |
| Cotton | `COT` |
| Cashmere | `CAS` |
| Mixed / unknown | `MIX` |

Material codes live in the Material Category database. Run `setup_codes.py` to view and assign them.

**Material database ID:** `d9f03692734141b7b5fa917cd6b37530`

---

## Creative director timelines

Used by `heritage.py` to orient Claude to the correct era for a piece. Do not paste into Notion — internal context only.

**Hermès:** Martin Margiela 1997–2003 · Christophe Lemaire 2010–14 · Nadège Vanhée-Cybulski 2014–present

**Christian Dior:** Dior 1947–57 · YSL 1957–60 · Marc Bohan 1960–89 · Gianfranco Ferré 1989–96 · John Galliano 1996–2011 · Raf Simons 2012–15 · Maria Grazia Chiuri 2016–present

**Chanel:** Coco Chanel 1910–71 · Karl Lagerfeld 1983–2019 · Virginie Viard 2019–24 · Matthieu Blazy 2025–present

**Salvatore Ferragamo:** Founded 1927 · Vara pump 1978 · Family-run; known for hand-lasted construction

**Burberry:** Thomas Burberry 1856 · Gabardine 1879 · Trench 1914 · Christopher Bailey 2001–18 · Riccardo Tisci 2018–22 · Daniel Lee 2022–present

**Louis Vuitton:** Founded 1854 · Monogram canvas 1896 · Marc Jacobs RTW 1997–2014 · Nicolas Ghesquière 2013–present

---

## Adding a new designer to heritage.py

1. Find the designer's Notion page ID (use the lookup script above)
2. Add to `TARGET_DESIGNERS` in `heritage.py` and `heritage_audit.py`
3. Add a `DESIGNER_ERAS` entry with creative director timeline
4. Add to this file
