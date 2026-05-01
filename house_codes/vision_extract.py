"""
Vision extraction — extract house codes from look images using Qwen2.5-VL.

Batches images (max BATCH_SIZE per call) to stay within context limits.
Evidence is always "Visual observation: ..." — never a text quote.
Checker Pass 2 (text evidence check) is skipped for vision codes;
Pass 1 taxonomy check still runs.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import llm as llm_module
import cache as cache_mod

_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH   = os.path.join(_DIR, "models_config.json")
TAXONOMY_PATH = os.path.join(_DIR, "taxonomy.json")

BATCH_SIZE = 8  # images per LLM call — keeps token count manageable


def _get_model():
    with open(CONFIG_PATH) as f:
        return json.load(f)["tasks"]["vision_analysis"]["model"]


def _taxonomy_ref():
    with open(TAXONOMY_PATH) as f:
        tax = json.load(f)
    lines = []
    for cat, cat_data in tax["categories"].items():
        lines.append(f"CATEGORY: {cat}")
        for sub, sub_data in cat_data["subcategories"].items():
            lines.append(f"  SUBCATEGORY: {sub}  — {sub_data['label']}")
    return "\n".join(lines)


VISION_SYSTEM = """\
You are a fashion house code analyst. Analyse runway/lookbook images and extract structured house codes.

You are looking at look images — extract what is VISUALLY PRESENT, not inferred from text.

WHAT YOU CAN EXTRACT FROM IMAGES:
  COLOUR — palette, signature colours, colour pairings
  SILHOUETTE — garment shape, hem, shoulder, volume, waist definition
  MATERIAL_FABRIC — visible fabric type, texture, surface treatments
  MOTIF_PRINT — visible prints, patterns, embroidery, embellishment
  HARDWARE_DETAIL — visible buttons, zippers, clasps, signatures, trim
  SENSORY_EXPERIENTIAL — show environment if visible in images

DO NOT extract from images alone:
  NARRATIVE_THEME — seasonal concept, emotional territory (needs editorial text)
  CULTURAL_REFERENCE — art movements, historical periods (needs text)
  CUSTOMER_ARCHETYPE_HOUSE — explicitly stated customer (needs text)

RULES:
1. category and subcategory MUST exactly match the ALLOWED TAXONOMY values.
2. evidence MUST start with "Visual observation: " and describe what is literally seen.
3. prominence: "Hero" (dominant across 3+ looks), "Supporting", or "Referenced".
4. If a code appears across multiple looks, note it once with the strongest prominence.
5. Do not repeat the same category/subcategory pair unless it represents a genuinely different code.

Return a JSON array of objects with exactly these keys:
  category, subcategory, description, prominence, new_or_recurring, evolution_note, evidence

Return only valid JSON. No markdown fencing. No preamble.\
"""


def extract(image_urls, brand, season_label, source="vision"):
    """
    Extract house codes from a list of look image URLs.
    Batches calls if > BATCH_SIZE images. Merges and deduplicates results.
    Returns list of code dicts (no checker_status — caller adds that).
    """
    if not image_urls:
        return []

    model   = _get_model()
    tax_ref = _taxonomy_ref()

    all_codes = []
    batches   = [image_urls[i:i+BATCH_SIZE] for i in range(0, len(image_urls), BATCH_SIZE)]

    for batch_idx, batch in enumerate(batches):
        cache_key = cache_mod.llm_key(model, VISION_SYSTEM, f"{brand}|{season_label}|{batch_idx}|{'|'.join(batch)}")
        cached = cache_mod.get("llm", cache_key)
        if cached:
            print(f"     [cache hit] vision batch {batch_idx+1}/{len(batches)}")
            all_codes.extend(cached)
            continue

        user_msg = (
            f"Brand: {brand}\n"
            f"Season: {season_label}\n"
            f"Source: {source}\n"
            f"Images in this batch: {len(batch)} of {len(image_urls)} total looks\n\n"
            f"ALLOWED TAXONOMY:\n{tax_ref}"
        )

        print(f"     Analysing {len(batch)} images (batch {batch_idx+1}/{len(batches)})...")
        raw = llm_module.call_vision(VISION_SYSTEM, user_msg, batch, max_tokens=3000, model=model)
        codes = _parse(raw)

        cache_mod.set("llm", cache_key, codes, ttl_days=14)
        all_codes.extend(codes)

    return _deduplicate(all_codes)


def _deduplicate(codes):
    """Keep highest-prominence instance per (category, subcategory) pair."""
    prominence_rank = {"Hero": 0, "Supporting": 1, "Referenced": 2}
    seen = {}
    for code in codes:
        key = (code.get("category", ""), code.get("subcategory", ""))
        rank = prominence_rank.get(code.get("prominence", "Referenced"), 2)
        if key not in seen or rank < prominence_rank.get(seen[key].get("prominence", "Referenced"), 2):
            seen[key] = code
    return list(seen.values())


def _parse(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []
