"""
Checker agent — validates LLM-extracted house codes for hallucination and taxonomy compliance.

Two-pass approach:
  Pass 1 (local, instant): taxonomy membership check — category/subcategory must exist.
  Pass 2 (LLM, fast model): evidence and overclaim check against source text.

Flag codes: "validated" | "flagged" | "rejected"
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import llm as llm_module

_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH   = os.path.join(_DIR, "models_config.json")
TAXONOMY_PATH = os.path.join(_DIR, "taxonomy.json")


def _get_model():
    with open(CONFIG_PATH) as f:
        return json.load(f)["tasks"]["checker"]["model"]


def _load_taxonomy():
    with open(TAXONOMY_PATH) as f:
        return json.load(f)["categories"]


CHECKER_SYSTEM = """\
You are a fact-checker for fashion house code extractions. Given extracted codes and the original source text, validate each one.

For each code check:
1. Does the evidence quote appear in or is directly supported by the source text?
2. Does the description stay within what the evidence supports (no overclaiming)?
3. Is this a duplicate of another code in the list?

For each code, set:
  "checker_status": "validated" | "flagged" | "rejected"
  "checker_flags": list of strings from: EVIDENCE_NOT_IN_SOURCE | OVERCLAIM | DUPLICATE | WEAK_EVIDENCE

Return the same JSON array with checker_status and checker_flags added to each object.
Return only valid JSON. No markdown fencing.\
"""


def check_taxonomy_only(extracted_codes):
    """
    Run only Pass 1 (taxonomy membership check) — for vision-extracted codes
    where there is no source text to verify evidence against.
    Sets checker_status to 'vision_ok' (passed) or 'rejected' (taxonomy mismatch).
    """
    taxonomy = _load_taxonomy()
    tax_upper = {k.upper(): {s.upper() for s in v["subcategories"]} for k, v in taxonomy.items()}

    for code in extracted_codes:
        flags = list(code.get("checker_flags", []))
        cat = code.get("category", "").upper().strip()
        sub = code.get("subcategory", "").upper().strip()
        code["category"]    = cat
        code["subcategory"] = sub
        if cat not in tax_upper:
            flags.append("TAXONOMY_MISMATCH")
            code["checker_status"] = "rejected"
        elif sub not in tax_upper[cat]:
            flags.append("TAXONOMY_MISMATCH")
            code["checker_status"] = "rejected"
        else:
            code["checker_status"] = "vision_ok"
        code["checker_flags"] = flags

    return extracted_codes


def check(extracted_codes, source_text, brand, season_label):
    """Validate extracted codes. Returns same list with checker_status and checker_flags added."""
    taxonomy = _load_taxonomy()

    # Pass 1: local taxonomy check — normalise to UPPER_CASE before comparing
    tax_upper = {k.upper(): {s.upper() for s in v["subcategories"]} for k, v in taxonomy.items()}

    for code in extracted_codes:
        flags = list(code.get("checker_flags", []))
        cat = code.get("category", "").upper().strip()
        sub = code.get("subcategory", "").upper().strip()
        # Normalise the code so downstream uses consistent casing
        code["category"]    = cat
        code["subcategory"] = sub
        if cat not in tax_upper:
            flags.append("TAXONOMY_MISMATCH")
            code["checker_status"] = "rejected"
        elif sub not in tax_upper[cat]:
            flags.append("TAXONOMY_MISMATCH")
            code["checker_status"] = "rejected"
        else:
            code.setdefault("checker_status", "pending")
        code["checker_flags"] = flags

    # Pass 2: LLM evidence check (only on non-rejected codes)
    pending = [c for c in extracted_codes if c.get("checker_status") != "rejected"]
    if not pending:
        return extracted_codes

    model = _get_model()
    user_msg = (
        f"Brand: {brand}\n"
        f"Season: {season_label}\n\n"
        f"SOURCE TEXT:\n{source_text[:6000]}\n\n"
        f"EXTRACTED CODES:\n{json.dumps(pending, indent=2)}"
    )

    raw = llm_module.call(CHECKER_SYSTEM, user_msg, max_tokens=4000, model=model)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()

    try:
        checked_pending = json.loads(raw)
    except json.JSONDecodeError:
        import re as _re
        # Strip malformed Unicode escapes from LLM output
        cleaned = _re.sub(r'\\u[0-9a-fA-F]{0,3}(?![0-9a-fA-F])', '', raw)
        try:
            checked_pending = json.loads(cleaned)
        except json.JSONDecodeError:
            # Fallback: return pending codes as-is with pending status
            return extracted_codes

    # Merge checker results back by position
    checked_map = {i: c for i, c in enumerate(checked_pending)}
    result = []
    pending_idx = 0
    for code in extracted_codes:
        if code.get("checker_status") == "rejected":
            result.append(code)
        else:
            merged = checked_map.get(pending_idx, code)
            # Preserve any taxonomy flags from Pass 1
            p1_flags = [f for f in code.get("checker_flags", []) if f == "TAXONOMY_MISMATCH"]
            merged["checker_flags"] = p1_flags + [
                f for f in merged.get("checker_flags", []) if f != "TAXONOMY_MISMATCH"
            ]
            result.append(merged)
            pending_idx += 1

    return result
