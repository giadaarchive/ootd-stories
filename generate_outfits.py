#!/usr/bin/env python3
"""
Generate outfit styling images for a collection item via OpenRouter image models.

Produces three looks:
  1. Off-duty model chic — effortless, street-style
  2. Gallery opening — elegant, polished
  3. Business casual — professional, composed

Usage:
  python3 generate_outfits.py --page <notion_page_id>
  python3 generate_outfits.py --page <notion_page_id> --model google/gemini-2.5-flash-image
  python3 generate_outfits.py --page <notion_page_id> --dry-run   # print prompts only

Images saved to: outfits/<page_id>/look_1.png  look_2.png  look_3.png
"""

import os, sys, json, base64, requests, argparse, time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]

NOTION_H = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
}

DEFAULT_IMAGE_MODEL = "google/gemini-2.5-flash-image"

STYLE_PROMPTS = [
    {
        "label": "Off-duty model chic",
        "suffix": (
            "Styled as off-duty model chic: effortless and cool. "
            "Minimal accessories, straight-leg denim or wide trousers, white sneakers or ankle boots. "
            "Shot on a Paris street, golden afternoon light, candid editorial feel. "
            "The piece is the clear focal point."
        ),
    },
    {
        "label": "Gallery opening — elegant",
        "suffix": (
            "Styled for a private gallery opening: refined and considered. "
            "Monochrome palette, sleek tailored trousers or a midi skirt, understated heels. "
            "Minimal gold jewellery, sleek low bun. Clean white-walled gallery background. "
            "Editorial, sophisticated, not fussy."
        ),
    },
    {
        "label": "Business casual — formal",
        "suffix": (
            "Styled as business casual formal: polished and authoritative. "
            "Well-cut trousers or a pencil skirt, simple silk blouse or fitted turtleneck underneath if layerable. "
            "Block-heel pumps or loafers, structured bag. Neutral office-corridor background. "
            "Confident, put-together, contemporary."
        ),
    },
]


def get_page(page_id):
    raw = page_id.replace("-", "")
    pid = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
    r = requests.get(f"https://api.notion.com/v1/pages/{pid}", headers=NOTION_H)
    r.raise_for_status()
    return r.json()


def extract_title_and_details(page):
    props = page["properties"]
    title_prop = next((v for v in props.values() if v.get("type") == "title"), None)
    title = title_prop["title"][0]["plain_text"] if title_prop and title_prop.get("title") else ""

    mat_rt = props.get("Material", {}).get("rich_text", [])
    material = mat_rt[0]["plain_text"] if mat_rt else ""

    colour_rt = props.get("Colour Detail", {}).get("rich_text", [])
    colour = colour_rt[0]["plain_text"] if colour_rt else ""

    cat_sel = props.get("Category", {}).get("select")
    category = cat_sel["name"] if cat_sel else ""

    return {"title": title, "material": material, "colour": colour, "category": category}


def get_heritage_description(page_id):
    """Read About This Piece text from Heritage section for richer image prompt context."""
    raw = page_id.replace("-", "")
    pid = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
    r = requests.get(f"https://api.notion.com/v1/blocks/{pid}/children", headers=NOTION_H)
    if r.status_code != 200:
        return ""
    blocks = r.json().get("results", [])
    collecting = False
    lines = []
    for b in blocks:
        btype = b.get("type", "")
        rt = b.get(btype, {}).get("rich_text", [])
        tx = "".join(x.get("plain_text", "") for x in rt)
        if btype == "heading_3" and "About This Piece" in tx:
            collecting = True
            continue
        if collecting:
            if btype == "heading_3":
                break
            if btype == "paragraph" and tx.strip():
                lines.append(tx.strip())
    return " ".join(lines[:2])[:400]


def build_image_prompt(details, heritage_text, style):
    item_desc = details["title"]
    parts = [item_desc]
    if details["material"]:
        parts.append(f"made of {details['material']}")
    if details["colour"]:
        parts.append(f"in {details['colour']}")
    item_str = ", ".join(parts)

    prompt = (
        f"Fashion editorial photograph. A woman wearing: {item_str}. "
    )
    if heritage_text:
        prompt += f"{heritage_text[:200]} "
    prompt += style["suffix"]
    prompt += (
        " High-end fashion photography. Film grain, natural colour palette. "
        "Full outfit visible, editorial quality. No text overlays."
    )
    return prompt


def generate_image(prompt, model, label):
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "modalities": ["image", "text"],
        },
        timeout=120,
    )
    if r.status_code != 200:
        raise RuntimeError(f"OpenRouter error {r.status_code}: {r.text[:300]}")

    data = r.json()
    message = data["choices"][0]["message"]

    # Image may come back as base64 data URL or external URL
    images = message.get("images", [])
    if images:
        img_url = images[0].get("image_url", {}).get("url", "")
        if img_url.startswith("data:"):
            b64 = img_url.split(",", 1)[1]
            return base64.b64decode(b64)
        elif img_url:
            ir = requests.get(img_url, timeout=30)
            return ir.content

    # Some models return image in content as multipart
    content = message.get("content", "")
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "image_url":
                img_url = part["image_url"]["url"]
                if img_url.startswith("data:"):
                    b64 = img_url.split(",", 1)[1]
                    return base64.b64decode(b64)

    raise RuntimeError(f"No image in response. Content: {str(message)[:300]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", required=True, metavar="PAGE_ID", help="Notion page ID")
    parser.add_argument("--model", default=DEFAULT_IMAGE_MODEL, help=f"Image model. Default: {DEFAULT_IMAGE_MODEL}")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts without generating")
    args = parser.parse_args()

    page = get_page(args.page)
    details = extract_title_and_details(page)
    heritage = get_heritage_description(args.page)

    print(f"Item: {details['title']}")
    print(f"Model: {args.model}\n")

    out_dir = Path("outfits") / args.page.replace("-", "")
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    for i, style in enumerate(STYLE_PROMPTS, 1):
        prompt = build_image_prompt(details, heritage, style)
        print(f"Look {i}: {style['label']}")
        if args.dry_run:
            print(f"  Prompt: {prompt[:200]}...")
            continue

        print(f"  Generating...")
        try:
            img_bytes = generate_image(prompt, args.model, style["label"])
            out_path = out_dir / f"look_{i}.png"
            out_path.write_bytes(img_bytes)
            print(f"  Saved: {out_path} ({len(img_bytes):,} bytes)")
        except Exception as e:
            print(f"  ERROR: {e}")
        time.sleep(2)


if __name__ == "__main__":
    main()
