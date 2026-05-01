"""
Disk cache for URL fetches and LLM responses.
Goal: reuse identical fetches/calls across runs to minimize token spend.

Cache key = SHA256 of (namespace + content_key).
Entries stored as JSON files in house_codes/cache/<namespace>/<hash>.json

TTL defaults:
  url    — 7 days   (page content unlikely to change)
  llm    — 14 days  (deterministic prompts on same text → same answer)
  tagwalk — 24h     (tag-walk data can be refreshed more often)
"""
import hashlib
import json
import os
from datetime import datetime, timedelta

_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")

TTL = {
    "url":     7,
    "llm":     14,
    "tagwalk": 1,
}


def _path(namespace, key_str):
    h = hashlib.sha256(f"{namespace}::{key_str}".encode()).hexdigest()
    d = os.path.join(_CACHE_DIR, namespace)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, h + ".json")


def get(namespace, key_str):
    """Return cached value or None if missing / expired."""
    p = _path(namespace, key_str)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            entry = json.load(f)
        expires = datetime.fromisoformat(entry["expires"])
        if datetime.utcnow() > expires:
            os.remove(p)
            return None
        return entry["value"]
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def set(namespace, key_str, value, ttl_days=None):
    """Store value with TTL. ttl_days defaults by namespace."""
    if ttl_days is None:
        ttl_days = TTL.get(namespace, 7)
    p = _path(namespace, key_str)
    entry = {
        "key_preview":  key_str[:120],
        "value":        value,
        "cached_at":    datetime.utcnow().isoformat(),
        "expires":      (datetime.utcnow() + timedelta(days=ttl_days)).isoformat(),
    }
    with open(p, "w", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False)


def llm_key(model, system, user):
    """Deterministic cache key for an LLM call."""
    return hashlib.sha256(f"{model}|||{system}|||{user}".encode()).hexdigest()


def stats():
    """Count cached entries per namespace."""
    result = {}
    if not os.path.isdir(_CACHE_DIR):
        return result
    for ns in os.listdir(_CACHE_DIR):
        ns_dir = os.path.join(_CACHE_DIR, ns)
        if os.path.isdir(ns_dir):
            result[ns] = len([f for f in os.listdir(ns_dir) if f.endswith(".json")])
    return result
