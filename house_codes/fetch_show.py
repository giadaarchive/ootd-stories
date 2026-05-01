"""
Fetch and clean fashion show data from multiple sources:
  - Brand website URL (public, cached)
  - Tag-walk collection page (Playwright browser session, cached)
  - YouTube video metadata + description (yt-dlp)
  - Raw pasted text

All URL fetches are disk-cached (7-day TTL for brand sites, 24h for tag-walk).
"""
import json
import os
import re
import subprocess
import sys

try:
    import requests
except ImportError:
    print("requests not installed — run: pip install requests", file=sys.stderr)
    raise

import cache as cache_mod

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# ── Public URL (with cache) ───────────────────────────────────────────────────

def fetch_url(url, timeout=20, force=False):
    """Fetch any public URL. Returns cleaned plain text. Cached 7 days."""
    if not force:
        cached = cache_mod.get("url", url)
        if cached:
            print(f"     [cache hit] {url[:60]}")
            return cached

    r = requests.get(url, headers=_HEADERS, timeout=timeout)
    r.raise_for_status()
    text = _clean_html(r.text)
    cache_mod.set("url", url, text, ttl_days=7)
    return text


def fetch_text(raw):
    """Accept pre-provided text (manually pasted or piped)."""
    return raw.strip()


# ── Tag-walk (Playwright browser session, with cache) ─────────────────────────

def fetch_tagwalk(url, force=False):
    """
    Fetch tag-walk collection page using the TWFOSID session cookie.
    The collection page is server-side rendered — no Playwright needed.

    Returns: plain text block with look count + image URLs embedded as metadata.
    CDN look images are publicly accessible (no auth needed) — stored for Phase 2 vision.

    Requires: TWFOSID_TAGWALK in .env
    """
    if not force:
        cached = cache_mod.get("tagwalk", url)
        if cached:
            print(f"     [cache hit] tagwalk {url[:60]}")
            return cached

    cookie_value = os.environ.get("TWFOSID_TAGWALK", "")
    if not cookie_value:
        raise EnvironmentError(
            "TWFOSID_TAGWALK not set in .env\n"
            "Get from: Chrome DevTools → Application → Cookies → tag-walk.com → TWFOSID"
        )

    headers = {
        **_HEADERS,
        "Cookie": f"TWFOSID={cookie_value}",
    }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    html = r.text

    text, look_urls = _parse_tagwalk_html(html)

    # Prepend structured metadata for LLM
    meta_lines = [f"Source: tag-walk collection — {url}"]
    if look_urls:
        meta_lines.append(f"Total looks in collection: {len(look_urls)}")
        meta_lines.append("Look image URLs (publicly accessible CDN, use for Phase 2 visual analysis):")
        for i, img_url in enumerate(look_urls[:53], 1):
            meta_lines.append(f"  Look {i:02d}: {img_url}")
    full_text = "\n".join(meta_lines) + "\n\n" + text

    cache_mod.set("tagwalk", url, full_text, ttl_days=1)
    return full_text


def _parse_tagwalk_html(html):
    """
    Parse tag-walk collection HTML.
    Returns (clean_text, look_image_urls_list).
    Look images use the /list/ CDN path (thumbnail size, optimal for vision models).
    """
    # Extract lazy-load look image URLs
    look_urls = re.findall(
        r'data-src=["\']https://cdn\.tag-walk\.com/list/([^"\']+\.jpg)["\']', html
    )
    look_urls = [f"https://cdn.tag-walk.com/view/{slug}" for slug in look_urls]

    # Extract any text tags that appear as visible labels on the page
    tag_labels = re.findall(
        r'<(?:a|span|li)[^>]+class=["\'][^"\']*(?:tag|label)[^"\']*["\'][^>]*>([\w\s,\-/éàèêîôùûüç]+)</',
        html, re.IGNORECASE
    )
    tag_labels = [re.sub(r'\s+', ' ', t).strip() for t in tag_labels if 2 < len(t.strip()) < 40]

    # Clean HTML to plain text
    text = _clean_html(html)
    if tag_labels:
        text = "VISIBLE TAGS ON PAGE: " + ", ".join(tag_labels[:40]) + "\n\n" + text

    return text, look_urls


def _parse_tagwalk_url(url):
    """
    Extract (designer_slug, season_slug, gender, city) from a tag-walk URL.
    e.g. /en/collection/woman/akris/fall-winter-2026?city=paris
    → ("akris", "fall-winter-2026", "woman", "paris")
    """
    m = re.search(
        r"/collection/([^/]+)/([^/]+)/([^/?]+)(?:\?city=([^&]+))?", url
    )
    if m:
        gender, designer, season, city = m.groups()
        return designer, season, gender, city
    # Fallback — return url for get_page_html
    raise ValueError(f"Cannot parse tag-walk URL: {url}")


# ── YouTube (metadata + description, with cache) ──────────────────────────────

