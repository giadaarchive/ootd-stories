"""
Playwright browser session for tag-walk (and other JS-rendered sites).
Launches a persistent headless Chromium with the TWFOSID session cookie injected.
The browser stays alive across multiple fetch calls — no repeated startup cost.

Usage (called internally by fetch_show.py):
    from browser_session import get_page_html
    html = get_page_html("https://www.tag-walk.com/en/collection/woman/akris/fall-winter-2026")

Environment:
    TWFOSID_TAGWALK  — session cookie value (set in .env)

The session persists for the lifetime of the Python process.
For cron/script use, the browser starts fresh each run but auth is injected via cookie
so no login step is needed.
"""
import os
import time

_browser = None
_context = None
_playwright = None


def _start():
    global _browser, _context, _playwright
    if _browser is not None:
        return

    from playwright.sync_api import sync_playwright

    cookie_value = os.environ.get("TWFOSID_TAGWALK", "")
    if not cookie_value:
        raise EnvironmentError(
            "TWFOSID_TAGWALK not set in .env\n"
            "Get it from: Chrome DevTools → Application → Cookies → tag-walk.com → TWFOSID"
        )

    _playwright = sync_playwright().start()
    _browser = _playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    _context = _browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        locale="en-US",
        viewport={"width": 1280, "height": 900},
    )

    # Inject the TWFOSID session cookie so we are already logged in
    _context.add_cookies([{
        "name":   "TWFOSID",
        "value":  cookie_value,
        "domain": ".tag-walk.com",
        "path":   "/",
        "secure": True,
        "httpOnly": True,
    }])


def get_page_html(url, wait_selector=None, wait_ms=3000):
    """
    Fetch a JS-rendered page and return its fully rendered HTML.

    wait_selector — CSS selector to wait for before capturing HTML (optional)
    wait_ms       — additional ms to wait after page load for dynamic content
    """
    _start()

    page = _context.new_page()
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)

        if wait_selector:
            try:
                page.wait_for_selector(wait_selector, timeout=10000)
            except Exception:
                pass   # selector optional — continue anyway

        if wait_ms:
            time.sleep(wait_ms / 1000)

        return page.content()
    finally:
        page.close()


def get_tagwalk_collection(designer_slug, season_slug, gender="woman", city=None):
    """
    Fetch a tag-walk collection page and extract look data.

    Returns dict:
      html        — full rendered HTML
      looks       — list of {image_url, tags, look_number}
      tag_summary — aggregated tags across all looks
    """
    params = f"?city={city}" if city else ""
    url = f"https://www.tag-walk.com/en/collection/{gender}/{designer_slug}/{season_slug}{params}"

    # Wait for the look grid to render
    html = get_page_html(url, wait_selector=".look-card, .look, [class*='look']", wait_ms=4000)
    looks, tag_summary = _parse_collection_html(html)
    return {"url": url, "html": html, "looks": looks, "tag_summary": tag_summary}


def _parse_collection_html(html):
    """Parse the rendered collection page to extract look data and tags."""
    import re, json

    looks = []
    tag_summary = {}

    # 1. Extract look images (cdn.tag-walk.com URLs that contain look numbers)
    img_urls = re.findall(r'https://cdn\.tag-walk\.com/(?:photos|looks)/[^\s"\'<>]+', html)
    for url in img_urls:
        num_m = re.search(r"/(\d{4,6})\.", url)
        if num_m:
            looks.append({"look_number": int(num_m.group(1)), "image_url": url, "tags": []})

    # 2. Extract tag text — tag-walk renders tags as clickable labels
    # Pattern: text inside tag anchor elements
    tag_texts = re.findall(
        r'<(?:a|span|li)[^>]*class=["\'][^"\']*(?:tag|label|filter)[^"\']*["\'][^>]*>([\w\s,\-/]+)</',
        html, re.IGNORECASE
    )
    for t in tag_texts:
        t = t.strip()
        if 2 < len(t) < 40 and not any(skip in t.lower() for skip in ["login", "sign", "share", "save"]):
            tag_summary[t] = tag_summary.get(t, 0) + 1

    # 3. Try to find any embedded JSON with look/tag data
    json_matches = re.findall(r'window\.__(?:DATA|INITIAL_STATE|NUXT)__\s*=\s*(\{.*?\});', html, re.DOTALL)
    for blob in json_matches[:2]:
        try:
            data = json.loads(blob)
            _harvest_tags(data, tag_summary)
        except (json.JSONDecodeError, RecursionError):
            pass

    return looks, tag_summary


def _harvest_tags(obj, result, depth=0):
    """Recursively find tag/color/silhouette arrays in JSON."""
    if depth > 5:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in ("tags", "colors", "silhouettes", "prints", "fabrics", "labels"):
                if isinstance(v, list):
                    for item in v:
                        if isinstance(item, str):
                            result[item] = result.get(item, 0) + 1
                        elif isinstance(item, dict) and "name" in item:
                            result[item["name"]] = result.get(item["name"], 0) + 1
            else:
                _harvest_tags(v, result, depth + 1)
    elif isinstance(obj, list):
        for item in obj[:20]:
            _harvest_tags(item, result, depth + 1)


def close():
    """Cleanly shut down the browser. Call at script end if needed."""
    global _browser, _context, _playwright
    if _context:
        _context.close()
        _context = None
    if _browser:
        _browser.close()
        _browser = None
    if _playwright:
        _playwright.stop()
        _playwright = None
