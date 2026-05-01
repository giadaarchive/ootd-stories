"""
Reactive query engine — answers fashion questions by fetching data on demand.

Flow per query:
  1. Interpret question  → {categories, season_label, gender, brands_hint}
  2. For each brand in coverage, fetch season from tag-walk if not in graph
  3. Query graph for relevant codes
  4. Synthesize a human-facing answer via LLM

Data is built on demand and cached — first query for a season is slow,
repeat queries are instant.
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(_HERE, "..", ".env"))

import graph
import fetch_show
import vision_extract
import checker as chk
import llm as llm_module
import cache as cache_mod

_DIR = _HERE
CONFIG_PATH   = os.path.join(_DIR, "models_config.json")
TAXONOMY_PATH = os.path.join(_DIR, "taxonomy.json")


# ── Brand coverage registry ───────────────────────────────────────────────────
# tagwalk_slug: the slug used in tag-walk URLs (None = no tag-walk coverage)
# city: the fashion week city (for tag-walk URL)
# brand_site_url: optional callable(period, year) → url for editorial text

BRAND_COVERAGE = {
    "women": [
        # Paris
        {"brand_id": "akris",           "name": "Akris",               "tagwalk_slug": "akris",               "city": "paris"},
        {"brand_id": "chanel",          "name": "Chanel",              "tagwalk_slug": "chanel",              "city": "paris"},
        {"brand_id": "dior",            "name": "Christian Dior",      "tagwalk_slug": "christian-dior",      "city": "paris"},
        {"brand_id": "hermes",          "name": "Hermès",              "tagwalk_slug": "hermes",              "city": "paris"},
        {"brand_id": "lv",              "name": "Louis Vuitton",       "tagwalk_slug": "louis-vuitton",       "city": "paris"},
        {"brand_id": "balenciaga",      "name": "Balenciaga",          "tagwalk_slug": "balenciaga",          "city": "paris"},
        {"brand_id": "saintlaurent",    "name": "Saint Laurent",       "tagwalk_slug": "saint-laurent",       "city": "paris"},
        {"brand_id": "celine",          "name": "Celine",              "tagwalk_slug": "celine",              "city": "paris"},
        {"brand_id": "givenchy",        "name": "Givenchy",            "tagwalk_slug": "givenchy",            "city": "paris"},
        {"brand_id": "valentino",       "name": "Valentino",           "tagwalk_slug": "valentino",           "city": "paris"},
        {"brand_id": "loewe",           "name": "Loewe",               "tagwalk_slug": "loewe",               "city": "paris"},
        {"brand_id": "miumiu",          "name": "Miu Miu",             "tagwalk_slug": "miu-miu",             "city": "paris"},
        {"brand_id": "isabelmarant",    "name": "Isabel Marant",       "tagwalk_slug": "isabel-marant",       "city": "paris"},
        {"brand_id": "acnestudios",     "name": "Acne Studios",        "tagwalk_slug": "acne-studios",        "city": "paris"},
        {"brand_id": "stellamccartney", "name": "Stella McCartney",    "tagwalk_slug": "stella-mccartney",    "city": "paris"},
        {"brand_id": "toteme",          "name": "Toteme",              "tagwalk_slug": "toteme",              "city": "paris"},
        {"brand_id": "zimmermann",      "name": "Zimmermann",          "tagwalk_slug": "zimmermann",          "city": "paris"},
        # Milan
        {"brand_id": "prada",           "name": "Prada",               "tagwalk_slug": "prada",               "city": "milan"},
        {"brand_id": "bottegaveneta",   "name": "Bottega Veneta",      "tagwalk_slug": "bottega-veneta",      "city": "milan"},
        {"brand_id": "gucci",           "name": "Gucci",               "tagwalk_slug": "gucci",               "city": "milan"},
        {"brand_id": "ferragamo",       "name": "Salvatore Ferragamo", "tagwalk_slug": "salvatore-ferragamo", "city": "milan"},
        {"brand_id": "maxmara",         "name": "Max Mara",            "tagwalk_slug": "max-mara",            "city": "milan"},
        {"brand_id": "brunellocucinelli","name": "Brunello Cucinelli", "tagwalk_slug": "brunello-cucinelli",  "city": "milan"},
        {"brand_id": "marni",           "name": "Marni",               "tagwalk_slug": "marni",               "city": "milan"},
        {"brand_id": "jilsander",       "name": "Jil Sander",          "tagwalk_slug": "jil-sander",          "city": "milan"},
        {"brand_id": "versace",         "name": "Versace",             "tagwalk_slug": "versace",             "city": "milan"},
        # London
        {"brand_id": "burberry",        "name": "Burberry",            "tagwalk_slug": "burberry",            "city": "london"},
        {"brand_id": "alexandermcqueen","name": "Alexander McQueen",   "tagwalk_slug": "alexander-mcqueen",   "city": "london"},
    ],
    "men": [
        {"brand_id": "dior_men",        "name": "Dior Men",            "tagwalk_slug": "dior-homme",          "city": "paris",  "gender_path": "man"},
        {"brand_id": "hermes_men",      "name": "Hermès Men",          "tagwalk_slug": "hermes",              "city": "paris",  "gender_path": "man"},
        {"brand_id": "lv_men",          "name": "Louis Vuitton Men",   "tagwalk_slug": "louis-vuitton",       "city": "paris",  "gender_path": "man"},
        {"brand_id": "prada_men",       "name": "Prada Men",           "tagwalk_slug": "prada",               "city": "milan",  "gender_path": "man"},
        {"brand_id": "brunellocucinelli_men","name":"Brunello Cucinelli Men","tagwalk_slug":"brunello-cucinelli","city":"milan", "gender_path": "man"},
        {"brand_id": "zegna",           "name": "Zegna",               "tagwalk_slug": "ermenegildo-zegna",   "city": "milan",  "gender_path": "man"},
        {"brand_id": "paulsmith",       "name": "Paul Smith",          "tagwalk_slug": "paul-smith",          "city": "milan",  "gender_path": "man"},
        {"brand_id": "burberry_men",    "name": "Burberry Men",        "tagwalk_slug": "burberry",            "city": "london", "gender_path": "man"},
    ],
}
# deduplicate women's list
_seen = set()
_deduped = []
for b in BRAND_COVERAGE["women"]:
    if b["brand_id"] not in _seen:
        _seen.add(b["brand_id"])
        _deduped.append(b)
BRAND_COVERAGE["women"] = _deduped


def _tagwalk_season_slug(period, year):
    mapping = {
        "SS":     f"spring-summer-{year}",
        "AW":     f"fall-winter-{year}",
        "FW":     f"fall-winter-{year}",
        "RESORT": f"resort-{year}",
        "COUTURE":f"couture-{year}",
        "PF":     f"pre-fall-{year}",
    }
    return mapping.get(period.upper(), f"{period.lower()}-{year}")


def _get_model(task="text_extraction"):
    with open(CONFIG_PATH) as f:
        return json.load(f)["tasks"][task]["model"]


# ── Step 1: Interpret query ───────────────────────────────────────────────────

VALID_CATEGORIES = [
    "COLOUR", "SILHOUETTE", "MATERIAL_FABRIC", "MOTIF_PRINT",
    "HARDWARE_DETAIL", "NARRATIVE_THEME", "CULTURAL_REFERENCE",
    "SENSORY_EXPERIENTIAL", "CUSTOMER_ARCHETYPE_HOUSE",
]

# Common user terms → valid category
_CATEGORY_ALIASES = {
    "material": "MATERIAL_FABRIC", "materials": "MATERIAL_FABRIC",
    "fabric": "MATERIAL_FABRIC", "fabrics": "MATERIAL_FABRIC",
    "textile": "MATERIAL_FABRIC", "textiles": "MATERIAL_FABRIC",
    "colour": "COLOUR", "color": "COLOUR", "colors": "COLOUR",
    "colours": "COLOUR", "palette": "COLOUR",
    "silhouette": "SILHOUETTE", "shape": "SILHOUETTE", "cut": "SILHOUETTE",
    "print": "MOTIF_PRINT", "prints": "MOTIF_PRINT",
    "pattern": "MOTIF_PRINT", "patterns": "MOTIF_PRINT", "motif": "MOTIF_PRINT",
    "hardware": "HARDWARE_DETAIL", "detail": "HARDWARE_DETAIL",
    "theme": "NARRATIVE_THEME", "mood": "SENSORY_EXPERIENTIAL", "narrative": "NARRATIVE_THEME",
    "cultural": "CULTURAL_REFERENCE", "reference": "CULTURAL_REFERENCE",
    "experience": "SENSORY_EXPERIENTIAL", "show": "SENSORY_EXPERIENTIAL",
}

INTERPRET_SYSTEM = f"""\
You are a fashion query interpreter. Extract structured intent from a natural-language question.

