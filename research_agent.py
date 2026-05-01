"""
Agentic research pipeline for heritage notes.

Pipeline:
  1. Qwen-VL analyzes item images from Notion → visual description
  2. Qwen-2.5-72B runs a research loop using web_search + fetch_url +
     search_auction_houses + search_editorial + search_museum_collections +
     visual_search + search_own_collection tools until it has enough to write
     all four heritage sections
  3. Returns structured research notes for heritage.py to draft from

Tools available to the research agent:
  web_search(query)                          — DuckDuckGo search, returns top snippets
  fetch_url(url)                             — fetches a web page and returns clean text
  search_auction_houses(brand, item_description, year) — targeted auction/resale searches
  search_editorial(brand, year)              — Vogue/WWD editorial snippets
  search_museum_collections(query)           — V&A API object search
  visual_search(image_url)                   — SerpAPI Google Lens similar-image search
  search_own_collection(brand, year)         — Notion DB query for owner's other pieces
"""

import json
import os
import re
import sys
import time

import requests as http_requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

import llm as llm_module
from dotenv import load_dotenv

load_dotenv()

VISION_MODEL    = "qwen/qwen2.5-vl-72b-instruct"
RESEARCH_MODEL  = "qwen/qwen-2.5-72b-instruct"

MAX_RESEARCH_ROUNDS = 8   # max tool-call rounds before forcing a draft
MAX_FETCH_CHARS     = 4000

SERPAPI_KEY   = os.environ.get("SERPAPI_KEY", "")
NOTION_TOKEN  = os.environ.get("NOTION_TOKEN", "")
COLLECTION_DB_ID = "ad079964969043ae9fa85a4f3ca1a9ee"

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


# ── Tool implementations ──────────────────────────────────────────────────────

def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Search DuckDuckGo and return list of {title, url, snippet}."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [{"title": r.get("title",""), "url": r.get("href",""), "snippet": r.get("body","")} for r in results]
    except Exception as e:
        return [{"error": str(e)}]


def fetch_url(url: str) -> str:
    """Fetch a web page and return clean plain text (capped)."""
    try:
        r = http_requests.get(url, timeout=12, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        })
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text[:MAX_FETCH_CHARS]
    except Exception as e:
        return f"Error fetching {url}: {e}"


