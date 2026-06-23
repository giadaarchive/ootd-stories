#!/usr/bin/env python3
"""
Collection DB cache — fetches all wardrobe items from Notion and caches locally.

Refreshes automatically if cache is older than CACHE_TTL_HOURS.
Items are indexed by clothing category (extracted from SKU code) for fast filtering.
"""

import os, json, time, requests, threading
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
COLLECTION_DB_ID = "ad079964-9690-43ae-9fa8-5a4f3ca1a9ee"
CACHE_FILE = Path(__file__).parent / "collection_cache.json"
CACHE_TTL_HOURS = 12
DESIGNER_CACHE_FILE = Path(__file__).parent / "designer_cache.json"

_refresh_lock = threading.Lock()
_refresh_in_progress = False

NOTION_H = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# SKU category code → clothing type labels (for matching AI descriptions)
SKU_CAT_LABELS = {
    "TOP": ["top", "t-shirt", "tee", "shirt", "blouse", "tank", "camisole"],
    "SHR": ["shirt", "button-down", "blouse", "top"],
    "KNT": ["knit", "sweater", "jumper", "pullover", "knitwear", "cardigan"],
    "TRS": ["trousers", "pants", "jeans", "slacks", "chinos", "wide-leg"],
    "SKT": ["skirt", "midi skirt", "mini skirt", "maxi skirt"],
    "DRS": ["dress", "gown", "shift", "wrap dress", "midi dress"],
    "OTW": ["jacket", "blazer", "coat", "outerwear", "cardigan", "bomber", "overcoat", "trench"],
    "SHO": ["shoes", "boots", "heels", "loafers", "sneakers", "flats", "mules", "sandals"],
    "BAG": ["bag", "purse", "tote", "clutch", "handbag", "shoulder bag", "crossbody"],
    "SCF": ["scarf", "silk scarf", "neckerchief"],
    "ACC": ["jewelry", "necklace", "earrings", "bracelet", "ring", "belt", "hat", "accessory"],
    "JMP": ["jumpsuit", "playsuit", "romper", "overalls"],
}


def _get_text(rich_text_list):
    return "".join(t.get("plain_text", "") for t in rich_text_list) if rich_text_list else ""


def _get_relation_name(relation_list, prop_key):
    """Return comma-joined names from a relation property (requires separate page fetch)."""
    # We store IDs only in the cache — name resolution done separately if needed
    return [r["id"] for r in relation_list] if relation_list else []


def fetch_all_items():
    """Fetch every item from the Collection DB. Returns list of slim item dicts."""
    items = []
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        r = requests.post(
            f"https://api.notion.com/v1/databases/{COLLECTION_DB_ID}/query",
            headers=NOTION_H,
            json=body,
        )
        r.raise_for_status()
        data = r.json()
        for page in data.get("results", []):
            p = page["properties"]
            name = _get_text(p.get("Second best", {}).get("title", []))
            if not name:
                name = _get_text(p.get("Old Title", {}).get("rich_text", []))
            if not name:
                continue  # skip unnamed items

            sku = _get_text(p.get("SKU", {}).get("rich_text", []))
            sku_parts = sku.split("-")
            sku_brand = sku_parts[0] if sku_parts else ""
            sku_cat = sku_parts[1] if len(sku_parts) >= 2 else ""

            colour = _get_text(p.get("Primary Colour", {}).get("rich_text", []))
            if not colour:
                colour = _get_text(p.get("Colour Detail", {}).get("rich_text", []))
            colour_detail = _get_text(p.get("Colour Detail", {}).get("rich_text", []))

            # Designer: relation — store page IDs; name resolution happens separately
            designer_ids = [r["id"] for r in p.get("Designer", {}).get("relation", [])]

            season = [s["name"] for s in p.get("Season", {}).get("multi_select", [])]
            fits = (p.get("Fits", {}).get("formula") or {}).get("number") or 0

            items.append({
                "id": page["id"],
                "name": name,
                "sku": sku,
                "sku_brand": sku_brand,
                "sku_cat": sku_cat,
                "colour": colour,
                "colour_detail": colour_detail,
                "designer_ids": designer_ids,
                "season": season,
                "fits": fits,
            })

        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
        time.sleep(0.35)  # respect 3 req/sec limit

    return items


