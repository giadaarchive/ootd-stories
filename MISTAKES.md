# Mistakes & How to Fix Them — ootd-stories

A running log of errors that have occurred, their root causes, and the exact fix. When something breaks, document it here.

---

## Wrong item scraped from Yahoo Japan

**Symptom:** The Notion page shows images/description for the wrong item (e.g. a duffel bag instead of a round bag).

**Cause:** Yahoo Japan auction HTML contains related listings. The image extractor (`re.findall` on `auctions.c.yimg.jp` URLs) picks up images from related items that appear further down the page HTML.

**Fix:** Use [`fix-wrong-entry.md`](./skills/fix-wrong-entry.md). Scrape the correct auction page again, upload images to GitHub, delete old blocks, rewrite with correct content.

**Prevention:** After running a scrape, always verify the first 2–3 image URLs before writing to Notion. Open the URLs in a browser to confirm they show the correct item.

---

## Images not loading on Notion page

**Symptom:** Broken image icons on a Notion item page.

**Cause:** Yahoo Japan (`auctions.c.yimg.jp`) and Mercari (`static.mercdn.net`) use hotlink-protected, session-authenticated URLs that expire within hours to days.

**Fix:** Use [`rehost-images.md`](./skills/rehost-images.md) immediately. Download images with a Yahoo Referer header and re-host permanently on GitHub.

**Prevention:** Run the rehost skill immediately after adding any item from Yahoo Japan or Mercari.

---

## Duplicate Heritage & House Notes sections

**Symptom:** The Notion item page shows two "Heritage & House Notes" headings with duplicate content below each.

**Cause:** `heritage.py --force` was run twice on the same page without deleting the first set first. The `--force` flag deletes blocks from the Heritage heading onwards, but if the deletion partially failed or the first run left a partial result, running again appends a second set.

**Fix:**
1. Open the Notion page
2. Find the second "Heritage & House Notes" heading
3. Select and delete all blocks from that heading to the end of the page
4. Or use this script to delete the duplicate programmatically:

```python
import os, requests, time
from dotenv import load_dotenv
load_dotenv()
H = {"Authorization": f"Bearer {os.environ['NOTION_TOKEN']}", "Notion-Version": "2022-06-28"}
PAGE_ID = "PASTE_PAGE_ID"

blocks = requests.get(f"https://api.notion.com/v1/blocks/{PAGE_ID}/children", headers=H).json()["results"]

def text(b):
    t = b.get("type","")
    return "".join(x.get("plain_text","") for x in b.get(t,{}).get("rich_text",[]))

# Find the second Heritage heading
heritage_indices = [i for i, b in enumerate(blocks) if b.get("type") == "heading_2" and "Heritage" in text(b)]
if len(heritage_indices) >= 2:
    for b in blocks[heritage_indices[1]:]:
        requests.delete(f"https://api.notion.com/v1/blocks/{b['id']}", headers=H)
        time.sleep(0.2)
    print(f"Deleted {len(blocks) - heritage_indices[1]} duplicate blocks")
```

**Prevention:** Check the Notion page before running `heritage.py --force` a second time. If a Heritage section already exists and looks correct, do not re-run.

---

## Heritage content is house-centric, not piece-specific

**Symptom:** The "About This Piece" section describes a generic version of the item (e.g. "Louis Vuitton has produced Monogram canvas bags since...") rather than this specific piece.

**Cause:** The `heritage.py` script ran without reading the page body first, so Claude had no specific context about what the item actually is. Old versions of `heritage.py` ran with the heritage heading as the first block, deleting body context before generating.

**Fix:** Ensure the page body has a description or images before re-running with `--force`. The current `heritage.py` reads `read_page_description()` before deleting any blocks, preserving context for Claude.

---

## JSON parse error in heritage.py or heritage_audit.py

**Symptom:** `ERROR: Expecting ',' delimiter: line X column Y` in script output.

**Cause:** Claude returned a JSON response that was cut off or malformed — usually because the content hit the `max_tokens` limit mid-response.

**Fix:** Re-run the script. This is almost always a transient API issue that resolves on retry. If it persists for the same item, increase `max_tokens` in the relevant `claude.messages.create()` call.

---

## Substack status not updating to "Posted"

**Symptom:** `substack.py` ran and posts are scheduled, but Notion entries still show `Post to Substack` instead of `Posted`.

**Cause:** The script crashed or was interrupted after scheduling but before the Notion PATCH request completed.

**Fix:** Manually update the status for affected entries:

```python
import os, requests
from dotenv import load_dotenv
load_dotenv()
H = {"Authorization": f"Bearer {os.environ['NOTION_TOKEN']}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
PAGE_IDS = ["PASTE_IDS_HERE"]
for pid in PAGE_IDS:
    r = requests.patch(f"https://api.notion.com/v1/pages/{pid}", headers=H,
        json={"properties": {"Substack": {"status": {"name": "Posted"}}}})
    print(pid, r.status_code)
```

---

## OOTD stories not generating — 0 images found

**Symptom:** `lookbook.py` reports "No images found" for an entry that visibly has photos.

**Cause:** Photos were added inside a synced block in Notion. `lookbook.py` reads only top-level blocks — it does not recurse into synced block children.

**Fix:** In Notion, move the images out of the synced block to the top level of the page. Then re-run `lookbook.py`.

---

## batch_tag_why_i_own_it.py applies wrong tags

**Symptom:** Tags applied don't match the actual reason for ownership.

**Cause:** The `--context` text was too vague for Claude to match confidently.

**Fix:** Delete the incorrectly applied tags from the Notion item. Re-run with a more specific `--context` string, or manually set the `Why I own it` tags in Notion.

---

## Heritage notes reproducing Japanese resale listing boilerplate

**Symptom:** Heritage output includes raw copy-paste from Yahoo Japan / Mercari: dimensions in W/H/D format, weight in grams, condition rank (Rank: B), field labels ("Manufacturer:", "Accessories: None", "Color (pattern) system:"), or disclaimers ("color may differ", "also sold in-store").

**Cause:** Notion page body contains unedited resale listing text. The heritage script reads this as context and may reproduce or reference it.

**Fix:** The `SYSTEM_PROMPT` in `heritage.py` now explicitly bans this content. If it still appears, clean the Notion page body — remove the raw listing block and replace with a plain description of the piece — then re-run with `--force <page_id>`.
