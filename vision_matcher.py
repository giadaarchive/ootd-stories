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

import json, base64, sys, os
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

Return a JSON object with key "matches" — an array of up to 3 candidates ranked by likelihood:
{"matches": [
  {"candidate_index": 0, "confidence": 0.92, "reasoning": "Navy double-breasted cut matches exactly"},
  {"candidate_index": 2, "confidence": 0.55, "reasoning": "Also navy blazer but different silhouette"}
]}

Confidence: 0.0–1.0. If best match confidence < 0.4, return empty array.
No markdown, no explanation.
"""


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
        return json.loads(raw).get("items", [])
    except json.JSONDecodeError:
        print(f"  [warn] JSON parse failed for identify step: {raw[:200]}", file=sys.stderr)
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
        ranked = json.loads(raw).get("matches", [])
    except json.JSONDecodeError:
        print(f"  [warn] JSON parse failed for match step: {raw[:200]}", file=sys.stderr)
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


def run_matching(image_b64: str, catalog: list[dict]) -> list[dict]:
    """
    Full pipeline: identify items → filter catalog → match each item.
    Returns list of result dicts ready for Telegram review UI:
    [{
        "identified": {type, colour, description},
        "top_matches": [{item, confidence, reasoning}],
        "status": "matched" | "ambiguous" | "unidentified"
    }]
    """
    from collection_cache import search

    identified_items = identify_items(image_b64)
    if not identified_items:
        return []

    results = []
    for item in identified_items:
        candidates = search(item["type"], item["colour"], catalog, max_results=35)
        top_matches = match_item(item, candidates) if candidates else []

        if top_matches:
            best_conf = top_matches[0]["confidence"]
            status = "matched" if best_conf >= 0.70 else "ambiguous"
        else:
            status = "unidentified"

        results.append({
            "identified": item,
            "top_matches": top_matches,
            "status": status,
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
