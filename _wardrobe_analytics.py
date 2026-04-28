#!/usr/bin/env python3
import os, requests, re
from collections import defaultdict
from datetime import date, timedelta
from dotenv import load_dotenv
load_dotenv()

NOTION_TOKEN = os.environ['NOTION_TOKEN']
ITEMS_DB = 'ad079964-9690-43ae-9fa8-5a4f3ca1a9ee'
TODAY = date(2026, 4, 23)
headers = {'Authorization': f'Bearer {NOTION_TOKEN}', 'Notion-Version': '2022-06-28', 'Content-Type': 'application/json'}

items, cursor = [], None
while True:
    body = {'page_size': 100}
    if cursor: body['start_cursor'] = cursor
    data = requests.post(f'https://api.notion.com/v1/databases/{ITEMS_DB}/query', headers=headers, json=body).json()
    items.extend(data.get('results', []))
    if not data.get('has_more'): break
    cursor = data.get('next_cursor')

items.sort(key=lambda x: x.get('created_time',''), reverse=True)
in_transit_ids = {x['id'] for x in items[:18]}

def get_text(prop): return ''.join(t['plain_text'] for t in prop) if prop else ''

rows = []
for item in items:
    if item['id'] in in_transit_ids: continue
    p = item['properties']
    if p.get('with/for mum', {}).get('checkbox'): continue
    sku      = get_text(p.get('SKU',{}).get('rich_text',[]))
    parts    = sku.split('-')
    brand    = parts[0] if parts else 'UNK'
    sku_cat  = parts[1] if len(parts) >= 2 else 'UNK'
    sku_color= parts[2] if len(parts) >= 3 else ''
    name     = get_text(p.get('Second best',{}).get('title',[])) or get_text(p.get('Old Title',{}).get('rich_text',[]))
    fits     = (p.get('Fits',{}).get('formula') or {}).get('number') or 0
    sgd      = p.get('SGD',{}).get('number') or 0
    retail_usd = p.get('Retail Price (USD)',{}).get('number') or 0
    cpw_f    = p.get('CPW (SGD)',{}).get('formula',{})
    cpw      = cpw_f.get('number') if cpw_f.get('type') == 'number' else None
    retail_cpw_f = p.get('Retail CPW (USD)',{}).get('formula',{})
    retail_cpw   = retail_cpw_f.get('number') if retail_cpw_f.get('type') == 'number' else None
    fav      = p.get('Favourite',{}).get('checkbox', False)
    last_worn_raw = ((p.get('Last Worn',{}).get('rollup') or {}).get('date') or {}).get('start')
    last_worn = date.fromisoformat(last_worn_raw[:10]) if last_worn_raw else None
    bought_raw = (p.get('Date I bought/own',{}).get('date') or {}).get('start')
    bought   = date.fromisoformat(bought_raw[:10]) if bought_raw else None
    why_tags = p.get('Why I own it (Tags)',{}).get('relation',[])
    rows.append(dict(name=name, brand=brand, sku_cat=sku_cat, sku_color=sku_color,
                     fits=fits, sgd=sgd, retail_usd=retail_usd, cpw=cpw, retail_cpw=retail_cpw,
                     fav=fav, last_worn=last_worn, bought=bought, why_tags=why_tags, id=item['id']))

print(f"Rows analysed: {len(rows)}  (excluded 18 in-transit + mum's items)\n")
print("="*70)

MACRO = {'TOP':'Tops','SHR':'Tops','KNT':'Tops','TRS':'Bottoms','SKT':'Bottoms',
         'DRS':'Dresses','OTW':'Outerwear','SHO':'Shoes','BAG':'Bags',
         'SCF':'Scarves & Accessories','JMP':'Jumpsuits',
         'JWL':'Jewelry','XAU':'Jewelry','DIA':'Jewelry',
         'WOW':'Wow Pieces','BAS':'Basics','OTH':'Other'}
NAME_MACROS = [
    (r'shoe|boot|heel|sneaker|loafer|slipper|sandal','Shoes'),
    (r'bag|purse|tote|clutch|wallet|pochette','Bags'),
    (r'dress|gown|qipao|cheong','Dresses'),
    (r'trouser|pant|jean|short|bermuda','Bottoms'),
    (r'skirt','Bottoms'),
    (r'coat|jacket|blazer|parka|puffer|cape|outerwear','Outerwear'),
    (r'scarf|stole|shawl','Scarves & Accessories'),
    (r'jumpsuit|playsuit|romper','Jumpsuits'),
    (r'top|shirt|blouse|tee|polo|sweater|knit|pullover','Tops'),
    (r'diamond|gold|ring|necklace|bracelet|earring|watch|jewel|crystal','Jewelry'),
]
def macro(r):
    m = MACRO.get(r['sku_cat'])
    if m: return m
    n = r['name'].lower()
    for pat, cat in NAME_MACROS:
        if re.search(pat, n): return cat
    return 'Other'