def search_auction_houses(brand: str, item_description: str, year: str = "") -> list[dict]:
    """
    Targeted DuckDuckGo searches across major auction houses and resale platforms.
    Returns merged list of {title, url, snippet, source}.
    """
    sites = [
        ("Christie's",  f"site:christies.com {brand} {item_description}"),
        ("Sotheby's",   f"site:sothebys.com {brand} {item_description}"),
        ("Bonhams",     f"site:bonhams.com {brand} {item_description}"),
        ("1stDibs",     f"site:1stdibs.com {brand} {item_description}"),
        ("Vestiaire",   f"site:vestiaire.com {brand} {item_description}"),
    ]
    merged = []
    for source_name, query in sites:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=3))
            for r in results:
                merged.append({
                    "source": source_name,
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
            time.sleep(0.3)
        except Exception as e:
            merged.append({"source": source_name, "error": str(e)})
    return merged


def search_editorial(brand: str, year: str) -> list[dict]:
    """
    DuckDuckGo snippet-only searches for editorial coverage on Vogue and WWD.
    Returns snippets only (no fetch — these sites are paywalled).
    """
    queries = [
        ("Vogue", f"site:vogue.com {brand} {year} collection"),
        ("WWD",   f"site:wwd.com {brand} {year}"),
    ]
    results = []
    for source_name, query in queries:
        try:
            with DDGS() as ddgs:
                hits = list(ddgs.text(query, max_results=3))
            for h in hits:
                results.append({
                    "source": source_name,
                    "title": h.get("title", ""),
                    "snippet": h.get("body", ""),
                    "url": h.get("href", ""),
                })
            time.sleep(0.3)
        except Exception as e:
            results.append({"source": source_name, "error": str(e)})
    return results


def search_museum_collections(query: str) -> list[dict]:
    """
    Search the V&A (Victoria and Albert Museum) open API for related objects.
    Free, no API key required. Returns list of {title, date, materials, objectType, url}.
    """
    try:
        url = f"https://api.vam.ac.uk/v2/objects/search?q={http_requests.utils.quote(query)}&page_size=5&images_exist=true"
        r = http_requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        records = data.get("records", [])
        if not records:
            print(f"     [museum] V&A: 0 results for '{query}' — skipping")
            return []
        results = []
        for rec in records:
            sys_no = rec.get("systemNumber", "")
            results.append({
                "title": rec.get("_primaryTitle", rec.get("objectType", "")),
                "date": rec.get("_primaryDate", ""),
                "materials": rec.get("materials", ""),
                "objectType": rec.get("objectType", ""),
                "url": f"https://collections.vam.ac.uk/item/{sys_no}/" if sys_no else "",
            })
        return results
    except Exception as e:
        print(f"     [museum] V&A search failed: {e} — continuing")
        return []


def visual_search(image_url: str) -> dict:
    """
    SerpAPI Google Lens search for visually similar items.
    Requires SERPAPI_KEY in environment. Gracefully skips if not set.
    """
    if not SERPAPI_KEY:
        return {"error": "SERPAPI_KEY not set — add to .env to enable visual search"}
    try:
        params = {
            "engine": "google_lens",
            "url": image_url,
            "api_key": SERPAPI_KEY,
        }
        r = http_requests.get("https://serpapi.com/search.json", params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        visual_matches = data.get("visual_matches", [])
        return {
            "matches_found": len(visual_matches),
            "top_matches": [
                {
                    "title": m.get("title", ""),
                    "source": m.get("source", ""),
                    "link": m.get("link", ""),
                    "price": m.get("price", {}).get("extracted_value", "") if isinstance(m.get("price"), dict) else "",
                }
                for m in visual_matches[:8]
            ],
        }
    except Exception as e:
        return {"error": f"visual_search failed: {e}"}


def search_own_collection(brand: str, year: str) -> list[dict]:
    """
    Query the owner's Notion collection DB for other pieces from the same brand.
    Returns list of {name, year, category}.
    """
    if not NOTION_TOKEN:
        return [{"error": "NOTION_TOKEN not set"}]
    try:
        body = {
            "page_size": 20,
            "filter": {
                "property": "Designer",
                "relation": {"is_not_empty": True},
            },
        }
        r = http_requests.post(
            f"https://api.notion.com/v1/databases/{COLLECTION_DB_ID}/query",
            headers=NOTION_HEADERS,
            json=body,
            timeout=10,
        )
        r.raise_for_status()
        pages = r.json().get("results", [])

        results = []
        brand_lower = brand.lower()
        for page in pages:
            props = page.get("properties", {})
            # Match by designer name in page title or Designer relation
            title_prop = next((v for v in props.values() if v.get("type") == "title"), None)
            name = (
                title_prop["title"][0].get("plain_text", "")
                if title_prop and title_prop.get("title")
                else ""
            )
            # Check designer relation names
            designer_rel = props.get("Designer", {}).get("relation", [])
            # Use name matching heuristic — pieces with brand in title
            if brand_lower in name.lower() or brand_lower in str(designer_rel).lower():
                year_date = props.get("Year It's Made (first hand)", {}).get("date", {})
                piece_year = year_date.get("start", "")[:4] if year_date else ""
                cat_sel = props.get("Category", {}).get("select")
                category = cat_sel["name"] if cat_sel else ""
                results.append({"name": name, "year": piece_year, "category": category})
        return results if results else [{"info": f"No other {brand} pieces found in collection"}]
    except Exception as e:
        return [{"error": f"search_own_collection failed: {e}"}]


# ── Tool definitions for OpenRouter function calling ─────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for information about fashion houses, creative directors, "
                "archive pieces, material history, or any factual detail needed for heritage research."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "max_results": {"type": "integer", "description": "Number of results (default 5)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch the full text of a web page URL for deeper reading.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to fetch"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_auction_houses",
            "description": (
                "Search Christie's, Sotheby's, Bonhams, 1stDibs, and Vestiaire Collective "
                "for comparable archive pieces. Use to assess rarity and find market comps."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "brand": {"type": "string", "description": "The fashion house/brand name"},
                    "item_description": {"type": "string", "description": "Brief description of the item type (e.g. 'cashmere coat' or 'silk scarf')"},
                    "year": {"type": "string", "description": "Approximate year of production (optional)"},
                },
                "required": ["brand", "item_description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_editorial",
            "description": (
                "Search Vogue and WWD for editorial coverage of a brand/season. "
                "Returns snippets only — useful for seasonal context without fetching paywalled pages."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "brand": {"type": "string", "description": "The fashion house/brand name"},
                    "year": {"type": "string", "description": "Year of the collection"},
                },
                "required": ["brand", "year"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_museum_collections",
            "description": (
                "Search the Victoria and Albert Museum open API for related fashion objects. "
                "Good for historical context, dating reference, and material verification."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (e.g. 'Hermès cashmere coat 1980s')"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "visual_search",
            "description": (
                "Use Google Lens (via SerpAPI) to find visually similar items from the item images. "
                "Helps identify comparable pieces and verify visual details."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "image_url": {"type": "string", "description": "Public URL of the item image to search"},
                },
                "required": ["image_url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_own_collection",
            "description": (
                "Query the owner's Notion collection database for other pieces from the same brand. "
                "Provides context on what else from this house is in the archive."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "brand": {"type": "string", "description": "The fashion house/brand name"},
                    "year": {"type": "string", "description": "Year of the piece being researched (optional context)"},
                },
                "required": ["brand"],
            },
        },
    },
]


# ── Step 1: Visual analysis of item images ────────────────────────────────────

VISION_SYSTEM = """\
You are analyzing images of a luxury fashion archive piece for a heritage research project.

Describe in precise detail what you observe:
- Item type, silhouette, length, fit
- Colours — exact shades, not just "dark" or "light"
- Materials — texture, weight, weave or knit structure if visible
- Hardware — closures, buttons, buckles: material, finish, shape
- Label details — any visible brand label, country of origin, composition tag, date codes
- Construction — visible seams, hand-finishing, lining material if visible
- Condition — any visible wear, discolouration, repairs
- Any other identifying marks or details

Be specific and factual. If something is not clearly visible, say so rather than guessing.\
"""

def analyze_images(image_urls: list[str], brand: str, item_name: str) -> str:
    """Run Qwen-VL on item images and return a detailed visual description."""
    if not image_urls:
        return "No images available."
    print(f"     [vision] analyzing {len(image_urls)} image(s) with {VISION_MODEL}")
    user_text = (
        f"Item: {brand} — {item_name}\n"
        f"Please analyze these images in detail for heritage research purposes."
    )
    return llm_module.call_vision(VISION_SYSTEM, user_text, image_urls, max_tokens=1200, model=VISION_MODEL)


# ── Step 2: Agentic research loop ─────────────────────────────────────────────

RESEARCH_SYSTEM = """\
You are a fashion historian and archive researcher. Your job is to gather factual information
about a specific luxury fashion piece so that a heritage document can be written.

You have access to:
  web_search(query)                           — search the web for information
  fetch_url(url)                              — read a specific page in full
  search_auction_houses(brand, item_description, year) — Christie's, Sotheby's, Bonhams, 1stDibs, Vestiaire
  search_editorial(brand, year)               — Vogue and WWD editorial snippets (snippets only, no fetch)
  search_museum_collections(query)            — V&A Museum API for historical fashion objects
  visual_search(image_url)                    — Google Lens to find visually similar pieces
  search_own_collection(brand, year)          — the owner's Notion archive for other pieces from this brand

Research strategy:
1. Identify the exact creative director at the house during the piece's year of production
2. Research what defined that era at the house — aesthetic, materials, silhouette philosophy
3. Find information about the specific materials used (cashmere sourcing, mink handling, etc.)
4. Search for similar archive pieces from that period to cross-reference details
5. Research any visible label markings, date codes, or construction methods to verify dating

REQUIRED research tasks:
- Determine the EXACT season (Fall/Winter or Spring/Summer + year) based on materials and collection timing
- Assess RARITY: search secondary market (Christie's, Sotheby's, 1stDibs, Vestiaire, Etsy) and count how
  many comparable pieces exist. This is critical — the archive focuses on extremely rare, unique,
  one-of-a-kind archival pieces. Rate as:
    Very Rare  (<3 comparable pieces found)
    Rare       (3–10 comparable pieces found)
    Uncommon   (10–30 comparable pieces found)
    Available  (30+ comparable pieces found)
- Check authentication markers from images: label typography, hardware finish, stitching patterns,
  date codes, country of origin format — these help verify age and authenticity
- Generate conservation recommendations specifically for Singapore climate (hot 28–34°C,
  humidity 70–90% year-round). Be specific to the materials identified.

Be thorough but efficient. Use 4–8 tool calls. Once you have enough to support all four heritage
sections (about_this_piece, design_language, craft_and_materials, historical_context), stop
searching and return a structured research summary.

Return your final output as JSON with exactly these keys:
{
  "visual_details": "...",
  "creative_director": "name and verified years",
  "season_attribution": "e.g. Fall/Winter 1987",
  "era_aesthetic": "...",
  "material_notes": "...",
  "historical_context": "...",
  "rarity_assessment": {
    "rating": "Very Rare | Rare | Uncommon | Available",
    "comparable_pieces_found": 2,
    "evidence": "2 comparable pieces found on Christie's and 1stDibs",
    "market_listings": [{"source": "Christie's", "description": "...", "price": "USD 4,200", "url": "..."}]
  },
  "authentication_signals": ["label typography consistent with 1980s production", "horse-carriage logo pre-1995 version"],
  "conservation_notes": "Singapore-specific storage and care instructions",
  "editorial_mentions": ["snippet from Vogue 1987 if found"],
  "museum_references": ["V&A object if found"],
  "own_collection_context": ["Other Hermès pieces owned: ..."],
  "sources": ["url1", "url2"]
}
Return only valid JSON when done — no markdown.\
"""


def _dispatch_tool(name: str, args: dict) -> str:
    if name == "web_search":
        results = web_search(args["query"], args.get("max_results", 5))
        return json.dumps(results, ensure_ascii=False)
    elif name == "fetch_url":
        return fetch_url(args["url"])
    elif name == "search_auction_houses":
        results = search_auction_houses(
            args["brand"],
            args["item_description"],
            args.get("year", ""),
        )
        return json.dumps(results, ensure_ascii=False)
    elif name == "search_editorial":
        results = search_editorial(args["brand"], args["year"])
        return json.dumps(results, ensure_ascii=False)
    elif name == "search_museum_collections":
        results = search_museum_collections(args["query"])
        return json.dumps(results, ensure_ascii=False)
    elif name == "visual_search":
        results = visual_search(args["image_url"])
        return json.dumps(results, ensure_ascii=False)
    elif name == "search_own_collection":
        results = search_own_collection(args["brand"], args.get("year", ""))
        return json.dumps(results, ensure_ascii=False)
    return f"Unknown tool: {name}"


def run_research_loop(brand: str, item_name: str, year: str, category: str,
                      material: str, visual_description: str) -> dict:
    """
    Agentic research loop — Qwen calls tools until done,
    then returns structured research notes.
    """
    from openai import OpenAI
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
    )

    user_msg = (
        f"Research this piece:\n"
        f"Brand: {brand}\n"
        f"Item: {item_name}\n"
        f"Year made: {year}\n"
        f"Category: {category}\n"
        f"Materials (from label/listing): {material}\n\n"
        f"Visual analysis from images:\n{visual_description}\n\n"
        f"Gather the research needed to write a complete heritage document. "
        f"Make sure to call search_auction_houses to assess rarity, and include "
        f"Singapore-specific conservation notes."
    )

    messages = [
        {"role": "system", "content": RESEARCH_SYSTEM},
        {"role": "user",   "content": user_msg},
    ]

    total_in = total_out = 0

    for round_num in range(MAX_RESEARCH_ROUNDS):
        resp = client.chat.completions.create(
            model=RESEARCH_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=1500,
        )
        msg = resp.choices[0].message
        u   = resp.usage
        total_in  += u.prompt_tokens
        total_out += u.completion_tokens

        # If no tool calls → model is done, extract the JSON
        if not msg.tool_calls:
            raw = msg.content.strip()
            print(f"     [research] {round_num+1} rounds, {total_in} in / {total_out} out")
            llm_module._log_cost(RESEARCH_MODEL, total_in, total_out)
            raw = raw.lstrip("```json").lstrip("```").rstrip("```").strip()
            try:
                return json.loads(raw)
            except Exception:
                return {"raw_notes": raw, "sources": []}

        # Execute each tool call
        messages.append({"role": "assistant", "content": msg.content, "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls
        ]})

        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            first_val = str(list(args.values())[0])[:60] if args else ""
            print(f"     [tool] {tc.function.name}({first_val})")
            result = _dispatch_tool(tc.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
        time.sleep(0.5)

    # Max rounds hit — ask for summary with what we have
    messages.append({"role": "user", "content": "Summarize your research findings as JSON now."})
    resp = client.chat.completions.create(model=RESEARCH_MODEL, messages=messages, max_tokens=1500)
    raw = resp.choices[0].message.content.strip()
    llm_module._log_cost(RESEARCH_MODEL, resp.usage.prompt_tokens, resp.usage.completion_tokens)
    raw = raw.lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        return json.loads(raw)
    except Exception:
        return {"raw_notes": raw, "sources": []}


# ── Public entry point ────────────────────────────────────────────────────────

def research(brand: str, item_name: str, year: str, category: str,
             material: str, image_urls: list[str]) -> dict:
    """
    Full research pipeline:
      1. Visual analysis of images
      2. Agentic web research loop with auction, editorial, museum, and collection tools
    Returns research notes dict for heritage.py to draft from.
    """
    print(f"     [research agent] starting for {brand} — {item_name}")

    # Step 1: visual analysis
    visual_desc = analyze_images(image_urls, brand, item_name)
    print(f"     [vision] done — {len(visual_desc)} chars")

    # Step 2: web research
    notes = run_research_loop(brand, item_name, year, category, material, visual_desc)
    notes["visual_description"] = visual_desc
    return notes
