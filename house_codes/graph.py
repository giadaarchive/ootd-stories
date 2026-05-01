"""
JSON-based graph storage for the house code knowledge graph.

Nodes: brands, creative_directors, seasons, house_codes
Edges: instances (season → code), trend_signals (cross-brand)

Indexed for two query axes:
  Vertical   — brand_id → seasons → instances
  Horizontal — season_label (e.g. AW2026) → brands → instances

Index is built in-memory on first query per session — no schema change, no extra files.
"""
import json
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

_FILES = {
    "brands":             "brands.json",
    "creative_directors": "creative_directors.json",
    "seasons":            "seasons.json",
    "house_codes":        "house_codes.json",
    "instances":          "instances.json",
    "trend_signals":      "trend_signals.json",
}

# In-memory index cache — rebuilt on first use, cleared on any write
_idx_cache = {}


def _path(key):
    return os.path.join(DATA_DIR, _FILES[key])


def _load(key):
    p = _path(key)
    if not os.path.exists(p):
        return [] if key in ("instances", "trend_signals") else {}
    with open(p) as f:
        return json.load(f)


def _save(key, data):
    _idx_cache.clear()          # invalidate index on any write
    with open(_path(key), "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _now():
    return datetime.utcnow().isoformat() + "Z"


# ── Index ─────────────────────────────────────────────────────────────────────

def _build_index():
    """Build in-memory index on instances for fast queries."""
    if "built" in _idx_cache:
        return
    instances = _load("instances")
    seasons   = _load("seasons")

    # brand_id → [instance, ...]
    by_brand = {}
    # season_label → [instance, ...]
    by_period = {}
    # season_id → [instance, ...]
    by_season_id = {}
    # (category, subcategory) → [instance, ...]
    by_code = {}

    for inst in instances:
        bid = inst["brand_id"]
        sid = inst["season_id"]
        cat = inst["category"]
        sub = inst["subcategory"]

        by_brand.setdefault(bid, []).append(inst)
        by_season_id.setdefault(sid, []).append(inst)
        by_code.setdefault((cat, sub), []).append(inst)
        by_code.setdefault((cat, None), []).append(inst)

        season = seasons.get(sid, {})
        label  = season.get("season_label")
        if label:
            by_period.setdefault(label, []).append(inst)

    _idx_cache.update({
        "built": True,
        "by_brand":     by_brand,
        "by_period":    by_period,
        "by_season_id": by_season_id,
        "by_code":      by_code,
    })


# ── Brands ────────────────────────────────────────────────────────────────────

def add_brand(brand_id, name, founded_year=None, founding_country=None, founding_category=None):
    brands = _load("brands")
    if brand_id not in brands:
        brands[brand_id] = {
            "id": brand_id,
            "name": name,
            "founded_year": founded_year,
            "founding_country": founding_country,
            "founding_category": founding_category,
            "added_at": _now(),
        }
        _save("brands", brands)
    return brand_id


# ── Creative Directors ────────────────────────────────────────────────────────

def add_creative_director(cd_id, name, brand_id, tenure_start=None, tenure_end=None):
    cds = _load("creative_directors")
    cds[cd_id] = {
        "id": cd_id, "name": name, "brand_id": brand_id,
        "tenure_start": tenure_start, "tenure_end": tenure_end,
    }
    _save("creative_directors", cds)
    return cd_id


# ── Seasons ───────────────────────────────────────────────────────────────────

def add_season(season_id, brand_id, year, period, creative_director_name,
               show_date=None, show_location=None, collection_title=None,
               source_urls=None, num_looks=None, look_image_urls=None,
               season_month_range=None):
    seasons = _load("seasons")
    if season_id in seasons:
        # Merge new source URLs into existing season
        existing_urls = seasons[season_id].get("source_urls", [])
        for u in (source_urls or []):
            if u and u not in existing_urls:
                existing_urls.append(u)
        seasons[season_id]["source_urls"] = existing_urls
    else:
        # Derive calendar month range from period
        # When clothes are WORN, not when collection is released
        _month_map = {
            "SS": [3,4,5,6,7,8], "AW": [9,10,11,12,1,2], "FW": [9,10,11,12,1,2],
            "RESORT": [4,5,6,7], "COUTURE": [1,6],  "PF": [7,8,9],
        }
        months = season_month_range or _month_map.get(period, [])
        seasons[season_id] = {
            "id": season_id,
            "brand_id": brand_id,
            "year": year,
            "period": period,
            "season_label": f"{period}{year}",
            "creative_director": creative_director_name,
            "show_date": show_date,
            "show_location": show_location,
            "collection_title": collection_title,
            "source_urls": [u for u in (source_urls or []) if u],
            "num_looks": num_looks,
            "look_image_urls": look_image_urls or [],   # Phase 2: Qwen-VL vision pipeline
            "season_month_range": months,               # Jan=1 … Dec=12
            "added_at": _now(),
        }
    _save("seasons", seasons)
    return season_id


# ── House Codes (canonical, brand-level) ──────────────────────────────────────

def upsert_house_code(code_id, brand_id, code_name, category, subcategory,
                      origin_story=None, first_appeared_season_id=None):
    codes = _load("house_codes")
    codes[code_id] = {
        "id": code_id, "brand_id": brand_id, "code_name": code_name,
        "category": category, "subcategory": subcategory,
        "origin_story": origin_story, "first_appeared_season_id": first_appeared_season_id,
    }
    _save("house_codes", codes)
    return code_id


# ── Season Code Instances (edges) ─────────────────────────────────────────────

def instance_exists(season_id, category, subcategory, evidence):
    """
    True if an instance with the same season+category+subcategory+evidence already exists.
    Prevents duplicates when re-running the same source URL.
    """
    instances = _load("instances")
    ev_clean = (evidence or "").strip().lower()
    for inst in instances:
        if (inst["season_id"] == season_id
                and inst["category"] == category
                and inst["subcategory"] == subcategory
                and (inst.get("evidence") or "").strip().lower() == ev_clean):
            return True
    return False


def add_instance(season_id, brand_id, category, subcategory, description,
                 prominence, new_or_recurring, evolution_note=None,
                 cross_brand_signal=None, evidence=None,
                 checker_status="pending", checker_flags=None,
                 source=None):
    """
    Add a code instance. Returns (instance_id, 'added'|'duplicate').
    Skips if an identical evidence+code already exists for this season.
    """
    if instance_exists(season_id, category, subcategory, evidence):
        return None, "duplicate"

    instances = _load("instances")
    instance_id = (
        f"{season_id}__{category.lower()}__{subcategory.lower()}__{len(instances):04d}"
    )
    instances.append({
        "id":                instance_id,
        "season_id":         season_id,
        "brand_id":          brand_id,
        "category":          category,
        "subcategory":       subcategory,
        "description":       description,
        "prominence":        prominence,
        "new_or_recurring":  new_or_recurring,
        "evolution_note":    evolution_note,
        "cross_brand_signal": cross_brand_signal,
        "evidence":          evidence,
        "checker_status":    checker_status,
        "checker_flags":     checker_flags or [],
        "source":            source,
        "added_at":          _now(),
    })
    _save("instances", instances)
    return instance_id, "added"


# ── Queries ───────────────────────────────────────────────────────────────────

def query_brand_timeline(brand_id):
    """Vertical: all seasons for brand, instances per season, chronological."""
    _build_index()
    seasons = _load("seasons")

    brand_season_ids = {
        sid for sid, s in seasons.items() if s["brand_id"] == brand_id
    }

    def sort_key(sid):
        s = seasons[sid]
        p_order = {"SS": 0, "AW": 1, "FW": 1, "RESORT": 2, "COUTURE": 3, "PF": 4}
        return (s["year"], p_order.get(s["period"], 9))

    result = {}
    by_sid = _idx_cache.get("by_season_id", {})
    for sid in sorted(brand_season_ids, key=sort_key):
        s = seasons[sid]
        result[s["season_label"]] = {
            "season":    s,
            "instances": by_sid.get(sid, []),
        }
    return result


def query_period_cross_section(period_label):
    """Horizontal: all brands in a given period, grouped by brand."""
    _build_index()
    seasons = _load("seasons")
    brands  = _load("brands")

    period_label = period_label.upper()
    by_period = _idx_cache.get("by_period", {})
    instances = by_period.get(period_label, [])

    result = {}
    for inst in instances:
        bid = inst["brand_id"]
        if bid not in result:
            result[bid] = {
                "brand":     brands.get(bid, {"name": bid}),
                "instances": [],
            }
        result[bid]["instances"].append(inst)
    return result


def query_code_across_brands(category, subcategory=None, period_label=None):
    """Diagonal: which brands show a specific code, optionally filtered by period."""
    _build_index()
    seasons  = _load("seasons")
    brands   = _load("brands")
    by_code  = _idx_cache.get("by_code", {})

    key      = (category.upper(), subcategory.upper() if subcategory else None)
    instances = by_code.get(key, [])

    if period_label:
        period_label = period_label.upper()
        period_sids  = {sid for sid, s in seasons.items() if s["season_label"] == period_label}
        instances    = [i for i in instances if i["season_id"] in period_sids]

    result = []
    for inst in instances:
        season = seasons.get(inst["season_id"], {})
        result.append({
            "brand":              brands.get(inst["brand_id"], {}).get("name", inst["brand_id"]),
            "brand_id":           inst["brand_id"],
            "season_label":       season.get("season_label"),
            "creative_director":  season.get("creative_director"),
            "description":        inst["description"],
            "prominence":         inst["prominence"],
            "evidence":           inst["evidence"],
            "checker_status":     inst.get("checker_status"),
        })
    return result


def summary():
    return {
        "brands":        len(_load("brands")),
        "seasons":       len(_load("seasons")),
        "instances":     len(_load("instances")),
        "trend_signals": len(_load("trend_signals")),
    }
