#!/usr/bin/env python3
"""
Two-step AI outfit matching.

Step 1 — identify_items(image_b64):
    Claude vision → free-form identification of every visible item.
    Returns [{type, colour, description}]

Step 2 — match_items(identified, catalog):
    For each identified item, filter catalog by category + colour,
    then Claude text call to rank top candidates.
    Returns [{identified, top_matches: [{item, confidence, reasoning}], status}]
"""

import json, base64, sys, os, re
import anthropic
from dotenv import load_dotenv
load_dotenv()

_client = None

def _anthropic():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


IDENTIFY_SYSTEM = """\
You are an expert fashion stylist. Analyze this outfit photo and identify every visible clothing item and accessory the person is wearing.

For each item return:
- type: the specific garment type (e.g. "blazer", "straight-leg trousers", "leather tote bag", "silk scarf", "ankle boots")
- colour: primary colour description (e.g. "navy", "camel", "off-white", "dark wash")
- description: one precise sentence describing the item (silhouette, material, key details)

Return a JSON object with key "items" containing an array. No markdown, no explanation.
Example:
{"items": [
  {"type": "double-breasted blazer", "colour": "navy", "description": "Navy wool double-breasted blazer with peak lapels and gold buttons"},
  {"type": "straight-leg trousers", "colour": "ivory", "description": "Ivory wool straight-leg trousers with a high waist"}
]}
"""

MATCH_SYSTEM = """\
You are a luxury wardrobe curator. You will receive a description of one clothing item and a list of candidates from the user's personal collection.

Select the best match and return your reasoning. If no candidate is a reasonable match, say so.

Return ONLY a raw JSON object — no markdown, no code fences, no explanation. Just the JSON.
{"matches": [
  {"candidate_index": 0, "confidence": 0.92, "reasoning": "Navy double-breasted cut matches exactly"},
  {"candidate_index": 2, "confidence": 0.55, "reasoning": "Also navy blazer but different silhouette"}
]}

Confidence: 0.0–1.0. If best match confidence < 0.4, return {"matches": []}.
Output raw JSON only. No ```json wrapper.
"""


