#!/usr/bin/env python3
"""
Tags Database Migration Script
Populates the Tags DB, migrates deinfluence multi_select → relations,
and tags wardrobe entries from their story content.

Run once the Tags DB is accessible:
  python3 deinfluence_tag_migration.py

Or in parts:
  python3 deinfluence_tag_migration.py --populate   # create tags only
  python3 deinfluence_tag_migration.py --deinfluence # migrate deinfluence
  python3 deinfluence_tag_migration.py --wardrobe    # tag wardrobe entries
"""

import os, sys, re, json, requests, anthropic
from dotenv import load_dotenv

load_dotenv("/Users/lisa/lookbook-stories/.env")

TOKEN = os.environ["NOTION_TOKEN"]
H = {"Authorization": f"Bearer {TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}

DEINFLUENCE_DB   = "349ccd15-cda1-8030-876a-dd491c9b992c"
WARDROBE_DB      = "ad079964-9690-43ae-9fa8-5a4f3ca1a9ee"
TAGS_DB          = "34accd15-cda1-805b-8ab7-e8a4f76f74c6"  # update if new DB created

# ─── FULL TAG VOCABULARY ────────────────────────────────────────────────────

TAGS = [
    # branding
    {"name": "visible-logo",           "type": "branding",      "description": "The logo is prominent and unavoidable"},
    {"name": "loud-branding",          "type": "branding",      "description": "Brand identity is loud in a performative way"},
    {"name": "logo-fatigue",           "type": "branding",      "description": "General tiredness with recognisable brand signalling"},

    # quality
    {"name": "craftsmanship",          "type": "quality",       "description": "Exceptional quality of construction, materials, or making"},
    {"name": "condition",              "type": "quality",       "description": "Item's physical condition is a concern"},
    {"name": "misleading-material-claim", "type": "quality",    "description": "Listing misrepresented the fabric or material"},

    # construction
    {"name": "natural-patina",         "type": "construction",  "description": "Aged character (leather, wear) that can't be faked"},
    {"name": "pattern-integrity",      "type": "construction",  "description": "The pattern/print is handled with exceptional care in construction"},

    # material
    {"name": "wrong-fabric-for-use-case", "type": "material",  "description": "Material doesn't suit how it would actually be worn"},
    {"name": "wrong-colour",           "type": "material",      "description": "Colour doesn't work for the wardrobe or doesn't suit"},

    # value
    {"name": "investment-piece",       "type": "value",         "description": "Likely to hold or gain value; justifiable long-term buy"},
    {"name": "price",                  "type": "value",         "description": "The price is the primary blocker or draw"},
    {"name": "have-better-in-wardrobe","type": "overlap",       "description": "Already own something that outperforms this — would be a downgrade"},

    # overlap
    {"name": "have-equivalent-in-wardrobe", "type": "overlap",  "description": "Already own something functionally and aesthetically equivalent — direct duplicate"},

    # identity
    {"name": "doesnt-fit-my-style",    "type": "identity",      "description": "Aesthetically appealing but not who she is — identity gap"},
    {"name": "doesnt-fit-my-wardrobe", "type": "identity",      "description": "No natural home for it; nothing to wear it with"},
    {"name": "versatile",              "type": "identity",      "description": "Works across many contexts in the wardrobe"},
    {"name": "timeless-silhouette",    "type": "identity",      "description": "The shape or cut is not trend-dependent"},

    # designer
    {"name": "love-the-designer",      "type": "designer",      "description": "Drawn to the specific creative person and their vision"},
    {"name": "brand-legacy",           "type": "designer",      "description": "Drawn to the brand's institutional history and heritage"},
    {"name": "brand-discovery",        "type": "designer",      "description": "Gateway piece — want to learn more about this brand"},

    # silhouette
    {"name": "too-common-silhouette",  "type": "silhouette",    "description": "Shape is generic, nothing distinctive"},
    {"name": "derivative-design",      "type": "silhouette",    "description": "Design is imitative; lacks its own point of view"},

    # unique
    {"name": "vintage-provenance",     "type": "unique",        "description": "Documented era, date, or origin story that adds value"},
    {"name": "rare-find",              "type": "unique",        "description": "Hard to source; unlikely to appear again"},

    # occasion
    {"name": "travel-worthy",         "type": "occasion",       "description": "Elevated enough to bring on a trip; not for every day"},

    # size
    {"name": "size-wrong",            "type": "size",           "description": "The sizing doesn't work"},

    # emotion
    {"name": "sentimental",           "type": "emotion",        "description": "Emotional attachment or personal story"},
    {"name": "gifted",                "type": "emotion",        "description": "Given as a gift or bought as a gift for someone"},

    # colour (as a positive draw — the colour itself is the appeal)
    {"name": "colour",                "type": "colour",         "description": "The specific colour is a primary reason — positive draw"},
]

APPROVED_YES = {
    "vintage-provenance", "investment-piece", "natural-patina", "travel-worthy",
    "craftsmanship", "rare-find", "brand-legacy", "versatile", "timeless-silhouette",
    "love-the-designer", "brand-discovery", "pattern-integrity", "colour",
    "sentimental", "gifted",
}
APPROVED_NO = {
    "visible-logo", "loud-branding", "logo-fatigue", "price", "condition",
    "size-wrong", "wrong-colour", "wrong-fabric-for-use-case",
    "misleading-material-claim", "too-common-silhouette", "derivative-design",
    "doesnt-fit-my-wardrobe", "doesnt-fit-my-style",
    "have-equivalent-in-wardrobe", "have-better-in-wardrobe",
}
APPROVED_OWN = APPROVED_YES  # wardrobe "why I own it" uses same yes vocabulary


# ─── HELPERS ────────────────────────────────────────────────────────────────

def query_db(db_id):
    pages, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor: body["start_cursor"] = cursor
        r = requests.post(f"https://api.notion.com/v1/databases/{db_id}/query", headers=H, json=body)
        r.raise_for_status()
        d = r.json()
        pages.extend(d.get("results", []))
        if not d.get("has_more"): break
        cursor = d.get("next_cursor")
    return pages


def get_story(page_id):
    """Extract 'The Story' or 'Why bought' text from wardrobe page body tables."""
    blocks = requests.get(f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=50", headers=H).json()
    for b in blocks.get("results", []):
        if b["type"] == "table":
            rows = requests.get(f"https://api.notion.com/v1/blocks/{b['id']}/children", headers=H).json()
            for row in rows.get("results", []):
                cells = row.get("table_row", {}).get("cells", [])
                if len(cells) >= 2:
                    key = "".join(r.get("plain_text","") for r in cells[0]).lower()
                    val = "".join(r.get("plain_text","") for r in cells[1])
                    if any(w in key for w in ["story", "why", "bought", "own"]) and val.strip():
                        return val.strip()
    return None


def ask_claude_tags(title, story, context="wardrobe"):
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    yes_pool = sorted(APPROVED_YES)
    no_pool  = sorted(APPROVED_NO)

    if context == "wardrobe":
        instruction = f"""Item: {title}
Owner's story: {story}

Tag this wardrobe piece. Use ONLY tags from the approved list.
Return JSON: {{"why_own": ["tag", ...], "what_id_change": ["tag", ...]}}
why_own = reasons she loves/bought it (from: {yes_pool})
what_id_change = things she'd change or doesn't love (from: {no_pool})"""
    else:
        instruction = f"""Item: {title}
Notes: {story}

Return JSON: {{"why_considering": ["tag", ...], "why_no": ["tag", ...]}}
why_considering from: {yes_pool}
why_no from: {no_pool}"""

    r = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": instruction}]
    )
    text = r.content[0].text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i+1])
    raise ValueError(f"No JSON in: {text[:200]}")


