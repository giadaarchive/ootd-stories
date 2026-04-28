#!/usr/bin/env python3
"""
Wardrobe Archive Script
Given a Notion page and a YouTube URL, fetches the video transcript,
uses Claude to extract the story, care instructions, and tags,
then writes everything back to the Notion entry.

Usage:
  python3 wardrobe_archive.py <notion_page_url_or_id> <youtube_url>

Example:
  python3 wardrobe_archive.py https://www.notion.so/lisajyt/... https://www.youtube.com/watch?v=oynop22uTMA
"""

import os
import re
import sys
import json
import requests
import anthropic
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi

load_dotenv("/Users/lisa/lookbook-stories/.env")

TOKEN = os.environ["NOTION_TOKEN"]
H = {"Authorization": f"Bearer {TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}

TAG_MAP_PATH = "/Users/lisa/lookbook-stories/tag_id_map.json"
with open(TAG_MAP_PATH) as f:
    TAG_MAP = json.load(f)

APPROVED_YES = sorted([
    "vintage-provenance", "investment-piece", "natural-patina", "travel-worthy",
    "craftsmanship", "rare-find", "brand-legacy", "versatile", "timeless-silhouette",
    "love-the-designer", "brand-discovery", "pattern-integrity", "colour",
    "sentimental", "gifted",
])
APPROVED_CHANGE = sorted([
    "visible-logo", "loud-branding", "logo-fatigue", "price", "condition",
    "size-wrong", "wrong-colour", "wrong-fabric-for-use-case",
    "misleading-material-claim", "too-common-silhouette", "derivative-design",
    "doesnt-fit-my-wardrobe", "doesnt-fit-my-style",
    "have-equivalent-in-wardrobe", "have-better-in-wardrobe",
])

WASH_METHODS = ["Spot clean", "Dry clean", "Machine wash", "Handwash"]
WASH_TEMPS   = ["60ºC", "40ºC", "30ºC", "20ºC", "Cold"]
STORAGE      = ["Cedar box", "Drawer", "Hanger"]
IRONING      = ["Press cloth required", "Do not iron", "Steam", "Medium"]
DRYING       = ["Dryer", "Lay flat to dry", "Line dry"]
SEASONS      = ["Spring", "Summer", "Autumn", "Winter"]

SYSTEM_PROMPT = f"""You analyse video transcripts about wardrobe pieces and extract structured information.

The videos are recorded by the owner, Lisa. She talks about what the item is, where it came from, why she has it, what she loves about the material or construction, and how to care for it.

Given a transcript and item context, return a JSON object with these exact fields:

{{
  "story": "Written narrative in third person. 2-4 paragraphs. Captures why she has this item, where it came from, what she values about it, and anything notable about the material or making. Based strictly on what she said — do not invent details.",
  "why_own": [],
  "what_id_change": [],
  "wash_method": [],
  "wash_temperature": [],
  "drying": null,
  "storage_method": [],
  "ironing": [],
  "season": []
}}

APPROVED values — use ONLY these, exactly as written:
- why_own (tags): {APPROVED_YES}
- what_id_change (tags): {APPROVED_CHANGE}
- wash_method: {WASH_METHODS}
- wash_temperature: {WASH_TEMPS}
- drying (single value or null): {DRYING}
- storage_method: {STORAGE}
- ironing: {IRONING}
- season: {SEASONS}

RULES:
- Only populate a field if it is clearly mentioned in the transcript. Empty list or null if not mentioned.
- Never invent values not in the approved lists.
- why_own: max 5 tags. what_id_change: only if she mentions something she'd change or doesn't love.
- story: write from the transcript. Do not summarise to bullet points — write prose."""


def extract_page_id(url_or_id):
    match = re.search(r"([a-f0-9]{32})(?:[?&#]|$)", url_or_id.replace("-", ""))
    if match:
        raw = match.group(1)
        return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
    return url_or_id


def extract_video_id(url):
    match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    if not match:
        raise ValueError(f"Could not extract video ID from: {url}")
    return match.group(1)


def get_transcript(video_id):
    api = YouTubeTranscriptApi()
    parts = api.fetch(video_id)
    return " ".join(t.text for t in parts)


def get_page(page_id):
    r = requests.get(f"https://api.notion.com/v1/pages/{page_id}", headers=H)
    r.raise_for_status()
    return r.json()


def find_story_row_id(page_id):
    """Walk the page body, find the table under 'Owners and Stories', return the block ID of 'The Story' row."""
    r = requests.get(f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=50", headers=H)
    blocks = r.json().get("results", [])

    in_owners_section = False
    for b in blocks:
        btype = b["type"]
        if btype == "heading_1":
            text = "".join(x.get("plain_text", "") for x in b.get("heading_1", {}).get("rich_text", []))
            in_owners_section = "Owner" in text
        if in_owners_section and btype == "table":
            rows_r = requests.get(f"https://api.notion.com/v1/blocks/{b['id']}/children", headers=H)
            for row in rows_r.json().get("results", []):
                cells = row.get("table_row", {}).get("cells", [])
                if cells:
                    key = "".join(c.get("plain_text", "") for c in cells[0]).strip()
                    if key == "The Story":
                        return row["id"]
    return None


def update_story_row(row_id, story_text):
    r = requests.patch(f"https://api.notion.com/v1/blocks/{row_id}", headers=H, json={
        "table_row": {
            "cells": [
                [{"type": "text", "text": {"content": "The Story"}}],
                [{"type": "text", "text": {"content": story_text}}],
            ]
        }
    })
    r.raise_for_status()


def analyse_transcript(title, transcript):
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    prompt = f"Item: {title}\n\nTranscript:\n{transcript[:9000]}\n\nReturn JSON only."
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError(f"No JSON found in response: {text[:200]}")


def build_property_patch(data):
    props = {}
    if data.get("wash_method"):
        valid = [v for v in data["wash_method"] if v in WASH_METHODS]
        if valid:
            props["Wash Method"] = {"multi_select": [{"name": v} for v in valid]}
    if data.get("wash_temperature"):
        valid = [v for v in data["wash_temperature"] if v in WASH_TEMPS]
        if valid:
            props["Wash Temperature"] = {"multi_select": [{"name": v} for v in valid]}
    if data.get("drying") and data["drying"] in DRYING:
        props["Drying"] = {"select": {"name": data["drying"]}}
    if data.get("storage_method"):
        valid = [v for v in data["storage_method"] if v in STORAGE]
        if valid:
            props["Storage Method"] = {"multi_select": [{"name": v} for v in valid]}
    if data.get("ironing"):
        valid = [v for v in data["ironing"] if v in IRONING]
        if valid:
            props["Ironing"] = {"multi_select": [{"name": v} for v in valid]}
    if data.get("season"):
        valid = [v for v in data["season"] if v in SEASONS]
        if valid:
            props["Season"] = {"multi_select": [{"name": v} for v in valid]}
    if data.get("why_own"):
        ids = [{"id": TAG_MAP[t]} for t in data["why_own"] if t in TAG_MAP]
        if ids:
            props["Why I own it (Tags)"] = {"relation": ids}
    if data.get("what_id_change"):
        ids = [{"id": TAG_MAP[t]} for t in data["what_id_change"] if t in TAG_MAP]
        if ids:
            props["What I'd change (Tags)"] = {"relation": ids}
    return props


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    page_id = extract_page_id(sys.argv[1])
    youtube_url = sys.argv[2]
    video_id = extract_video_id(youtube_url)

    print(f"Page:  {page_id}")
    print(f"Video: {video_id}")

    page = get_page(page_id)
    title_parts = page["properties"]["Second best"]["title"]
    title = title_parts[0]["plain_text"] if title_parts else "(no title)"
    print(f"Item:  {title}\n")

    print("Fetching transcript...")
    transcript = get_transcript(video_id)
    print(f"  {len(transcript)} chars\n")

    print("Analysing with Claude...")
    data = analyse_transcript(title, transcript)

    print("Extracted:")
    print(f"  Why own      : {data.get('why_own', [])}")
    print(f"  What I'd change: {data.get('what_id_change', [])}")
    print(f"  Wash method  : {data.get('wash_method', [])}")
    print(f"  Wash temp    : {data.get('wash_temperature', [])}")
    print(f"  Drying       : {data.get('drying')}")
    print(f"  Storage      : {data.get('storage_method', [])}")
    print(f"  Ironing      : {data.get('ironing', [])}")
    print(f"  Season       : {data.get('season', [])}")
    print(f"  Story        : {data.get('story', '')[:100]}...")

    if data.get("story"):
        print("\nWriting story to page body...")
        story_row_id = find_story_row_id(page_id)
        if story_row_id:
            update_story_row(story_row_id, data["story"])
            print("  ✓ Story written")
        else:
            print("  ✗ Could not find 'The Story' row — add it manually in the Owners and Stories table")

    props = build_property_patch(data)
    if props:
        print(f"\nUpdating properties: {', '.join(props.keys())}")
        r = requests.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=H, json={"properties": props})
        r.raise_for_status()
        print("  ✓ Properties updated")
    else:
        print("\nNo properties to update (nothing was mentioned in the transcript).")

    print("\nDone.")


if __name__ == "__main__":
    main()
