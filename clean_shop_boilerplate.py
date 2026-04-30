#!/usr/bin/env python3
"""Remove Japanese resale boilerplate from all for-sale Notion pages."""

import os, requests, time
from dotenv import load_dotenv
load_dotenv()

H = {'Authorization': f'Bearer {os.environ["NOTION_TOKEN"]}', 'Notion-Version': '2022-06-28'}
DB = 'ad079964969043ae9fa85a4f3ca1a9ee'

r = requests.post(f'https://api.notion.com/v1/databases/{DB}/query', headers=H, json={
    'filter': {'property': 'For Sale', 'checkbox': {'equals': True}},
    'page_size': 50
})
pages = r.json()['results']
print(f'{len(pages)} for-sale items\n')

def txt(b):
    t = b.get('type', '')
    rt = b.get(t, {}).get('rich_text', [])
    return ''.join(x.get('plain_text', '') for x in rt)

BOILERPLATE_KEYWORDS = [
    # Japanese resale structure
    'Made in Italy', 'Made in Japan', 'Management number', 'Condition:', 'Rank:',
    'Shipping included', 'Category:', 'Strap length:', 'Interior:', 'Dimensions:',
    'W19cm', 'Brand:', 'Sold via', 'Self-standing', '2WAY',
    'Hand/Shoulder', 'Manufacturer:', 'Accessories: None', 'Color (pattern)',
    'also sold in-store', 'color may differ', 'Free Shipping',
    # Condition language
    'Minor surface scratch', 'Very good condition', 'signs of use',
    'excellent used condition', 'used condition', 'good condition',
    'no particular', 'no noticeable',
    # Auction/listing context
    'auction listing', 'Yahoo Japan', 'auction has ended', 'The auction',
    'listed under', 'listed on', 'women\'s tops category', 'men\'s',
    '美品', '良品', '中古', 'ヤフオク',
    # Resale field labels
    'Nº ', 'nº ', 'Serial', 'serial number',
]

cleaned = 0
already_ok = 0

for page in pages:
    pid = page['id']
    props = page['properties']
    title_prop = next((v for v in props.values() if v.get('type') == 'title'), None)
    title = title_prop['title'][0]['plain_text'] if title_prop and title_prop.get('title') else '(no title)'

    r2 = requests.get(f'https://api.notion.com/v1/blocks/{pid}/children', headers=H)
    if r2.status_code != 200:
        print(f'  SKIP {title[:50]} ({r2.status_code})')
        continue

    blocks = r2.json()['results']
    to_delete = []
    dividers_before_heritage = []

    for b in blocks:
        t = b['type']
        tx = txt(b)
        if t == 'heading_2' and 'Heritage' in tx:
            break
        if t == 'heading_3' and tx.strip().lower() in ('description', 'details', 'item details', 'product description'):
            to_delete.append(b['id'])
        elif t == 'paragraph' and any(kw in tx for kw in BOILERPLATE_KEYWORDS):
            to_delete.append(b['id'])
        elif t == 'divider':
            dividers_before_heritage.append(b['id'])

    # Keep at most 1 divider before Heritage, delete extras
    if len(dividers_before_heritage) > 1:
        for bid in dividers_before_heritage[:-1]:
            to_delete.append(bid)

    unique_deletes = list(dict.fromkeys(to_delete))  # preserve order, dedupe

    if unique_deletes:
        print(f'  CLEAN [{len(unique_deletes)}] {title[:60]}')
        for bid in unique_deletes:
            dr = requests.delete(f'https://api.notion.com/v1/blocks/{bid}', headers=H)
            if dr.status_code not in (200, 404):
                print(f'    ERROR {bid}: {dr.status_code}')
            time.sleep(0.25)
        cleaned += 1
    else:
        print(f'  OK    {title[:60]}')
        already_ok += 1

    time.sleep(0.3)

print(f'\nDone: {cleaned} cleaned, {already_ok} already clean')