# ─── STEP 1: POPULATE TAGS DB ───────────────────────────────────────────────

def populate_tags_db():
    """Create one page per tag in the Tags DB. Returns {tag_name: page_id}."""
    print("Populating Tags database...")
    tag_map = {}

    for tag in TAGS:
        r = requests.post("https://api.notion.com/v1/pages", headers=H, json={
            "parent": {"database_id": TAGS_DB},
            "properties": {
                "Name": {"title": [{"text": {"content": tag["name"]}}]},
            }
        })
        if r.status_code in (200, 201):
            pid = r.json()["id"]
            tag_map[tag["name"]] = pid
            print(f"  ✓ {tag['name']} ({tag['type']})")
        else:
            print(f"  ✗ {tag['name']}: {r.json().get('message','')[:80]}")

    # Save map to disk so migration steps can use it
    with open("/Users/lisa/lookbook-stories/tag_id_map.json", "w") as f:
        json.dump(tag_map, f, indent=2)
    print(f"\nTag map saved ({len(tag_map)} tags)")
    return tag_map


# ─── STEP 2: MIGRATE DEINFLUENCE ────────────────────────────────────────────

def migrate_deinfluence(tag_map):
    """Convert multi_select tags on deinfluence entries to Tag relations."""
    print("\nMigrating deinfluence entries...")
    pages = query_db(DEINFLUENCE_DB)

    for page in pages:
        props = page["properties"]
        title = props.get("Item - Third Best", {}).get("title", [{}])[0].get("plain_text", "?")

        yes_tags = [t["name"] for t in props.get("Why i was considering", {}).get("multi_select", [])]
        no_tags  = [t["name"] for t in props.get("Why ultimately no", {}).get("multi_select", [])]
        all_tags = list(dict.fromkeys(yes_tags + no_tags))  # deduplicated, ordered

        relation_ids = [{"id": tag_map[t]} for t in all_tags if t in tag_map]
        if not relation_ids:
            continue

        r = requests.patch(f"https://api.notion.com/v1/pages/{page['id']}", headers=H, json={
            "properties": {"Tag": {"relation": relation_ids}}
        })
        print(f"  {'✓' if r.status_code == 200 else '✗'} {title[:55]}  [{', '.join(all_tags[:4])}...]")


