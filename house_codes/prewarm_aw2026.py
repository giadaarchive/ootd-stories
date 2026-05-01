"""
Pre-warm AW2026 data for all major fashion houses — women's and men's.
Fetches tag-walk look images + runs vision extraction for each brand/season.
Skips brands already in the graph with data. Handles failures gracefully.
Run: python3 house_codes/prewarm_aw2026.py
"""
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(_HERE, "..", ".env"))

import graph
import fetch_show
import vision_extract
import checker as chk

PERIOD = "AW"
YEAR   = 2026

WOMEN = [
    # Paris
    {"brand_id": "akris",           "name": "Akris",               "slug": "akris",            "city": "paris"},
    {"brand_id": "chanel",          "name": "Chanel",              "slug": "chanel",           "city": "paris"},
    {"brand_id": "dior",            "name": "Christian Dior",      "slug": "christian-dior",   "city": "paris"},
    {"brand_id": "hermes",          "name": "Hermès",              "slug": "hermes",           "city": "paris"},
    {"brand_id": "lv",              "name": "Louis Vuitton",       "slug": "louis-vuitton",    "city": "paris"},
    {"brand_id": "balenciaga",      "name": "Balenciaga",          "slug": "balenciaga",       "city": "paris"},
    {"brand_id": "saintlaurent",    "name": "Saint Laurent",       "slug": "saint-laurent",    "city": "paris"},
    {"brand_id": "celine",          "name": "Celine",              "slug": "celine",           "city": "paris"},
    {"brand_id": "givenchy",        "name": "Givenchy",            "slug": "givenchy",         "city": "paris"},
    {"brand_id": "valentino",       "name": "Valentino",           "slug": "valentino",        "city": "paris"},
    {"brand_id": "loewe",           "name": "Loewe",               "slug": "loewe",            "city": "paris"},
    {"brand_id": "miumiu",          "name": "Miu Miu",             "slug": "miu-miu",          "city": "paris"},
    {"brand_id": "jacquemus",       "name": "Jacquemus",           "slug": "jacquemus",        "city": "paris"},
    {"brand_id": "isabelmarant",    "name": "Isabel Marant",       "slug": "isabel-marant",    "city": "paris"},
    {"brand_id": "acnestudios",     "name": "Acne Studios",        "slug": "acne-studios",     "city": "paris"},
    {"brand_id": "stellamccartney", "name": "Stella McCartney",    "slug": "stella-mccartney", "city": "paris"},
    {"brand_id": "toteme",          "name": "Toteme",              "slug": "toteme",           "city": "paris"},
    {"brand_id": "zimmermann",      "name": "Zimmermann",          "slug": "zimmermann",       "city": "paris"},
    {"brand_id": "paulsmith",       "name": "Paul Smith",          "slug": "paul-smith",       "city": "milan"},
    # Milan
    {"brand_id": "prada",           "name": "Prada",               "slug": "prada",            "city": "milan"},
    {"brand_id": "bottegaveneta",   "name": "Bottega Veneta",      "slug": "bottega-veneta",   "city": "milan"},
    {"brand_id": "gucci",           "name": "Gucci",               "slug": "gucci",            "city": "milan"},
    {"brand_id": "ferragamo",       "name": "Salvatore Ferragamo", "slug": "salvatore-ferragamo","city": "milan"},
    {"brand_id": "maxmara",         "name": "Max Mara",            "slug": "max-mara",         "city": "milan"},
    {"brand_id": "brunellocucinelli","name": "Brunello Cucinelli", "slug": "brunello-cucinelli","city": "milan"},
    {"brand_id": "loropiana",       "name": "Loro Piana",          "slug": "loro-piana",       "city": "milan"},
    {"brand_id": "marni",           "name": "Marni",               "slug": "marni",            "city": "milan"},
    {"brand_id": "jilsander",       "name": "Jil Sander",          "slug": "jil-sander",       "city": "milan"},
    {"brand_id": "versace",         "name": "Versace",             "slug": "versace",          "city": "milan"},
    {"brand_id": "tods",            "name": "Tod's",               "slug": "tods",             "city": "milan"},
    {"brand_id": "etro",            "name": "Etro",                "slug": "etro",             "city": "milan"},
    {"brand_id": "kiton",           "name": "Kiton",               "slug": "kiton",            "city": "milan"},
    # London
    {"brand_id": "burberry",        "name": "Burberry",            "slug": "burberry",         "city": "london"},
    {"brand_id": "alexandermcqueen","name": "Alexander McQueen",   "slug": "alexander-mcqueen","city": "london"},
    {"brand_id": "jwanderson",      "name": "JW Anderson",         "slug": "jw-anderson",      "city": "london"},
    # New York
    {"brand_id": "marcjacobs",      "name": "Marc Jacobs",         "slug": "marc-jacobs",      "city": "new-york"},
]

