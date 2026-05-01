#!/usr/bin/env python3
"""
House Code Knowledge Graph — main CLI.

ADDING SHOWS:
  python3 house_codes/house_code_graph.py --add-show https://... akris AW2026 "Albert Kriemler"
  python3 house_codes/house_code_graph.py --add-text akris AW2026 --cd "Albert Kriemler" --text "..."
  cat show_notes.txt | python3 house_codes/house_code_graph.py --add-text akris AW2026

QUERYING:
  python3 house_codes/house_code_graph.py --query-brand akris
  python3 house_codes/house_code_graph.py --query-period AW2026
  python3 house_codes/house_code_graph.py --query-code COLOUR
  python3 house_codes/house_code_graph.py --query-code COLOUR PALETTE --period AW2026

VISION:
  python3 house_codes/house_code_graph.py --analyze-images akris AW2026

STATUS:
  python3 house_codes/house_code_graph.py --status
"""
import argparse
import json
import os
import sys

# Allow importing sibling modules and parent llm.py
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(_HERE, "..", ".env"))

import graph
import extract as extractor
import checker as chk
import fetch_show
import vision_extract


# ── Brand register ────────────────────────────────────────────────────────────

BRANDS = {
    "akris":        {"name": "Akris",                 "founded_year": 1922, "founding_country": "Switzerland", "founding_category": "RTW"},
    "hermes":       {"name": "Hermès",                "founded_year": 1837, "founding_country": "France",      "founding_category": "Leather goods / RTW"},
    "dior":         {"name": "Christian Dior",        "founded_year": 1946, "founding_country": "France",      "founding_category": "Couture / RTW"},
    "chanel":       {"name": "Chanel",                "founded_year": 1910, "founding_country": "France",      "founding_category": "Couture / RTW"},
    "lv":           {"name": "Louis Vuitton",         "founded_year": 1854, "founding_country": "France",      "founding_category": "Leather goods / RTW"},
    "ferragamo":    {"name": "Salvatore Ferragamo",   "founded_year": 1927, "founding_country": "Italy",       "founding_category": "Shoes / RTW"},
    "zimmermann":   {"name": "Zimmermann",            "founded_year": 1991, "founding_country": "Australia",   "founding_category": "RTW"},
    "valextra":     {"name": "Valextra",              "founded_year": 1937, "founding_country": "Italy",       "founding_category": "Leather goods"},
    "kiton":        {"name": "Kiton",                 "founded_year": 1956, "founding_country": "Italy",       "founding_category": "Tailoring / RTW"},
    "bertoni":      {"name": "Bertoni",               "founded_year": None, "founding_country": None,          "founding_category": "RTW"},
}


def _ensure_brand(brand_id):
    info = BRANDS.get(brand_id, {
        "name": brand_id,
        "founded_year": None,
        "founding_country": None,
        "founding_category": None,
    })
    graph.add_brand(brand_id, **info)
    return info.get("name", brand_id)


def _parse_season(label):
    """'AW2026' or 'AW26' → ('AW', 2026).  'FW' normalised to 'AW'."""
    label = label.upper().strip()
    for period in ("COUTURE", "RESORT", "PF", "AW", "FW", "SS"):
        if label.startswith(period):
            year_s = label[len(period):]
            if len(year_s) == 2:
                year_s = "20" + year_s
            return ("AW" if period == "FW" else period), int(year_s)
    raise ValueError(f"Cannot parse season label: {label!r}  (expected e.g. AW2026, SS26)")


# ── Core flow ─────────────────────────────────────────────────────────────────