VALID CATEGORIES (use ONLY these exact strings):
{', '.join(VALID_CATEGORIES)}

Return JSON with:
  "categories": list of VALID CATEGORY strings relevant to the question — must be exact matches above
  "season_label": e.g. "SS2026", "AW2026", "AW2025" — infer from question.
                  Today is {{today}}. Current runway season: SS2026 shows happened Sep 2025. AW2026 shows happened Jan–Feb 2026.
                  "this season" or "this spring" = SS2026. "next season" or "this autumn/fall/winter" = AW2026.
  "gender": "women" or "men" or "both" — default "women"
  "brands_hint": list of brand names explicitly mentioned in question (e.g. ["Hermès"]). Empty list if no specific brand.
  "synthesis_instruction": one sentence on what kind of answer to give

Return only valid JSON. No markdown.\
"""

def _normalise_categories(raw_cats: list) -> list:
    result = []
    for c in raw_cats:
        cu = c.upper().strip()
        if cu in VALID_CATEGORIES:
            result.append(cu)
        elif cu in _CATEGORY_ALIASES:
            result.append(_CATEGORY_ALIASES[cu])
        else:
            alias = _CATEGORY_ALIASES.get(cu.lower())
            if alias:
                result.append(alias)
    return list(dict.fromkeys(result)) or ["COLOUR"]  # dedupe, fallback


def interpret(question, today="2026-05-01"):
    model = _get_model("text_extraction")
    system = INTERPRET_SYSTEM.replace("{today}", today)
    raw = llm_module.call(system, f"Question: {question}", max_tokens=400, model=model)
    raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    intent = json.loads(raw)
    intent["categories"] = _normalise_categories(intent.get("categories", []))
    return intent


# ── Step 2: Ensure data exists for brand + season ────────────────────────────

def _season_has_data(brand_id, season_label):
    """True if any instances exist for this brand + season in the graph."""
    seasons = graph._load("seasons")
    # Find season_id
    for sid, s in seasons.items():
        if s["brand_id"] == brand_id and s["season_label"] == season_label.upper():
            instances = graph._load("instances")
            return any(i["season_id"] == sid for i in instances)
    return False


def _ensure_brand(brand_id, name, founding_country=None):
    graph.add_brand(brand_id, name, founding_country=founding_country)


def _fetch_season(brand_info, period, year, gender_path="woman"):
    """Fetch tag-walk look images + run vision extraction for a brand/season."""
    brand_id   = brand_info["brand_id"]
    name       = brand_info["name"]
    slug       = brand_info.get("tagwalk_slug")
    city       = brand_info.get("city", "paris")
    gpath      = brand_info.get("gender_path", gender_path)
    season_label = f"{period}{year}"
    season_id    = f"{brand_id}_{period.lower()}{year}"

    _ensure_brand(brand_id, name)
    graph.add_season(season_id, brand_id, year, period, "Unknown")

    if not slug:
        print(f"     [skip] {name} — no tag-walk coverage for {season_label}")
        return 0

    tw_slug = _tagwalk_season_slug(period, year)
    url = f"https://www.tag-walk.com/en/collection/{gpath}/{slug}/{tw_slug}?city={city}"

    print(f"     Fetching {name} {season_label} from tag-walk...")
    try:
        text = fetch_show.fetch_tagwalk(url)
    except Exception as e:
        print(f"     [error] {name}: {e}")
        return 0

    # Extract look image URLs from the returned text block
    import re
    look_image_urls = re.findall(r'Look \d+: (https://cdn\.tag-walk\.com/\S+)', text)
    if not look_image_urls:
        print(f"     [warn] {name} — 0 look images extracted")
        return 0

    # Persist look image URLs to season
    graph.add_season(season_id, brand_id, year, period, "Unknown", look_image_urls=look_image_urls)

    # Vision extraction
    vision_codes = vision_extract.extract(look_image_urls, name, season_label, url)
    vision_codes = chk.check_taxonomy_only(vision_codes)

    added = 0
    for code in vision_codes:
        _, outcome = graph.add_instance(
            season_id=season_id, brand_id=brand_id,
            category=code["category"], subcategory=code["subcategory"],
            description=code.get("description", ""),
            prominence=code.get("prominence", "Unknown"),
            new_or_recurring=code.get("new_or_recurring", "Unknown"),
            evolution_note=code.get("evolution_note"),
            evidence=code.get("evidence"),
            checker_status=code.get("checker_status", "pending"),
            checker_flags=code.get("checker_flags", []),
            source=url,
        )
        if outcome == "added":
            added += 1

    print(f"     {name} {season_label} — {added} codes stored")
    return added


def ensure_coverage(period, year, gender="women", verbose=True):
    """
    For each brand in coverage, fetch season data if not already in graph.
    Returns list of brand_ids that now have data.
    """
    coverage = BRAND_COVERAGE.get(gender, [])
    period   = period.upper()
    season_label = f"{period}{year}"
    ready = []

    for b in coverage:
        if _season_has_data(b["brand_id"], season_label):
            if verbose:
                print(f"     [cached] {b['name']} {season_label}")
            ready.append(b["brand_id"])
        else:
            if verbose:
                print(f"     [fetch ] {b['name']} {season_label}")
            n = _fetch_season(b, period, year)
            if n > 0:
                ready.append(b["brand_id"])

    return ready


# ── Step 3: Pull codes from graph ─────────────────────────────────────────────

def pull_codes(categories, season_label, gender="women", brands_hint=None):
    """Pull relevant instances from the graph for the given categories + season."""
    results = []
    # Map brand name hints → brand_ids for filtering
    hint_ids = None
    if brands_hint:
        all_brands = BRAND_COVERAGE.get("women", []) + BRAND_COVERAGE.get("men", [])
        hint_ids = {b["brand_id"] for b in all_brands
                    if any(h.lower() in b["name"].lower() for h in brands_hint)}
    for cat in categories:
        rows = graph.query_code_across_brands(cat, period_label=season_label)
        # Filter to relevant gender brands
        brand_ids = {b["brand_id"] for b in BRAND_COVERAGE.get(gender, [])}
        rows = [r for r in rows if r["brand_id"] in brand_ids]
        # Filter to specific brands if hinted
        if hint_ids:
            rows = [r for r in rows if r["brand_id"] in hint_ids]
        # Only use validated or vision_ok codes
        rows = [r for r in rows if r.get("checker_status") in ("validated", "vision_ok", "flagged")]
        results.extend(rows)
    return results


# ── Step 4: Synthesize answer (with answer cache) ─────────────────────────────

SYNTHESIZE_SYSTEM = """\
You are a fashion trend analyst. Given extracted house code data from multiple runway collections,
answer the user's question clearly and confidently.

