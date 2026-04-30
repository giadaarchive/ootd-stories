#!/usr/bin/env python3
"""
Remove all non-image blocks before Heritage & House Notes from every for-sale page.

Page body rule: images only before Heritage. Everything else gets deleted.
Run this any time to clean all shop pages in one shot.
"""

import os, requests, time
from dotenv import load_dotenv
load_dotenv()

H = {'Authorization': f'Bearer {os.environ["NOTION_TOKEN"]}', 'Notion-Version': '2022-06-28'}
DB = 'ad079964969043ae9fa85a4f3ca1a9ee'
HERITAGE_MARKER = "Heritage & House Notes"


def get_blocks(page_id):
    blocks, cursor = [], None
    while True:
        url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        if cursor:
            url += f"?start_cursor={cursor}"
        r = requests.get(url, headers=H)
        r.raise_for_status()
        d = r.json()
        blocks.extend(d.get("results", []))
        if not d.get("has_more"):
            break
        cursor = d["next_cursor"]
    return blocks


def txt(b):
    t = b.get("type", "")
    return "".join(x.get("plain_text", "") for x in b.get(t, {}).get("rich_text", []))


def clean_page(pid, title):
    blocks = get_blocks(pid)
    to_delete = []
    for b in blocks:
        btype = b["type"]
        if btype == "heading_2" and HERITAGE_MARKER in txt(b):
            break
        if btype != "image":
            to_delete.append(b["id"])

    if not to_delete:
        print(f"  OK    {title[:65]}")
        return 0

    print(f"  CLEAN [{len(to_delete):2d}] {title[:60]}")
    for bid in to_delete:
        r = requests.delete(f"https://api.notion.com/v1/blocks/{bid}", headers=H)
        if r.status_code not in (200, 404):
            print(f"    ERROR {bid}: {r.status_code}")
        time.sleep(0.15)
    return len(to_delete)


r = requests.post(f'https://api.notion.com/v1/databases/{DB}/query', headers=H, json={
    'filter': {'property': 'For Sale', 'checkbox': {'equals': True}},
    'page_size': 100
})
pages = r.json()['results']
print(f'{len(pages)} for-sale pages\n')

total = 0
for page in pages:
    pid = page['id']
    props = page['properties']
    title_prop = next((v for v in props.values() if v.get('type') == 'title'), None)
    title = title_prop['title'][0]['plain_text'] if title_prop and title_prop.get('title') else '(no title)'
    total += clean_page(pid, title)
    time.sleep(0.2)

print(f'\nDone — {total} blocks removed across all pages.')