def add_show(url, brand_id, season_label, cd_name, raw_text=None):
    brand_id = brand_id.lower()
    period, year = _parse_season(season_label)
    season_label_norm = f"{period}{year}"
    season_id = f"{brand_id}_{period.lower()}{year}"

    brand_name = _ensure_brand(brand_id)
    graph.add_season(
        season_id=season_id,
        brand_id=brand_id,
        year=year,
        period=period,
        creative_director_name=cd_name or "Unknown",
        source_urls=[url] if url else [],
    )

    print(f"\n  Brand   : {brand_name}")
    print(f"  Season  : {season_label_norm}")
    print(f"  Director: {cd_name or '—'}")
    print(f"  ID      : {season_id}")

    # 1. Fetch — route by source type
    look_image_urls = []
    if raw_text:
        text = fetch_show.fetch_text(raw_text)
        source_url = url or "manual input"
    elif url and "tag-walk.com" in url:
        print(f"\n  Fetching (tag-walk): {url}")
        text = fetch_show.fetch_tagwalk(url)
        source_url = url
        # tag-walk look image URLs embedded in the returned text as metadata block
        look_image_urls = _extract_tagwalk_image_urls(text)
    elif url and ("youtube.com" in url or "youtu.be" in url):
        print(f"\n  Fetching (YouTube): {url}")
        text, look_image_urls = fetch_show.fetch_youtube(url)
        source_url = url
        hint = fetch_show.youtube_season_hint(url)
        if hint:
            print(f"  YouTube hint: {hint}")
    elif url:
        print(f"\n  Fetching: {url}")
        text = fetch_show.fetch_url(url)
        source_url = url
    else:
        print("ERROR: provide a URL or --text")
        sys.exit(1)

    print(f"  Text: {len(text):,} chars")
    if look_image_urls:
        print(f"  Images: {len(look_image_urls)} look frames available")
        # Persist look image URLs to season node
        graph.add_season(season_id, brand_id, year, period,
                         cd_name or "Unknown", look_image_urls=look_image_urls)

    # 2a. Text extraction (when we have meaningful text)
    codes = []
    if len(text.strip()) > 300:
        print("\n  Extracting house codes (text)...")
        codes = extractor.extract(text, brand_name, season_label_norm, source_url)
        print(f"  {len(codes)} codes extracted from text")

    # 2b. Vision extraction (when we have look images)
    vision_codes = []
    if look_image_urls:
        print(f"\n  Extracting house codes (vision — {len(look_image_urls)} images)...")
        vision_codes = vision_extract.extract(look_image_urls, brand_name, season_label_norm, source_url)
        print(f"  {len(vision_codes)} codes extracted from images")

    # 3. Check — text codes through full checker; vision codes taxonomy-only (no source text to verify)
    all_codes = []
    if codes:
        print("\n  Running checker (text codes)...")
        codes = chk.check(codes, text, brand_name, season_label_norm)
        all_codes.extend(codes)

    if vision_codes:
        print("  Running checker (vision codes — taxonomy pass only)...")
        vision_codes = chk.check_taxonomy_only(vision_codes)
        all_codes.extend(vision_codes)

    counts = {}
    for c in all_codes:
        s = c.get("checker_status", "pending")
        counts[s] = counts.get(s, 0) + 1
    print(f"  Checker: {counts.get('validated',0)} validated  |  "
          f"{counts.get('flagged',0)} flagged  |  "
          f"{counts.get('rejected',0)} rejected  |  "
          f"{counts.get('vision_ok',0)} vision_ok")

    # 4. Store (with deduplication)
    print("\n  Storing...")
    added = dupes = 0
    for code in all_codes:
        _, outcome = graph.add_instance(
            season_id=season_id,
            brand_id=brand_id,
            category=code["category"],
            subcategory=code["subcategory"],
            description=code.get("description", ""),
            prominence=code.get("prominence", "Unknown"),
            new_or_recurring=code.get("new_or_recurring", "Unknown"),
            evolution_note=code.get("evolution_note"),
            evidence=code.get("evidence"),
            checker_status=code.get("checker_status", "pending"),
            checker_flags=code.get("checker_flags", []),
            source=source_url,
        )
        if outcome == "added":
            added += 1
            flag_str = " [" + ", ".join(code.get("checker_flags", [])) + "]" if code.get("checker_flags") else ""
            print(f"    [{code.get('checker_status','?'):9s}] {code['category']} / {code['subcategory']}{flag_str}")
        else:
            dupes += 1

    dupe_note = f"  ({dupes} duplicate(s) skipped)" if dupes else ""
    print(f"\n  Done — {added} new instances stored for {season_id}{dupe_note}")
    print(f"  Graph: {graph.summary()}")


def _extract_tagwalk_image_urls(text):
    """Pull look image URLs from the metadata block embedded by fetch_tagwalk."""
    import re
    return re.findall(r'Look \d+: (https://cdn\.tag-walk\.com/\S+)', text)


# ── Queries ───────────────────────────────────────────────────────────────────

def cmd_analyze_images(brand_id, season_label):
    """Run vision extraction on already-stored look_image_urls for a season."""
    brand_id = brand_id.lower()
    period, year = _parse_season(season_label)
    season_label_norm = f"{period}{year}"
    season_id = f"{brand_id}_{period.lower()}{year}"

    seasons = graph._load("seasons")
    if season_id not in seasons:
        print(f"Season {season_id} not found in graph.")
        return

    season = seasons[season_id]
    look_image_urls = season.get("look_image_urls", [])
    if not look_image_urls:
        print(f"No look_image_urls stored for {season_id}. Run --add-show with a tag-walk or YouTube URL first.")
        return

    brand_name = _ensure_brand(brand_id)
    print(f"\n  {brand_name}  {season_label_norm}  — {len(look_image_urls)} look images")
    print(f"\n  Extracting house codes (vision)...")
    vision_codes = vision_extract.extract(look_image_urls, brand_name, season_label_norm, "vision")
    print(f"  {len(vision_codes)} codes extracted from images")

    print("  Running checker (taxonomy only)...")
    vision_codes = chk.check_taxonomy_only(vision_codes)

    print("\n  Storing...")
    added = dupes = 0
    for code in vision_codes:
        _, outcome = graph.add_instance(
            season_id=season_id,
            brand_id=brand_id,
            category=code["category"],
            subcategory=code["subcategory"],
            description=code.get("description", ""),
            prominence=code.get("prominence", "Unknown"),
            new_or_recurring=code.get("new_or_recurring", "Unknown"),
            evolution_note=code.get("evolution_note"),
            evidence=code.get("evidence"),
            checker_status=code.get("checker_status", "pending"),
            checker_flags=code.get("checker_flags", []),
            source="vision",
        )
        if outcome == "added":
            added += 1
            print(f"    [{code.get('checker_status','?'):9s}] {code['category']} / {code['subcategory']}")
        else:
            dupes += 1

    dupe_note = f"  ({dupes} duplicate(s) skipped)" if dupes else ""
    print(f"\n  Done — {added} new vision instances stored for {season_id}{dupe_note}")
    print(f"  Graph: {graph.summary()}")