def _load_designer_cache() -> dict:
    """Load persisted designer ID → name map."""
    if DESIGNER_CACHE_FILE.exists():
        try:
            return json.loads(DESIGNER_CACHE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_designer_cache(id_to_name: dict):
    DESIGNER_CACHE_FILE.write_text(json.dumps(id_to_name, ensure_ascii=False))


def _resolve_designer_names(items):
    """
    Resolve designer page IDs → names, reusing any already-known mappings.
    Persists the mapping so incremental refreshes only fetch new designers.
    """
    known = _load_designer_cache()
    all_ids = {did for item in items for did in item["designer_ids"]}
    unknown = all_ids - set(known)

    if unknown:
        print(f"  Resolving {len(unknown)} new designer(s) ({len(known)} already cached)...")
        for did in unknown:
            try:
                r = requests.get(f"https://api.notion.com/v1/pages/{did}", headers=NOTION_H, timeout=15)
                r.raise_for_status()
                props = r.json().get("properties", {})
                name_prop = next((v for v in props.values() if v.get("type") == "title"), None)
                if name_prop:
                    known[did] = _get_text(name_prop.get("title", []))
                time.sleep(0.35)
            except Exception:
                pass
        _save_designer_cache(known)

    for item in items:
        item["designer"] = ", ".join(
            known.get(did, "") for did in item["designer_ids"] if known.get(did)
        )


def refresh():
    """Fetch from Notion, resolve designer names, write cache. Returns item list."""
    global _refresh_in_progress
    print("Refreshing collection cache...", flush=True)
    items = fetch_all_items()
    print(f"  Fetched {len(items)} items. Resolving designer names...", flush=True)
    _resolve_designer_names(items)
    cache = {"fetched_at": time.time(), "items": items}
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False))
    print(f"  Cache written: {CACHE_FILE}  ({len(items)} items)", flush=True)
    _refresh_in_progress = False
    return items


def _background_refresh():
    """Run refresh() in a daemon thread — doesn't block callers."""
    global _refresh_in_progress
    with _refresh_lock:
        if _refresh_in_progress:
            return
        _refresh_in_progress = True
    t = threading.Thread(target=refresh, daemon=True, name="cache-refresh")
    t.start()


def load(force_refresh=False):
    """
    Load items from cache.

    - If cache is fresh: return immediately.
    - If cache is stale but exists: return stale data NOW, refresh in background.
    - If no cache: block on first refresh (unavoidable on first run).
    - force_refresh=True: block on refresh regardless.
    """
    if force_refresh:
        return refresh()

    if CACHE_FILE.exists():
        cache = json.loads(CACHE_FILE.read_text())
        items = cache.get("items", [])
        age_hours = (time.time() - cache.get("fetched_at", 0)) / 3600

        if age_hours < CACHE_TTL_HOURS:
            return items  # fresh — return immediately

        # Stale — return now, refresh in background
        print(f"  [cache] stale ({age_hours:.0f}h old) — using cached data, refreshing in background", flush=True)
        _background_refresh()
        return items

    # No cache at all — must block
    return refresh()


def search(query_type: str, query_colour: str, items: list, max_results=40) -> list:
    """
    Filter collection items by clothing type and/or colour.

    query_type: clothing type string (e.g. "blazer", "tote bag")
    query_colour: colour description (e.g. "navy", "camel")
    Returns up to max_results items, scored by relevance.
    """
    query_type_lower = query_type.lower()
    query_colour_lower = query_colour.lower()

    # Find matching SKU category codes for this type
    matching_cats = set()
    for cat, labels in SKU_CAT_LABELS.items():
        if any(label in query_type_lower for label in labels):
            matching_cats.add(cat)
        if any(word in label for word in query_type_lower.split() for label in labels):
            matching_cats.add(cat)

    scored = []
    for item in items:
        score = 0
        name_lower = item["name"].lower()
        colour_lower = (item["colour"] + " " + item["colour_detail"]).lower()

        # Category match
        if item["sku_cat"] in matching_cats:
            score += 3
        # Type keywords in name
        for word in query_type_lower.split():
            if len(word) > 3 and word in name_lower:
                score += 2
        # Colour match
        for word in query_colour_lower.split():
            if len(word) > 3 and word in colour_lower:
                score += 2
            if word in name_lower:
                score += 1

        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda x: -x[0])
    return [item for _, item in scored[:max_results]]


if __name__ == "__main__":
    import sys
    force = "--refresh" in sys.argv
    items = load(force_refresh=force)
    print(f"Loaded {len(items)} items")
    if "--search" in sys.argv:
        idx = sys.argv.index("--search")
        q = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "blazer"
        results = search(q, "", items)
        for r in results[:5]:
            print(f"  {r['sku']} — {r['name']} ({r['colour']})")