def fetch_youtube(url, force=False):
    """
    Extract show metadata from a YouTube video using yt-dlp.
    Returns (text, look_image_urls) where look_image_urls are distinct keyframe thumbnails.
    Cached 7 days.
    """
    cache_key = f"youtube::{url}"
    if not force:
        cached = cache_mod.get("url", cache_key)
        if cached:
            print(f"     [cache hit] youtube {url[:60]}")
            if isinstance(cached, dict):
                return cached["text"], cached.get("look_image_urls", [])
            return cached, []  # legacy cache — text only

    cmd = ["yt-dlp", "--dump-json", "--no-playlist", url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        cmd = [sys.executable, "-m", "yt_dlp", "--dump-json", "--no-playlist", url]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except FileNotFoundError:
            raise EnvironmentError("yt-dlp not installed. Run: pip install yt-dlp")

    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr[:300]}")

    meta  = json.loads(result.stdout)
    parts = []

    title       = meta.get("title", "")
    description = (meta.get("description", "") or "").strip()
    channel     = meta.get("channel", "") or meta.get("uploader", "")
    upload_date = meta.get("upload_date", "")
    duration    = meta.get("duration", 0)

    parts.append(f"VIDEO TITLE: {title}")
    if channel:
        parts.append(f"CHANNEL: {channel}")
    if upload_date:
        parts.append(f"UPLOAD DATE: {upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}")
    if duration:
        parts.append(f"DURATION: {duration//60}m {duration%60}s")

    if description:
        parts.append(f"\nDESCRIPTION:\n{description[:3000]}")

    chapters = meta.get("chapters", [])
    if chapters:
        parts.append("\nCHAPTERS:")
        for ch in chapters:
            parts.append(f"  {ch.get('title','')}  @ {ch.get('start_time',0):.0f}s")

    # Extract distinct keyframe thumbnails for vision pipeline.
    # YouTube uses numeric IDs (1, 2, 3) for different video frames; filter to .jpg only.
    look_image_urls = _youtube_keyframe_urls(meta)
    if look_image_urls:
        parts.append(f"\nKEYFRAME THUMBNAILS: {len(look_image_urls)} frames available for vision analysis")

    text = "\n".join(parts)
    cache_mod.set("url", cache_key, {"text": text, "look_image_urls": look_image_urls}, ttl_days=7)
    return text, look_image_urls


def _youtube_keyframe_urls(meta):
    """
    Extract distinct keyframe thumbnail URLs from yt-dlp metadata.
    YouTube exposes up to 3 keyframes as 1.jpg / 2.jpg / 3.jpg.
    Prefers highest resolution variant of each unique frame.
    """
    thumbnails = meta.get("thumbnails", [])
    # Group by base filename (strip query string)
    frames = {}
    for t in thumbnails:
        raw_url = t.get("url", "")
        if not raw_url.endswith(".jpg"):
            continue
        base = raw_url.split("?")[0]
        filename = base.rsplit("/", 1)[-1]  # e.g. "1.jpg", "maxresdefault.jpg"
        # Only take simple numeric frames and the high-res default
        if filename in ("1.jpg", "2.jpg", "3.jpg", "maxresdefault.jpg", "hq720.jpg", "sddefault.jpg"):
            # Prefer clean URL (no query string)
            if filename not in frames or "?" not in base:
                frames[filename] = base

    # Return numeric keyframes first, then the best resolution default
    ordered = []
    for name in ("1.jpg", "2.jpg", "3.jpg", "maxresdefault.jpg"):
        if name in frames:
            ordered.append(frames[name])
    return ordered


def youtube_season_hint(url):
    """
    Extract brand + season + year from a YouTube video title.
    Returns dict: {brand, period, year} or {} if not parseable.
    Handles English and transliterated Asian titles.
    """
    cmd = ["yt-dlp", "--dump-json", "--no-playlist", "--no-warnings", url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        cmd = [sys.executable, "-m", "yt_dlp", "--dump-json", "--no-playlist", "--no-warnings", url]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except FileNotFoundError:
            return {}
    if result.returncode != 0:
        return {}
    title = json.loads(result.stdout).get("title", "")
    return _parse_youtube_title(title)


def _parse_youtube_title(title):
    """Parse multilingual show titles → {brand, period, year}."""
    # Translate common non-English season keywords
    season_synonyms = {
        "automne": "FALL", "autumn": "FALL", "hiver": "WINTER", "winter": "WINTER",
        "printemps": "SPRING", "spring": "SPRING", "été": "SUMMER", "summer": "SUMMER",
        "primavera": "SPRING", "otoño": "FALL", "invierno": "WINTER", "verano": "SUMMER",
        "herbst": "FALL", "frühjahr": "SPRING", "秋冬": "FALLWINTER", "春夏": "SPRINGSUMMER",
        "fw": "FALL", "aw": "FALL", "ss": "SPRING", "f/w": "FALL", "s/s": "SPRING",
    }

    t_norm = title.upper()
    for word, replacement in season_synonyms.items():
        t_norm = t_norm.replace(word.upper(), replacement)

    period = None
    for kw, p in [
        ("FALL/WINTER", "AW"), ("FALL-WINTER", "AW"), ("FALL WINTER", "AW"), ("FALLWINTER", "AW"),
        ("AUTUMN/WINTER", "AW"), ("AUTUMN WINTER", "AW"),
        ("SPRING/SUMMER", "SS"), ("SPRING SUMMER", "SS"), ("SPRINGSUMMER", "SS"),
        ("RESORT", "RESORT"), ("COUTURE", "COUTURE"), ("PRE-FALL", "PF"),
        ("FALL", "AW"), ("AUTUMN", "AW"), ("SPRING", "SS"), ("WINTER", "AW"),
    ]:
        if kw in t_norm:
            period = p
            break

    year_m = re.search(r"\b(20\d{2})\b", t_norm)
    year   = int(year_m.group(1)) if year_m else None

    brand_m = re.match(r"^([A-Z][A-Z\s\-&'/]+?)\s+(?:FALL|SPRING|AUTUMN|WINTER|RESORT|COUTURE|PRE)", t_norm)
    brand   = brand_m.group(1).strip().title() if brand_m else ""

    return {"brand": brand, "period": period, "year": year}


# ── Shared HTML cleaner ───────────────────────────────────────────────────────

def _clean_html(html):
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>",  " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    for entity, char in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
                          ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"), ("&apos;", "'")]:
        html = html.replace(entity, char)
    return re.sub(r"\s+", " ", html).strip()
