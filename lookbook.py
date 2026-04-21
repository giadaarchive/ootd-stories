import os
import io
import time
import base64
import requests
import anthropic
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
OOTD_PROPERTY = "OOTD Story"
MAX_IMAGES_PER_ENTRY = 3

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

PROMPT = """You are writing fashion narratives for a personal lookbook. Write an evocative, atmospheric fashion story for this outfit.

Write 3–4 paragraphs that capture the vibe, energy and character of this look. Do not describe the clothes literally — write about the feeling, the world this outfit belongs to, the character wearing it, the cultural moment it references.

The tone is chic, elegant, scene-setting. Think Vogue editorial caption meets personal essay. British English. Written by someone who knows both fashion and literature.

The philosophy: every day is an occasion. This outfit is how someone chose to show up today. Make that visible. Give it meaning, narrative, a point of view.

Do not start with "I" or reference yourself. Begin in scene.

Style rules:
- Never use contradiction sentence structures. Do not write "She is not X, Y, or Z. She is W." Build meaning through what something IS, not by negating what it is not.
- Use no em dashes (—). If you feel the urge to use one, restructure the sentence instead. Maximum one em dash in the entire piece if truly unavoidable, but the strong preference is none at all."""

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def fetch_all_pages():
    pages = []
    has_more = True
    start_cursor = None

    while has_more:
        body = {
            "page_size": 100,
            "sorts": [{"property": "Added", "direction": "descending"}],
        }
        if start_cursor:
            body["start_cursor"] = start_cursor

        r = requests.post(
            f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
            headers=NOTION_HEADERS,
            json=body,
        )
        r.raise_for_status()
        data = r.json()
        pages.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    return pages


def has_story(page):
    prop = page.get("properties", {}).get(OOTD_PROPERTY, {})
    rich_text = prop.get("rich_text", [])
    return bool(rich_text) and rich_text[0].get("plain_text", "").strip()


def get_page_image_urls(page_id):
    urls = []
    has_more = True
    start_cursor = None

    while has_more:
        url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        if start_cursor:
            url += f"?start_cursor={start_cursor}"

        r = requests.get(url, headers=NOTION_HEADERS)
        r.raise_for_status()
        data = r.json()

        for block in data.get("results", []):
            if block.get("type") == "image":
                img = block["image"]
                if img.get("type") == "file":
                    urls.append(img["file"]["url"])
                elif img.get("type") == "external":
                    urls.append(img["external"]["url"])

        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    return urls


MAX_IMAGE_BYTES = 4 * 1024 * 1024  # 4MB safe limit (Claude max is 5MB)

def image_to_base64(url):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.content

    # Resize if over the size limit
    if len(data) > MAX_IMAGE_BYTES:
        img = Image.open(io.BytesIO(data))
        img = img.convert("RGB")
        scale = 0.7
        while True:
            w, h = int(img.width * scale), int(img.height * scale)
            buf = io.BytesIO()
            img.resize((w, h), Image.LANCZOS).save(buf, format="JPEG", quality=85)
            if buf.tell() <= MAX_IMAGE_BYTES or scale < 0.2:
                data = buf.getvalue()
                break
            scale *= 0.7
        return base64.standard_b64encode(data).decode(), "image/jpeg"

    content_type = r.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
    if content_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        content_type = "image/jpeg"
    return base64.standard_b64encode(data).decode(), content_type


def generate_story(image_urls):
    content = []

    for url in image_urls[:MAX_IMAGES_PER_ENTRY]:
        try:
            data, media_type = image_to_base64(url)
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": data},
            })
        except Exception as e:
            print(f"    Warning: skipped image — {e}")

    if not content:
        return None

    content.append({"type": "text", "text": PROMPT})

    for attempt in range(5):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                messages=[{"role": "user", "content": content}],
            )
            return response.content[0].text
        except Exception as e:
            if "rate_limit" in str(e).lower() and attempt < 4:
                wait = 60 * (attempt + 1)
                print(f"    Rate limited — waiting {wait}s before retry {attempt + 1}/4")
                time.sleep(wait)
            else:
                raise
    return None


def chunk_text(text, size=2000):
    """Split text into chunks for Notion's rich_text limit."""
    return [text[i:i + size] for i in range(0, len(text), size)]


def write_story(page_id, story):
    rich_text = [
        {"type": "text", "text": {"content": chunk}}
        for chunk in chunk_text(story)
    ]
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=NOTION_HEADERS,
        json={"properties": {OOTD_PROPERTY: {"rich_text": rich_text}}},
    )
    return r.status_code == 200


def main():
    print("Fetching lookbook entries...")
    pages = fetch_all_pages()
    print(f"Total entries: {len(pages)}")

    to_process = [p for p in pages if not has_story(p)]
    print(f"Entries needing stories: {len(to_process)}\n")

    success, skipped, failed = 0, 0, 0

    for i, page in enumerate(to_process):
        page_id = page["id"]

        # Get a readable title if available
        title_prop = next(
            (v for v in page.get("properties", {}).values() if v.get("type") == "title"),
            None,
        )
        title = (
            title_prop["title"][0]["plain_text"]
            if title_prop and title_prop.get("title")
            else page_id
        )

        print(f"[{i + 1}/{len(to_process)}] {title}")

        try:
            image_urls = get_page_image_urls(page_id)
            if not image_urls:
                print("  No images found — skipping")
                skipped += 1
                continue

            print(f"  {len(image_urls)} image(s) found")

            story = generate_story(image_urls)
            if not story:
                print("  Could not generate story — skipping")
                skipped += 1
                continue

            if write_story(page_id, story):
                print("  Written successfully")
                success += 1
            else:
                print("  Failed to write to Notion")
                failed += 1

        except Exception as e:
            print(f"  Error — skipping: {e}")
            failed += 1

        time.sleep(0.4)  # stay within Notion API rate limits

    print(f"\nDone. {success} written, {skipped} skipped, {failed} failed.")


if __name__ == "__main__":
    main()
