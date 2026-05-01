"""
Extract house codes from fashion show text using LLM via OpenRouter.

Features:
  - Always reads models_config.json at call time (stays current after model_watcher runs)
  - Disk cache: identical prompt + model → cached response (14-day TTL)
  - Language detection + auto-translation to English before extraction
  - HTML artifact cleaning (UI labels, nav chrome stripped)
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import llm as llm_module
import cache as cache_mod

_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH   = os.path.join(_DIR, "models_config.json")
TAXONOMY_PATH = os.path.join(_DIR, "taxonomy.json")


def _get_model(task="text_extraction"):
    with open(CONFIG_PATH) as f:
        return json.load(f)["tasks"][task]["model"]


def _taxonomy_ref():
    with open(TAXONOMY_PATH) as f:
        tax = json.load(f)
    lines = []
    for cat, cat_data in tax["categories"].items():
        lines.append(f"CATEGORY: {cat}")
        for sub, sub_data in cat_data["subcategories"].items():
            lines.append(f"  SUBCATEGORY: {sub}  — {sub_data['label']}")
    return "\n".join(lines)


# ── Language detection ────────────────────────────────────────────────────────

_NON_ASCII_THRESHOLD = 0.15   # if >15% of chars are non-ASCII, likely non-English

def _is_likely_english(text):
    if not text:
        return True
    sample = text[:2000]
    non_ascii = sum(1 for c in sample if ord(c) > 127)
    return (non_ascii / len(sample)) < _NON_ASCII_THRESHOLD


def translate_to_english(text, model=None):
    """
    Translate non-English text to English using LLM.
    Cached — same text translated only once.
    Returns (translated_text, source_language_hint).
    """
    if _is_likely_english(text):
        return text, "en"

    if model is None:
        model = _get_model("text_extraction")

    cache_key = cache_mod.llm_key(model, "translate", text[:4000])
    cached = cache_mod.get("llm", cache_key)
    if cached:
        return cached["text"], cached["lang"]

    system = (
        "Translate the following fashion show text to English.\n"
        "Preserve all specific fashion terms, brand names, material names, and designer quotes exactly.\n"
        "First line of your response: 'LANGUAGE: <detected language>'\n"
        "Then the full English translation. No other preamble."
    )
    result = llm_module.call(system, text[:6000], max_tokens=4000, model=model)

    lang = "unknown"
    if result.startswith("LANGUAGE:"):
        first_line, _, rest = result.partition("\n")
        lang = first_line.replace("LANGUAGE:", "").strip().lower()
        result = rest.strip()

    cache_mod.set("llm", cache_key, {"text": result, "lang": lang}, ttl_days=30)
    return result, lang


# ── HTML cleaning ─────────────────────────────────────────────────────────────

_UI_PATTERNS = [
    r"\bshare\b", r"\bfollow\b", r"\bsubscribe\b",
    r"\bsign in\b", r"\bsign up\b", r"\blog in\b",
    r"\bcookie\b", r"\bprivacy policy\b", r"\bterms of (?:use|service)\b",
    r"\bback to top\b", r"\bsee all\b", r"\bview (?:all|more|collection)\b",
    r"\bshop now\b", r"\bshop the look\b",
    r"\badd to (?:cart|bag|wishlist)\b",
    r"\bfilter by\b", r"\bsort by\b",
]


def clean_for_extraction(text):
    """Strip UI chrome and page furniture from scraped HTML text."""
    text = re.sub(r"\s+", " ", text).strip()
    for pat in _UI_PATTERNS:
        text = re.sub(pat, " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


# ── Main extraction ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a fashion house code analyst. Extract structured house code instances from the provided fashion show text.

RULES:
1. Only extract codes CLEARLY EVIDENCED in the text. Never invent or infer beyond what is written.
2. category MUST match one of the allowed CATEGORY values exactly (ALL_CAPS_UNDERSCORED).
3. subcategory MUST match one of the allowed SUBCATEGORY values for that category exactly.
4. If a code maps to multiple subcategories, create one instance per subcategory.
5. prominence: "Hero" (dominant — central to narrative or 3+ looks), "Supporting", or "Referenced".
6. evidence MUST be a verbatim quote or close paraphrase directly from the source text.
7. CUSTOMER_ARCHETYPE_HOUSE: only use text the house/designer explicitly uses to describe their customer.
   CUSTOMER_ARCHETYPE_OBSERVED: infer from the overall runway patterns — NOT a section header or UI label.
8. Reject any code where evidence is UI furniture, navigation text, or a section heading.
9. If you see non-English text, treat it as already translated — extract codes from the meaning.

Return a JSON array of objects with exactly these keys:
  category, subcategory, description, prominence, new_or_recurring, evolution_note, evidence

Return only valid JSON. No markdown fencing. No preamble.\
"""


def extract(text, brand, season_label, source_url, task="text_extraction"):
    """
    Extract house codes from show text.
    Auto-translates non-English text. Uses disk cache to avoid re-processing.
    Returns list of raw code instance dicts.
    """
    model   = _get_model(task)
    tax_ref = _taxonomy_ref()

    # 1. Translate if needed
    text, source_lang = translate_to_english(clean_for_extraction(text), model=model)

    # 2. Build prompt
    user_msg = (
        f"Brand: {brand}\n"
        f"Season: {season_label}\n"
        f"Source: {source_url}\n"
        + (f"Original language: {source_lang}\n" if source_lang != "en" else "")
        + f"\nALLOWED TAXONOMY:\n{tax_ref}\n\n"
        f"SHOW TEXT:\n{text[:8000]}"
    )

    # 3. Check LLM cache
    cache_key = cache_mod.llm_key(model, SYSTEM_PROMPT, user_msg)
    cached = cache_mod.get("llm", cache_key)
    if cached:
        print(f"     [cache hit] extraction")
        return cached

    # 4. Call LLM
    raw    = llm_module.call(SYSTEM_PROMPT, user_msg, max_tokens=4000, model=model)
    result = _parse(raw)

    # 5. Cache result
    cache_mod.set("llm", cache_key, result, ttl_days=14)
    return result


def _parse(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    return json.loads(raw)