MEN = [
    {"brand_id": "dior_men",        "name": "Dior Men",            "slug": "dior-homme",       "city": "paris"},
    {"brand_id": "hermes_men",      "name": "Hermès Men",          "slug": "hermes",           "city": "paris"},
    {"brand_id": "lv_men",          "name": "Louis Vuitton Men",   "slug": "louis-vuitton",    "city": "paris"},
    {"brand_id": "loewe_men",       "name": "Loewe Men",           "slug": "loewe",            "city": "paris"},
    {"brand_id": "valentino_men",   "name": "Valentino Men",       "slug": "valentino",        "city": "paris"},
    {"brand_id": "prada_men",       "name": "Prada Men",           "slug": "prada",            "city": "milan"},
    {"brand_id": "gucci_men",       "name": "Gucci Men",           "slug": "gucci",            "city": "milan"},
    {"brand_id": "zegna",           "name": "Zegna",               "slug": "ermenegildo-zegna","city": "milan"},
    {"brand_id": "brunellocucinelli_men","name":"Brunello Cucinelli Men","slug":"brunello-cucinelli","city":"milan"},
    {"brand_id": "kiton_men",       "name": "Kiton Men",           "slug": "kiton",            "city": "milan"},
    {"brand_id": "ferragamo_men",   "name": "Ferragamo Men",       "slug": "ferragamo",        "city": "milan"},
    {"brand_id": "canali",          "name": "Canali",              "slug": "canali",           "city": "milan"},
    {"brand_id": "burberry_men",    "name": "Burberry Men",        "slug": "burberry",         "city": "london"},
]


def season_has_data(brand_id, season_id):
    instances = graph._load("instances")
    return any(i["season_id"] == season_id for i in instances)


def fetch_brand(brand, gender_path):
    brand_id   = brand["brand_id"]
    name       = brand["name"]
    slug       = brand["slug"]
    city       = brand["city"]
    season_id  = f"{brand_id}_{PERIOD.lower()}{YEAR}"
    season_label = f"{PERIOD}{YEAR}"

    if season_has_data(brand_id, season_id):
        print(f"  [skip] {name} — already has data")
        return 0

    graph.add_brand(brand_id, name)
    graph.add_season(season_id, brand_id, YEAR, PERIOD, "Unknown")

    tw_slug = f"fall-winter-{YEAR}"
    url = f"https://www.tag-walk.com/en/collection/{gender_path}/{slug}/{tw_slug}?city={city}"

    print(f"  [fetch] {name}  {url}")
    try:
        text = fetch_show.fetch_tagwalk(url)
    except Exception as e:
        print(f"  [fail]  {name}: {e}")
        return 0

    import re
    look_urls = re.findall(r'Look \d+: (https://cdn\.tag-walk\.com/\S+)', text)
    if not look_urls:
        print(f"  [warn]  {name}: 0 look images")
        return 0

    print(f"           {len(look_urls)} looks → running vision...")
    graph.add_season(season_id, brand_id, YEAR, PERIOD, "Unknown", look_image_urls=look_urls)

    codes = vision_extract.extract(look_urls, name, season_label, url)
    codes = chk.check_taxonomy_only(codes)

    added = 0
    for code in codes:
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

    print(f"           {added} codes stored  [{graph.summary()['instances']} total]")
    return added


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--gender", choices=["women", "men", "both"], default="both")
    args = p.parse_args()

    todo_w = WOMEN if args.gender in ("women", "both") else []
    todo_m = MEN   if args.gender in ("men",   "both") else []

    total_brands = len(todo_w) + len(todo_m)
    print(f"\nPre-warming AW{YEAR} — {total_brands} brands\n")

    done = errors = 0
    for brand in todo_w:
        result = fetch_brand(brand, "woman")
        if result > 0:
            done += 1
        elif result == 0:
            errors += 1

    for brand in todo_m:
        result = fetch_brand(brand, "man")
        if result > 0:
            done += 1
        elif result == 0:
            errors += 1

    print(f"\nDone — {done} brands with data, {errors} skipped/failed")
    print(f"Graph: {graph.summary()}")