# ── A1: Most worn item per macro category ─────────────────────────────────────
print("A1 — MOST WORN ITEM PER MACRO CATEGORY (excl. jewelry/watches)\n")
cat_best = defaultdict(lambda: {'fits':0,'name':''})
for r in rows:
    mc = macro(r)
    if mc == 'Jewelry': continue
    if r['fits'] > cat_best[mc]['fits']:
        cat_best[mc] = {'fits':r['fits'],'name':r['name'][:65]}
for cat in sorted(cat_best):
    b = cat_best[cat]
    print(f"  {cat:<28} {b['fits']:>4} wears  →  {b['name']}")

# ── A2: Average CPW and Retail CPW ────────────────────────────────────────────
print("\nA2 — AVERAGE COST PER WEAR\n")
cpw_vals = [r['cpw'] for r in rows if r['cpw'] and r['cpw'] > 0 and r['fits'] > 0]
retail_cpw_vals = [r['retail_cpw'] for r in rows if r['retail_cpw'] and r['retail_cpw'] > 0 and r['fits'] > 0]
print(f"  Overall avg CPW (SGD):        {sum(cpw_vals)/len(cpw_vals):.2f}  (n={len(cpw_vals)} items)")
if retail_cpw_vals:
    print(f"  Overall avg Retail CPW (USD): {sum(retail_cpw_vals)/len(retail_cpw_vals):.2f}  (n={len(retail_cpw_vals)} items)")
print()
cat_cpw = defaultdict(list); cat_retail = defaultdict(list)
for r in rows:
    mc = macro(r)
    if r['cpw'] and r['cpw'] > 0 and r['fits'] > 0: cat_cpw[mc].append(r['cpw'])
    if r['retail_cpw'] and r['retail_cpw'] > 0 and r['fits'] > 0: cat_retail[mc].append(r['retail_cpw'])
all_cats = sorted(set(list(cat_cpw)+list(cat_retail)))
print(f"  {'Category':<28} {'Avg CPW SGD':>12} {'Avg Retail CPW USD':>20}")
print(f"  {'-'*62}")
for cat in all_cats:
    c = f"{sum(cat_cpw[cat])/len(cat_cpw[cat]):.2f}" if cat_cpw[cat] else 'n/a'
    rc = f"{sum(cat_retail[cat])/len(cat_retail[cat]):.2f}" if cat_retail[cat] else 'n/a'
    print(f"  {cat:<28} {c:>12} {rc:>20}")

# ── A3: Favourites with low wear counts ───────────────────────────────────────
print("\nA3 — FAVOURITES WITH LOW WEAR COUNTS\n")
favs = sorted([r for r in rows if r['fav']], key=lambda x: x['fits'])
print(f"  Total favourites: {len(favs)}\n")
print(f"  {'Item':<55} {'Wears':>6} {'CPW SGD':>9}")
print(f"  {'-'*72}")
for r in favs:
    cpw_str = f"{r['cpw']:.1f}" if r['cpw'] else 'n/a'
    print(f"  {r['name'][:54]:<55} {r['fits']:>6} {cpw_str:>9}")

# ── A4: Items by Last Worn recency ────────────────────────────────────────────
print("\nA4 — ITEMS BY LAST WORN RECENCY\n")
for label, days in [('Last 3 months',90),('Last 12 months',365),('Last 24 months',730),('Last 36 months',1095)]:
    cutoff = TODAY - timedelta(days=days)
    n = sum(1 for r in rows if r['last_worn'] and r['last_worn'] >= cutoff)
    print(f"  {label:<22}: {n:>4} items")
print()
never_owned_1yr = [r for r in rows if r['fits']==0 and r['bought'] and (TODAY-r['bought']).days>365]
stale_24 = [r for r in rows if r['fits']>0 and (not r['last_worn'] or (TODAY-r['last_worn']).days>730) and r['bought'] and (TODAY-r['bought']).days>730]
stale_36 = [r for r in rows if r['fits']>0 and (not r['last_worn'] or (TODAY-r['last_worn']).days>1095) and r['bought'] and (TODAY-r['bought']).days>1095]
print(f"  Never worn (owned 1+ yr):      {len(never_owned_1yr)} items")
for r in never_owned_1yr[:6]: print(f"    → {r['name'][:65]}  (bought {r['bought']})")
print(f"\n  Not touched in 24+ months:     {len(stale_24)} items")
for r in sorted(stale_24, key=lambda x: x['last_worn'] or date(2000,1,1))[:8]:
    print(f"    → {r['name'][:55]}  last worn {r['last_worn']}")
print(f"\n  Not touched in 36+ months:     {len(stale_36)} items")
for r in sorted(stale_36, key=lambda x: x['last_worn'] or date(2000,1,1))[:8]:
    print(f"    → {r['name'][:55]}  last worn {r['last_worn']}")