def cmd_query_brand(brand_id):
    timeline = graph.query_brand_timeline(brand_id.lower())
    if not timeline:
        print(f"No data for brand '{brand_id}'")
        return
    for season_label, data in timeline.items():
        s = data["season"]
        print(f"\n{'='*60}")
        print(f"  {season_label}  |  CD: {s.get('creative_director','?')}  |  {s.get('show_location','')}")
        for inst in data["instances"]:
            status = inst.get("checker_status", "?")
            print(f"    [{inst['prominence']:10s}] {inst['category']} / {inst['subcategory']}")
            print(f"               {inst['description'][:80]}")


def cmd_query_period(period_label):
    cross = graph.query_period_cross_section(period_label)
    if not cross:
        print(f"No data for period '{period_label}'")
        return
    print(f"\nPeriod: {period_label.upper()}  |  {len(cross)} brands\n")
    for bid, data in cross.items():
        brand_name = data["brand"].get("name", bid)
        instances = data["instances"]
        print(f"  {brand_name}  ({len(instances)} codes)")
        for inst in instances:
            print(f"    [{inst['prominence']:10s}] {inst['category']} / {inst['subcategory']}")


def cmd_query_code(category, subcategory=None, period=None):
    results = graph.query_code_across_brands(category, subcategory, period)
    if not results:
        label = f"{category}" + (f" / {subcategory}" if subcategory else "")
        print(f"No instances found for {label}" + (f" in {period}" if period else ""))
        return
    label = f"{category}" + (f" / {subcategory}" if subcategory else "")
    period_str = f" in {period}" if period else ""
    print(f"\nCode: {label}{period_str}  |  {len(results)} instances\n")
    for r in results:
        print(f"  {r['brand']:20s}  {r['season_label']:8s}  [{r['prominence']:10s}]  {r['description'][:60]}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="House Code Knowledge Graph")

    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--add-show", nargs="+", metavar="ARG",
                       help="URL BRAND SEASON [CD_NAME]")
    group.add_argument("--add-text", nargs=2, metavar=("BRAND", "SEASON"),
                       help="Add show from --text or stdin")
    group.add_argument("--analyze-images", nargs=2, metavar=("BRAND", "SEASON"),
                       help="Run vision extraction on stored look_image_urls for a season")
    group.add_argument("--query-brand",  metavar="BRAND_ID")
    group.add_argument("--query-period", metavar="PERIOD",  help="e.g. AW2026")
    group.add_argument("--query-code",   nargs="+", metavar="ARG",
                       help="CATEGORY [SUBCATEGORY]")
    group.add_argument("--status", action="store_true", help="Show graph summary")

    p.add_argument("--cd",     metavar="CD_NAME")
    p.add_argument("--text",   metavar="TEXT")
    p.add_argument("--period", metavar="PERIOD", help="Filter period for --query-code")

    args = p.parse_args()

    if args.add_show:
        parts = args.add_show
        if len(parts) < 3:
            p.error("--add-show requires: URL BRAND SEASON [CD_NAME]")
        url, brand_id, season_label = parts[0], parts[1], parts[2]
        cd_name = parts[3] if len(parts) > 3 else args.cd
        add_show(url, brand_id, season_label, cd_name)

    elif args.analyze_images:
        cmd_analyze_images(args.analyze_images[0], args.analyze_images[1])

    elif args.add_text:
        brand_id, season_label = args.add_text
        cd_name = args.cd
        raw_text = args.text or sys.stdin.read()
        if not raw_text.strip():
            p.error("--add-text requires --text TEXT or piped stdin")
        add_show(None, brand_id, season_label, cd_name, raw_text=raw_text)

    elif args.query_brand:
        cmd_query_brand(args.query_brand)

    elif args.query_period:
        cmd_query_period(args.query_period)

    elif args.query_code:
        cat = args.query_code[0]
        sub = args.query_code[1] if len(args.query_code) > 1 else None
        cmd_query_code(cat, sub, args.period)

    elif args.status:
        print(json.dumps(graph.summary(), indent=2))


if __name__ == "__main__":
    main()