def _parse_json(raw: str) -> dict:
    """Parse JSON from model response, stripping markdown code fences if present."""
    raw = raw.strip()
    # Strip ```json ... ``` or ``` ... ``` wrappers
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```\s*$', '', raw)
    return json.loads(raw.strip())


def identify_items(image_b64: str) -> list[dict]:
    """
    Step 1: Claude vision identifies all visible items in the outfit photo.
    image_b64: base64-encoded JPEG bytes.
    Returns list of {type, colour, description}.
    """
    msg = _anthropic().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=IDENTIFY_SYSTEM,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_b64,
                    },
                },
                {"type": "text", "text": "Identify every item in this outfit photo."},
            ],
        }],
    )
    raw = msg.content[0].text.strip()
    print(f"  Identify tokens: {msg.usage.input_tokens} in / {msg.usage.output_tokens} out", file=sys.stderr)
    try:
        return _parse_json(raw).get("items", [])
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  [warn] JSON parse failed for identify step: {e} — {raw[:200]}", file=sys.stderr)
        return []


def _format_candidates(candidates: list[dict]) -> str:
    lines = []
    for i, c in enumerate(candidates):
        designer = c.get("designer", "")
        colour = " ".join(filter(None, [c.get("colour"), c.get("colour_detail")]))
        lines.append(f"{i}. {c['name']} | {designer} | {colour} | SKU: {c['sku']}")
    return "\n".join(lines)


def match_item(identified: dict, candidates: list[dict]) -> list[dict]:
    """
    Step 2: Claude ranks catalog candidates for one identified item.
    Returns list of {item: dict, confidence: float, reasoning: str}.
    """
    if not candidates:
        return []

    user_text = (
        f"Item to match: {identified['description']}\n"
        f"Type: {identified['type']}, Colour: {identified['colour']}\n\n"
        f"Candidates from collection:\n{_format_candidates(candidates)}"
    )

    msg = _anthropic().messages.create(
        model="claude-haiku-4-5-20251001",  # cheaper for text-only ranking
        max_tokens=400,
        system=MATCH_SYSTEM,
        messages=[{"role": "user", "content": user_text}],
    )
    raw = msg.content[0].text.strip()
    print(f"  Match tokens: {msg.usage.input_tokens} in / {msg.usage.output_tokens} out", file=sys.stderr)

    try:
        ranked = _parse_json(raw).get("matches", [])
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  [warn] JSON parse failed for match step: {e} — {raw[:200]}", file=sys.stderr)
        return []

    results = []
    for m in ranked:
        idx = m.get("candidate_index")
        if idx is not None and 0 <= idx < len(candidates):
            results.append({
                "item": candidates[idx],
                "confidence": m.get("confidence", 0.0),
                "reasoning": m.get("reasoning", ""),
            })
    return results


def run_matching(image_b64: str, catalog: list[dict], img_hash: str | None = None) -> list[dict]:
    """
    Full pipeline: identify items → filter catalog → match each item.

    Learning layer (requires img_hash):
      - Same image seen before → skip AI, replay prior decisions instantly
      - Same item type+colour seen before → inject previously-approved item as top candidate

    Returns list of result dicts ready for Telegram review UI:
    [{
        "identified": {type, colour, description},
        "top_matches": [{item, confidence, reasoning}],
        "status": "matched" | "ambiguous" | "unidentified",
        "from_memory": bool
    }]
    """
    import corrections_db
    from collection_cache import search

    # ── Level 1: exact image replay ───────────────────────────────────────────
    if img_hash:
        prior = corrections_db.lookup_image(img_hash)
        if prior:
            print(f"  [memory] exact image match — replaying {len(prior)} prior decisions", file=sys.stderr)
            results = []
            for d in prior:
                item = next((c for c in catalog if c["id"] == d["correct_id"]), None)
                if not item:
                    continue
                results.append({
                    "identified": {
                        "type": d["item_type"],
                        "colour": "",
                        "description": f"Previously identified as {d['correct_name']}",
                    },
                    "top_matches": [{
                        "item": item,
                        "confidence": 1.0,
                        "reasoning": "From your correction history",
                    }],
                    "status": "matched",
                    "from_memory": True,
                })
            if results:
                return results

    # ── Level 2: fresh AI identification ─────────────────────────────────────
    identified_items = identify_items(image_b64)
    if not identified_items:
        return []

    results = []
    for item in identified_items:
        candidates = search(item["type"], item["colour"], catalog, max_results=35)

        # ── Level 2b: inject prior corrections for this type+colour ──────────
        if img_hash:
            prior_for_type = corrections_db.lookup_type_colour(item["type"], item["colour"])
            if prior_for_type:
                print(f"  [memory] type+colour match for '{item['type']} {item['colour']}': "
                      f"{[p['correct_name'] for p in prior_for_type]}", file=sys.stderr)
                # Move previously-approved items to the front of candidates
                prior_ids = {p["correct_id"] for p in prior_for_type}
                priority = [c for c in candidates if c["id"] in prior_ids]
                rest = [c for c in candidates if c["id"] not in prior_ids]
                candidates = priority + rest

        top_matches = match_item(item, candidates) if candidates else []

        # If the top match is a prior correction, boost its confidence to 0.95
        if top_matches and img_hash:
            prior_for_type = corrections_db.lookup_type_colour(item["type"], item["colour"])
            prior_ids = {p["correct_id"] for p in prior_for_type}
            if top_matches[0]["item"]["id"] in prior_ids:
                top_matches[0] = dict(top_matches[0], confidence=0.95,
                                      reasoning=top_matches[0]["reasoning"] + " [confirmed by your history]")

        if top_matches:
            best_conf = top_matches[0]["confidence"]
            status = "matched" if best_conf >= 0.70 else "ambiguous"
        else:
            status = "unidentified"

        results.append({
            "identified": item,
            "top_matches": top_matches,
            "status": status,
            "from_memory": False,
        })

    return results


if __name__ == "__main__":
    import sys
    from pathlib import Path
    import collection_cache

    if len(sys.argv) < 2:
        print("Usage: python3 vision_matcher.py <image_path>")
        sys.exit(1)

    image_path = Path(sys.argv[1])
    image_b64 = base64.standard_b64encode(image_path.read_bytes()).decode()

    print("Loading collection cache...")
    catalog = collection_cache.load()
    print(f"Catalog: {len(catalog)} items\n")

    print("Running matching pipeline...")
    results = run_matching(image_b64, catalog)

    for i, r in enumerate(results, 1):
        ident = r["identified"]
        print(f"\n{i}. {ident['type']} ({ident['colour']}) — {r['status'].upper()}")
        print(f"   {ident['description']}")
        for m in r["top_matches"][:2]:
            print(f"   → {m['item']['name']} ({m['confidence']:.0%}) — {m['reasoning'][:60]}")