# ── A5: Brand worn most (wears/item, excl jewelry) ────────────────────────────
print("\nA5 — BRAND: WEARS PER ITEM OWNED (excl. jewelry/gold)\n")
EXCL = {'JWL','XAU','DIA'}
brand_data = defaultdict(lambda: {'items':0,'total_wears':0})
for r in rows:
    if r['sku_cat'] in EXCL: continue
    if re.search(r'gold|diamond|ring|necklace|bracelet|earring|watch', r['name'].lower()): continue
    if r['brand'] in ('UNK',''): continue
    brand_data[r['brand']]['items'] += 1
    brand_data[r['brand']]['total_wears'] += r['fits']
brand_ranked = sorted([(b,d['items'],d['total_wears'],d['total_wears']/d['items'])
                        for b,d in brand_data.items() if d['items']>=2], key=lambda x:-x[3])
print(f"  {'Brand':<12} {'Items':>6} {'Total wears':>12} {'Wears/item':>12}")
print(f"  {'-'*46}")
for b,n_items,tw,wpi in brand_ranked[:20]:
    print(f"  {b:<12} {n_items:>6} {tw:>12} {wpi:>12.1f}")

# ── A6: Best deals ────────────────────────────────────────────────────────────
print("\nA6 — BEST DEALS (retail savings × wear progress to 30)\n")
deals = []
for r in rows:
    if not r['retail_usd'] or r['retail_usd']==0: continue
    retail_sgd = r['retail_usd'] * 1.35
    paid_sgd   = r['sgd'] if r['sgd'] > 0 else retail_sgd
    savings    = max(0, retail_sgd - paid_sgd)
    score      = savings * min(r['fits']/30, 1.0)
    deals.append((score, r['name'], r['fits'], paid_sgd, retail_sgd, savings))
deals.sort(reverse=True)
print(f"  {'Item':<48} {'Wears':>6} {'Paid SGD':>9} {'Retail SGD':>11} {'Savings':>9} {'Score':>7}")
print(f"  {'-'*93}")
for score,name,fits,paid,retail,savings in deals[:15]:
    print(f"  {name[:47]:<48} {fits:>6} {paid:>9.0f} {retail:>11.0f} {savings:>9.0f} {score:>7.0f}")

# ── A7: Colour analysis ───────────────────────────────────────────────────────
print("\nA7 — COLOUR ANALYSIS\n")
color_data = defaultdict(lambda: {'items':0,'total_wears':0})
for r in rows:
    col = r['sku_color'] or 'UNK'
    color_data[col]['items'] += 1
    color_data[col]['total_wears'] += r['fits']
color_ranked = sorted(color_data.items(), key=lambda x:-x[1]['total_wears'])
print(f"  {'Color':<10} {'Items':>6} {'Total wears':>12} {'Avg wears':>10}")
print(f"  {'-'*42}")
for col,d in color_ranked[:20]:
    print(f"  {col:<10} {d['items']:>6} {d['total_wears']:>12} {d['total_wears']/d['items']:>10.1f}")

# ── A8: Dead weight ───────────────────────────────────────────────────────────
print("\nA8 — DEAD WEIGHT: OWNED 12+ MONTHS, NEVER WORN\n")
dead = sorted([r for r in rows if r['fits']==0 and r['bought'] and (TODAY-r['bought']).days>365],
              key=lambda x: x['bought'] or date(2099,1,1))
print(f"  Total: {len(dead)} items\n")
print(f"  {'Item':<58} {'Bought':>12} {'SGD':>7}")
print(f"  {'-'*80}")
for r in dead:
    print(f"  {r['name'][:57]:<58} {str(r['bought']):>12} {r['sgd']:>7.0f}")

# ── A9: CPW trend by purchase year ────────────────────────────────────────────
print("\nA9 — CPW TREND BY PURCHASE YEAR\n")
year_data = defaultdict(lambda: {'cpw_vals':[],'fits_vals':[],'count':0})
for r in rows:
    if not r['bought']: continue
    yr = r['bought'].year
    year_data[yr]['count'] += 1
    if r['cpw'] and r['cpw']>0 and r['fits']>0: year_data[yr]['cpw_vals'].append(r['cpw'])
    if r['fits']>0: year_data[yr]['fits_vals'].append(r['fits'])
print(f"  {'Year':>6} {'Items':>7} {'Avg CPW SGD':>13} {'Avg wears':>11}")
print(f"  {'-'*42}")
for yr in sorted(year_data):
    d = year_data[yr]
    avg_cpw  = f"{sum(d['cpw_vals'])/len(d['cpw_vals']):.2f}" if d['cpw_vals'] else 'n/a'
    avg_fits = f"{sum(d['fits_vals'])/len(d['fits_vals']):.1f}" if d['fits_vals'] else 'n/a'
    print(f"  {yr:>6} {d['count']:>7} {avg_cpw:>13} {avg_fits:>11}")
print("\n" + "="*70)
