#!/usr/bin/env python3
"""
Daily cron: check OpenRouter for latest available models, update models_config.json.

Scoring approach (no fragile substring matching):
  For each task, models are ranked by:
    1. Family preference rank (first match in preference list wins)
    2. Context window size (larger = better, from API)
    3. Estimated parameter count extracted from model name (70b > 32b > 7b)

Usage:
  python3 house_codes/model_watcher.py          — update config
  python3 house_codes/model_watcher.py --list   — print models + scores, no update
  python3 house_codes/model_watcher.py --dry-run — show changes, don't save

Cron (add to crontab manually — see instructions below):
  0 9 * * *  cd /Users/lisa/lookbook-stories && /usr/local/bin/python3 house_codes/model_watcher.py >> /tmp/model_watcher.log 2>&1
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
import requests as http_requests

_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_DIR, "models_config.json")

# Per-task: ranked list of model family keywords.
# These are regex patterns matched against model IDs (case-insensitive).
# First match = highest preference. Partial matches within a family are
# then ranked by context window (larger = better) + param count.
TASK_FAMILIES = {
    "text_extraction": [
        r"qwen.*72b", r"qwen.*70b",
        r"llama.*3\.3.*70b", r"llama.*3\.1.*70b",
        r"deepseek.*chat", r"deepseek.*v3",
        r"mistral.*large",
    ],
    "vision_analysis": [
        r"qwen.*vl.*72b", r"qwen2\.5.*vl", r"qwen.*vl",
        r"pixtral.*large", r"intern.*vl.*72b", r"intern.*vl",
        r"llava.*34b", r"llava",
    ],
    "checker": [
        r"llama.*3\.3.*70b", r"llama.*3\.1.*70b",
        r"qwen.*72b", r"qwen.*70b",
        r"mistral.*large",
    ],
    "cross_brand_analysis": [
        r"qwen.*72b", r"qwen.*70b",
        r"llama.*3\.3.*70b",
        r"deepseek.*chat",
    ],
    "trend_signal": [
        r"qwen.*72b", r"qwen.*70b",
        r"llama.*3\.3.*70b",
    ],
}


def _param_count(model_id):
    """Extract parameter count in billions from model ID string. Returns 0 if not found."""
    m = re.search(r"(\d+(?:\.\d+)?)b", model_id.lower())
    return float(m.group(1)) if m else 0.0


def _score_model(model_id, context_window, family_patterns):
    """
    Score a model for a task. Lower score = better (like a rank).
    Returns (family_rank, -context_window, -param_count) — sort ascending.
    """
    mid = model_id.lower()
    for rank, pattern in enumerate(family_patterns):
        if re.search(pattern, mid):
            return (rank, -(context_window or 0), -_param_count(model_id))
    return (len(family_patterns), 0, 0)   # no family match — worst


def get_models_with_metadata():
    """Fetch model list from OpenRouter with context window metadata."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise EnvironmentError("OPENROUTER_API_KEY not set in .env")

    # Use raw requests to get full model objects (openai client strips metadata)
    resp = http_requests.get(
        "https://openrouter.ai/api/v1/models",
        headers={"Authorization": f"Bearer {key}"},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])
    return [
        {
            "id":             m["id"],
            "context_window": m.get("context_length") or m.get("context_window") or 0,
        }
        for m in data
    ]


def pick_best(models, family_patterns):
    """Return best model ID by scoring against family patterns."""
    scored = []
    for m in models:
        score = _score_model(m["id"], m["context_window"], family_patterns)
        if score[0] < len(family_patterns):   # only models that matched a family
            scored.append((score, m["id"]))
    if not scored:
        return None
    scored.sort()
    return scored[0][1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list",    action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ts = datetime.utcnow().isoformat()
    print(f"[{ts}] model_watcher starting")

    try:
        models = get_models_with_metadata()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"  {len(models)} models on OpenRouter")

    if args.list:
        for m in sorted(models, key=lambda x: x["id"]):
            print(f"  {m['id']:60s}  ctx={m['context_window']:,}")
        return

    with open(CONFIG_PATH) as f:
        config = json.load(f)

    changes = []
    for task, patterns in TASK_FAMILIES.items():
        best = pick_best(models, patterns)
        old  = config["tasks"].get(task, {}).get("model", "—")
        if best:
            config["tasks"][task]["model"] = best
            if old != best:
                print(f"  {task}: {old}  →  {best}")
                changes.append(task)
            else:
                print(f"  {task}: unchanged ({best})")
        else:
            print(f"  {task}: no match found, keeping {old}")

    config["last_updated"] = datetime.utcnow().date().isoformat()

    if args.dry_run:
        print(f"  [dry-run] {len(changes)} task(s) would change — not saved")
        return

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

    print(f"  Done — {len(changes)} task(s) updated")


if __name__ == "__main__":
    main()
