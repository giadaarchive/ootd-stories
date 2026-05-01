"""
Taxonomy mapper: converts tag-walk tag vocabulary → our taxonomy categories.

Strategy:
  Phase 1 (now): Use tag-walk's tags as the primary vocabulary.
                 Map their tag categories to our top-level categories.
                 Store the raw tag-walk label in `description`, our category in `category`.

  Phase 2 (Asian brands): Extend mapping with Japanese/Chinese/Korean vocabulary.
                 Use LLM to map unknown terms to our taxonomy.

Tag-walk tag categories (observed from their UI):
  Couleur / Colour     → COLOUR / PALETTE or SIGNATURE_COLOUR
  Silhouette           → SILHOUETTE / GARMENT_SILHOUETTE or VOLUME_PLACEMENT
  Matière / Fabric     → MATERIAL_FABRIC / TEXTILE_TECHNIQUE or SIGNATURE_MATERIAL
  Imprimé / Print      → MOTIF_PRINT / (subcategory by type)
  Longueur / Length    → SILHOUETTE / HEM
  Col / Collar         → HARDWARE_DETAIL / CLOSURE_TYPE (or SILHOUETTE / SHOULDER)
  Manches / Sleeves    → SILHOUETTE / GARMENT_SILHOUETTE
  Accessoires          → HARDWARE_DETAIL / SIGNATURE_HARDWARE
  Thème / Theme        → NARRATIVE_THEME / SEASONAL_CONCEPT
  Style                → NARRATIVE_THEME / EMOTIONAL_TERRITORY
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import llm as llm_module

_DIR = os.path.dirname(os.path.abspath(__file__))
TAXONOMY_PATH  = os.path.join(_DIR, "taxonomy.json")
CONFIG_PATH    = os.path.join(_DIR, "models_config.json")

# Static mapping: tag-walk category keyword → (our category, our subcategory)
# Used for fast, deterministic mapping without LLM
STATIC_MAP = {
    # Colour
    "couleur":        ("COLOUR", "PALETTE"),
    "color":          ("COLOUR", "PALETTE"),
    "colour":         ("COLOUR", "PALETTE"),

    # Silhouette / Shape
    "silhouette":     ("SILHOUETTE", "GARMENT_SILHOUETTE"),
    "shape":          ("SILHOUETTE", "GARMENT_SILHOUETTE"),
    "forme":          ("SILHOUETTE", "GARMENT_SILHOUETTE"),
    "longueur":       ("SILHOUETTE", "HEM"),
    "length":         ("SILHOUETTE", "HEM"),
    "volume":         ("SILHOUETTE", "VOLUME_PLACEMENT"),
    "épaule":         ("SILHOUETTE", "SHOULDER_CONSTRUCTION"),
    "shoulder":       ("SILHOUETTE", "SHOULDER_CONSTRUCTION"),
    "waist":          ("SILHOUETTE", "WAIST_DEFINITION"),
    "taille":         ("SILHOUETTE", "WAIST_DEFINITION"),

    # Material / Fabric
    "matière":        ("MATERIAL_FABRIC", "TEXTILE_TECHNIQUE"),
    "fabric":         ("MATERIAL_FABRIC", "TEXTILE_TECHNIQUE"),
    "material":       ("MATERIAL_FABRIC", "TEXTILE_TECHNIQUE"),
    "tissu":          ("MATERIAL_FABRIC", "TEXTILE_TECHNIQUE"),
    "textile":        ("MATERIAL_FABRIC", "TEXTILE_TECHNIQUE"),
    "leather":        ("MATERIAL_FABRIC", "SIGNATURE_MATERIAL"),
    "cuir":           ("MATERIAL_FABRIC", "SIGNATURE_MATERIAL"),

    # Print / Pattern
    "imprimé":        ("MOTIF_PRINT", "ABSTRACT_PRINT"),
    "print":          ("MOTIF_PRINT", "ABSTRACT_PRINT"),
    "motif":          ("MOTIF_PRINT", "SYMBOLIC_MOTIF"),
    "pattern":        ("MOTIF_PRINT", "GEOMETRIC_PATTERN"),
    "floral":         ("MOTIF_PRINT", "FIGURATIVE_PRINT"),
    "graphique":      ("MOTIF_PRINT", "GEOMETRIC_PATTERN"),
    "graphic":        ("MOTIF_PRINT", "GEOMETRIC_PATTERN"),
    "abstract":       ("MOTIF_PRINT", "ABSTRACT_PRINT"),
    "abstrait":       ("MOTIF_PRINT", "ABSTRACT_PRINT"),
    "animal":         ("MOTIF_PRINT", "FIGURATIVE_PRINT"),

    # Hardware / Detail
    "col":            ("HARDWARE_DETAIL", "CLOSURE_TYPE"),
    "collar":         ("HARDWARE_DETAIL", "CLOSURE_TYPE"),
    "fermeture":      ("HARDWARE_DETAIL", "CLOSURE_TYPE"),
    "closure":        ("HARDWARE_DETAIL", "CLOSURE_TYPE"),
    "accessoire":     ("HARDWARE_DETAIL", "SIGNATURE_HARDWARE"),
    "accessory":      ("HARDWARE_DETAIL", "SIGNATURE_HARDWARE"),
    "hardware":       ("HARDWARE_DETAIL", "SIGNATURE_HARDWARE"),
    "finition":       ("HARDWARE_DETAIL", "INTERIOR_DETAIL"),
    "finish":         ("HARDWARE_DETAIL", "INTERIOR_DETAIL"),

    # Cultural / Theme
    "thème":          ("NARRATIVE_THEME", "SEASONAL_CONCEPT"),
    "theme":          ("NARRATIVE_THEME", "SEASONAL_CONCEPT"),
    "style":          ("NARRATIVE_THEME", "EMOTIONAL_TERRITORY"),
    "inspiration":    ("CULTURAL_REFERENCE", "ART_MOVEMENT"),
    "référence":      ("CULTURAL_REFERENCE", "HISTORICAL_PERIOD"),
    "reference":      ("CULTURAL_REFERENCE", "HISTORICAL_PERIOD"),

    # Show / Experiential
    "lieu":           ("SENSORY_EXPERIENTIAL", "SHOW_ENVIRONMENT"),
    "venue":          ("SENSORY_EXPERIENTIAL", "SHOW_ENVIRONMENT"),
    "musique":        ("SENSORY_EXPERIENTIAL", "SOUND_MUSIC"),
    "music":          ("SENSORY_EXPERIENTIAL", "SOUND_MUSIC"),
}


def map_tagwalk_tag(tag_label, tag_category_hint=None):
    """
    Map a single tag-walk tag to our taxonomy.
    Returns (category, subcategory) or (None, None) if no match.

    tag_label        — e.g. "Cobalt Blue", "Straight Silhouette", "Floral Print"
    tag_category_hint — e.g. "colour", "silhouette" (from tag-walk's own grouping)
    """
    if tag_category_hint:
        hint_lower = tag_category_hint.lower().strip()
        for key, (cat, sub) in STATIC_MAP.items():
            if key in hint_lower:
                return cat, sub

    # Try to match the tag label itself
    label_lower = tag_label.lower().strip()
    for key, (cat, sub) in STATIC_MAP.items():
        if key in label_lower:
            return cat, sub

    return None, None


def map_tagwalk_tags_to_instances(tags_dict, brand_id, season_id, source="tagwalk"):
    """
    Convert tag-walk aggregated tags dict {tag_label: count} to instance dicts.
    Returns list of partial instance dicts (no checker_status — caller adds that).

    Tags with count ≥ 3 = Hero, count ≥ 2 = Supporting, else Referenced.
    """
    instances = []
    for tag_label, count in tags_dict.items():
        cat, sub = map_tagwalk_tag(tag_label)
        if not cat:
            continue   # unmapped tag — skip for now

        prominence = "Hero" if count >= 3 else ("Supporting" if count >= 2 else "Referenced")
        instances.append({
            "season_id":       season_id,
            "brand_id":        brand_id,
            "category":        cat,
            "subcategory":     sub,
            "description":     tag_label,
            "prominence":      prominence,
            "new_or_recurring": "Unknown",
            "evolution_note":  None,
            "evidence":        f"tag-walk tag: '{tag_label}' (appears {count}× across looks)",
            "source":          source,
        })
    return instances


def llm_map_unknown_tags(unknown_tags, brand, season_label, task="text_extraction"):
    """
    Use LLM to map tags that don't match the static map.
    Useful for Asian-language tags or highly specific technical terms.
    Returns list of (tag_label, category, subcategory) tuples.
    """
    with open(TAXONOMY_PATH) as f:
        tax = json.load(f)
    with open(CONFIG_PATH) as f:
        model = json.load(f)["tasks"][task]["model"]

    tax_ref = "\n".join(
        f"CATEGORY: {cat}\n" + "\n".join(
            f"  SUBCATEGORY: {sub}" for sub in cat_data["subcategories"]
        )
        for cat, cat_data in tax["categories"].items()
    )

    system = (
        "Map each fashion tag to the correct CATEGORY and SUBCATEGORY from the taxonomy.\n"
        "If the tag is in a non-English language, first translate it, then map it.\n"
        "Return a JSON array: [{\"tag\": \"...\", \"category\": \"...\", \"subcategory\": \"...\"}]\n"
        "If a tag cannot be mapped, set category and subcategory to null.\n"
        "Return only valid JSON. No markdown."
    )
    user = (
        f"Brand: {brand}\nSeason: {season_label}\n\n"
        f"TAXONOMY:\n{tax_ref}\n\n"
        f"TAGS TO MAP:\n" + "\n".join(f"- {t}" for t in unknown_tags)
    )

    raw = llm_module.call(system, user, max_tokens=2000, model=model)
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