Be specific: name actual colours/materials/silhouettes seen. Cite which houses.
Write in a direct, editorial tone — no hedging, no "it seems like."
Keep the answer under 200 words unless the question requires more detail.\
"""

cache_mod.TTL["answer"] = 30  # answers cached 30 days

def _answer_cache_key(categories, season_key, gender, brands_hint):
    """Stable cache key from intent — same question phrased differently hits same cache."""
    import hashlib
    parts = sorted(categories) + [season_key, gender] + sorted(brands_hint or [])
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def synthesize(question, codes, synthesis_instruction, cache_key=None):
    if not codes:
        return "Not enough runway data collected yet to answer this question."

    if cache_key:
        cached = cache_mod.get("answer", cache_key)
        if cached:
            print("     [answer cache hit]")
            return cached

    model = _get_model("cross_brand_analysis")

    codes_text = json.dumps([{
        "brand": c["brand"], "season": c["season_label"],
        "category": c.get("category", ""), "subcategory": c.get("subcategory", ""),
        "description": c["description"], "prominence": c["prominence"],
    } for c in codes], indent=2)

    user_msg = (
        f"Question: {question}\n\n"
        f"Instruction: {synthesis_instruction}\n\n"
        f"Runway data ({len(codes)} code instances across {len({c['brand'] for c in codes})} brands):\n"
        f"{codes_text}"
    )

    result = llm_module.call(SYNTHESIZE_SYSTEM, user_msg, max_tokens=600, model=model)
    if cache_key and result:
        cache_mod.set("answer", cache_key, result, ttl_days=30)
    return result


# ── Main entry point ──────────────────────────────────────────────────────────

def answer(question, today="2026-05-01", verbose=True):
    """
    Answer a fashion question reactively — fetching data on demand if needed.
    Returns the synthesized answer string.
    """
    if verbose:
        print(f"\n  Interpreting: {question!r}")

    intent = interpret(question, today)
    if verbose:
        print(f"  Intent: {intent}")

    categories   = intent.get("categories", ["COLOUR"])
    season_label = intent.get("season_label", "SS2026").upper()
    gender       = intent.get("gender", "women")
    synthesis_instr = intent.get("synthesis_instruction", "Answer the question directly.")

    # Parse season
    period = ""
    year   = 0
    for p in ("COUTURE", "RESORT", "AW", "FW", "SS", "PF"):
        if season_label.startswith(p):
            period = "AW" if p == "FW" else p
            year   = int(season_label[len(p):])
            if year < 100:
                year += 2000
            break

    if verbose:
        print(f"\n  Ensuring {gender} coverage for {period}{year}...")
    ensure_coverage(period, year, gender, verbose)

    if verbose:
        print(f"\n  Pulling {categories} codes for {season_label}...")
    codes = pull_codes(categories, f"{period}{year}", gender)

    if verbose:
        print(f"  {len(codes)} relevant code instances found")
        print(f"\n  Synthesizing answer...")

    return synthesize(question, codes, synthesis_instr)


def emit(obj):
    """Write a JSON line to stdout — used in --stream mode for the frontend."""
    import sys
    print(json.dumps(obj), flush=True)


def answer_streaming(question, today="2026-05-01"):
    """
    Like answer() but emits structured JSON lines for the Next.js SSE frontend.
    Each line: {"type": "...", ...}

    Fast path: if cached data exists for the season, answer immediately.
    Cold path: fetch missing brands on demand only when season has zero data.
    """
    emit({"type": "status", "message": "Interpreting question..."})
    try:
        intent = interpret(question, today)
    except Exception as e:
        emit({"type": "error", "message": f"Interpretation failed: {e}"})
        return

    categories      = intent.get("categories", ["COLOUR"])
    season_label    = intent.get("season_label", "SS2026").upper()
    gender          = intent.get("gender", "women")
    synthesis_instr = intent.get("synthesis_instruction", "Answer the question directly.")
    brands_hint     = intent.get("brands_hint", [])

    period = ""
    year   = 0
    for p in ("COUTURE", "RESORT", "AW", "FW", "SS", "PF"):
        if season_label.startswith(p):
            period = "AW" if p == "FW" else p
            year   = int(season_label[len(p):])
            if year < 100:
                year += 2000
            break

    season_key = f"{period}{year}"
    coverage   = BRAND_COVERAGE.get(gender, [])
    ans_key    = _answer_cache_key(categories, season_key, gender, brands_hint)

    # ── Fast path: answer from whatever is already cached ────────────────────
    cached_codes = pull_codes(categories, season_key, gender, brands_hint=brands_hint)

    if cached_codes:
        # Show which brands contributed
        cached_brand_ids = {c["brand_id"] for c in cached_codes}
        for b in coverage:
            status = "cached" if b["brand_id"] in cached_brand_ids else "no_data"
            if status == "cached":
                emit({"type": "brand", "brand": b["name"],
                      "season": season_label, "status": "cached"})

        emit({"type": "codes_found", "count": len(cached_codes),
              "brands": list({c["brand"] for c in cached_codes})})
        emit({"type": "status", "message": "Synthesizing answer..."})
        try:
            result = synthesize(question, cached_codes, synthesis_instr, cache_key=ans_key)
            emit({"type": "answer", "content": result,
                  "season": season_label, "gender": gender,
                  "categories": categories})
        except Exception as e:
            emit({"type": "error", "message": f"Synthesis failed: {e}"})
        return

    # ── Cold path: nothing cached for this season, fetch on demand ───────────
    emit({"type": "status", "message": f"No data yet for {season_key}. Fetching from runway sources..."})

    for b in coverage:
        if _season_has_data(b["brand_id"], season_key):
            emit({"type": "brand", "brand": b["name"], "season": season_label, "status": "cached"})
        else:
            emit({"type": "brand", "brand": b["name"], "season": season_label, "status": "fetching"})
            n = _fetch_season(b, period, year)
            emit({"type": "brand", "brand": b["name"], "season": season_label,
                  "status": "done", "codes_added": n})

    codes = pull_codes(categories, season_key, gender, brands_hint=brands_hint)
    emit({"type": "codes_found", "count": len(codes),
          "brands": list({c["brand"] for c in codes})})
    emit({"type": "status", "message": "Synthesizing answer..."})
    try:
        result = synthesize(question, codes, synthesis_instr, cache_key=ans_key)
        emit({"type": "answer", "content": result,
              "season": season_label, "gender": gender,
              "categories": categories})
    except Exception as e:
        emit({"type": "error", "message": f"Synthesis failed: {e}"})


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    stream_mode = "--stream" in args
    args = [a for a in args if a != "--stream"]

    q = " ".join(args) or "What are the three colours I will see for spring summer 2026?"

    if stream_mode:
        answer_streaming(q)
    else:
        result = answer(q)
        print("\n" + "="*60)
        print(result)