# ─── STEP 3: TAG WARDROBE ENTRIES ───────────────────────────────────────────

def tag_wardrobe(tag_map, limit=15):
    """Tag the most recent wardrobe entries using their story content."""
    print(f"\nTagging last {limit} wardrobe entries...")
    pages = requests.post(f"https://api.notion.com/v1/databases/{WARDROBE_DB}/query",
        headers=H, json={"sorts": [{"property": "Added", "direction": "descending"}],
                         "page_size": limit}).json().get("results", [])

    for page in pages:
        title = page["properties"].get("Second best", {}).get("title", [{}])[0].get("plain_text", "?")
        existing = page["properties"].get("Why i own it", {}).get("relation", [])
        if existing:
            print(f"  — skip (already tagged): {title[:55]}")
            continue

        story = get_story(page["id"])
        if not story:
            print(f"  ✗ no story: {title[:55]}")
            continue

        print(f"  Tagging: {title[:55]}")
        tags = ask_claude_tags(title, story, context="wardrobe")
        own_tags = tags.get("why_own", [])
        relation_ids = [{"id": tag_map[t]} for t in own_tags if t in tag_map]

        if relation_ids:
            r = requests.patch(f"https://api.notion.com/v1/pages/{page['id']}", headers=H, json={
                "properties": {"Why i own it": {"relation": relation_ids}}
            })
            print(f"    → {', '.join(own_tags)}")


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--all"

    if mode in ("--populate", "--all"):
        tag_map = populate_tags_db()
    else:
        try:
            with open("/Users/lisa/lookbook-stories/tag_id_map.json") as f:
                tag_map = json.load(f)
            print(f"Loaded tag map ({len(tag_map)} tags)")
        except FileNotFoundError:
            print("Run --populate first to create tags and generate tag_id_map.json")
            sys.exit(1)

    if mode in ("--deinfluence", "--all"):
        migrate_deinfluence(tag_map)

    if mode in ("--wardrobe", "--all"):
        tag_wardrobe(tag_map)


if __name__ == "__main__":
    main()
