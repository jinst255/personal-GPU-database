"""Scrape GPU prices using Google search.
Google strips $ signs but leaves price numbers in context.
Strategy: search for card + 'price', extract numbers in expected price range."""
import csv, re, time, sys
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.parse import quote

H = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0'}

def fetch(url, timeout=15):
    try:
        req = Request(url, headers=H)
        with urlopen(req, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='replace')
    except:
        return None

def get_prices_from_google(query, min_price, max_price):
    """Search Google and extract price numbers in range."""
    q = quote(query)
    html = fetch(f'https://www.google.com/search?q={q}')
    if not html:
        return []

    # Find numbers with optional commas: 1,599 or 1599
    nums = re.findall(r'([\d,]+\.?\d*)', html)
    prices = []
    for n in nums:
        try:
            v = float(n.replace(',', ''))
            if min_price <= v <= max_price:
                prices.append(v)
        except:
            pass

    # Remove duplicates and sort
    prices = sorted(set(prices))
    return prices

def price_for_gpu(name, expected_min, expected_max):
    """Get best new price for a GPU via Google search."""
    prices = get_prices_from_google(f'{name} price buy newegg amazon', expected_min, expected_max)
    if not prices:
        # Try broader search
        prices = get_prices_from_google(f'{name} price', expected_min, expected_max)
    if not prices:
        return None
    # Return the most common low price (lower quartile)
    idx = max(0, len(prices) // 4)
    return round(prices[idx], 2)

def used_price_for_gpu(name, expected_min, expected_max):
    """Get used price for a GPU via Google search."""
    prices = get_prices_from_google(f'{name} ebay used price sold', expected_min, expected_max)
    if not prices:
        prices = get_prices_for_gpu(f'{name} used price', int(expected_min * 0.5), expected_max)
    if not prices:
        return None
    # Median
    mid = len(prices) // 2
    return round(prices[mid], 2)

# Price range estimates by GPU tier
def get_expected_range(name):
    """Return (new_min, new_max) price range based on GPU name."""
    name_lower = name.lower()
    if 'rtx 5090' in name_lower:
        return (1500, 4000)
    elif 'rtx 5080' in name_lower:
        return (800, 1500)
    elif 'rtx 5070 ti' in name_lower:
        return (600, 1000)
    elif 'rtx 5070' in name_lower and 'ti' not in name_lower:
        return (400, 800)
    elif 'rtx 4090' in name_lower:
        return (1500, 3500)
    elif 'rtx 4080' in name_lower:
        return (800, 1500)
    elif 'rtx 4070 ti' in name_lower:
        return (600, 1000)
    elif 'rtx 4070' in name_lower and 'ti' not in name_lower:
        return (400, 700)
    elif 'rtx 4060 ti' in name_lower:
        return (250, 550)
    elif 'rtx 4060' in name_lower and 'ti' not in name_lower:
        return (200, 400)
    elif 'rtx 3090' in name_lower:
        return (500, 1500)
    elif 'rtx 3080' in name_lower:
        return (400, 900)
    elif 'rtx 3070' in name_lower:
        return (300, 600)
    elif 'rtx 3060' in name_lower:
        return (200, 450)
    elif 'rtx 3050' in name_lower:
        return (150, 300)
    elif 'rtx 2080' in name_lower:
        return (300, 800)
    elif 'rtx 2070' in name_lower:
        return (200, 600)
    elif 'rtx 2060' in name_lower:
        return (200, 400)
    elif 'gtx 1660' in name_lower:
        return (100, 300)
    elif 'gtx 1650' in name_lower:
        return (80, 200)
    elif 'gtx 1080' in name_lower:
        return (100, 400)
    elif 'gtx 1070' in name_lower:
        return (80, 300)
    elif 'gtx 1060' in name_lower:
        return (60, 200)
    elif 'gtx 1050' in name_lower:
        return (40, 150)
    elif 'gtx 980' in name_lower:
        return (50, 200)
    elif 'gtx 970' in name_lower:
        return (40, 150)
    elif 'gtx 960' in name_lower:
        return (30, 100)
    elif 'gtx 780' in name_lower:
        return (30, 150)
    elif 'gtx 750' in name_lower:
        return (20, 80)
    elif 'gtx 680' in name_lower:
        return (20, 80)
    elif 'gtx 580' in name_lower:
        return (20, 80)
    elif 'titan' in name_lower:
        return (100, 5000)
    elif 'rx 9070' in name_lower:
        return (400, 800)
    elif 'rx 9060' in name_lower:
        return (250, 500)
    elif 'rx 7900' in name_lower:
        return (500, 1200)
    elif 'rx 7800' in name_lower:
        return (350, 600)
    elif 'rx 7700' in name_lower:
        return (300, 500)
    elif 'rx 7600' in name_lower:
        return (200, 400)
    elif 'rx 6950' in name_lower:
        return (400, 800)
    elif 'rx 6900' in name_lower:
        return (350, 700)
    elif 'rx 6800' in name_lower:
        return (300, 600)
    elif 'rx 6750' in name_lower:
        return (250, 500)
    elif 'rx 6700' in name_lower:
        return (200, 450)
    elif 'rx 6650' in name_lower:
        return (150, 350)
    elif 'rx 6600' in name_lower and 'xt' not in name_lower:
        return (150, 300)
    elif 'rx 6600' in name_lower:
        return (150, 350)
    elif 'rx 6500' in name_lower:
        return (80, 200)
    elif 'rx 6400' in name_lower:
        return (60, 150)
    elif 'rx 5700' in name_lower:
        return (150, 400)
    elif 'rx 5600' in name_lower:
        return (120, 300)
    elif 'rx 5500' in name_lower:
        return (80, 200)
    elif 'rx 590' in name_lower:
        return (80, 200)
    elif 'rx 580' in name_lower:
        return (60, 180)
    elif 'rx 570' in name_lower:
        return (50, 150)
    elif 'rx 560' in name_lower:
        return (30, 100)
    elif 'rx 550' in name_lower:
        return (20, 80)
    elif 'rx 480' in name_lower:
        return (50, 150)
    elif 'rx 470' in name_lower:
        return (40, 120)
    elif 'rx 460' in name_lower:
        return (30, 80)
    elif 'r9 fury' in name_lower or 'r9 390' in name_lower or 'r9 290' in name_lower:
        return (50, 300)
    elif 'r9 280' in name_lower or 'r9 270' in name_lower:
        return (30, 150)
    elif 'vega' in name_lower:
        return (80, 400)
    elif 'radeon vii' in name_lower:
        return (100, 400)
    elif 'hd 7970' in name_lower:
        return (20, 80)
    elif 'hd 79' in name_lower:
        return (15, 60)
    elif 'hd 78' in name_lower:
        return (15, 50)
    elif 'hd 77' in name_lower:
        return (10, 40)
    elif 'radeon pro' in name_lower:
        return (200, 5000)
    else:
        return (10, 5000)

ts = datetime.now().strftime('%Y-%m-%dT%H:%M')

with open('gpu_database.csv', newline='') as f:
    reader = csv.reader(f)
    header = next(reader)
    rows = [list(r) for r in reader]

COL = {name: i for i, name in enumerate(header)}

# Skip mobile GPUs
to_price = [(i, r) for i, r in enumerate(rows) if r[COL['category']] != 'mobile']
print(f"GPUs to price: {len(to_price)}")

updated = 0
for idx, r in to_price:
    name = r[COL['gpu_name']]
    cat = r[COL['category']]
    new_min, new_max = get_expected_range(name)
    updated += 1
    print(f"\n[{updated}/{len(to_price)}] {name} (range: ${new_min}-${new_max})")

    # New price via Google
    new_price = price_for_gpu(name, new_min, new_max)
    if new_price:
        r[COL['price_usd_new_current']] = str(new_price)
        print(f"  New price: ${new_price}")

    # eBay used price (skip datacenter)
    if cat != 'datacenter':
        used_price = price_for_gpu(f'{name} used ebay', int(new_min * 0.4), new_max)
        if used_price:
            r[COL['price_usd_ebay_used']] = str(used_price)
            q = quote(name + ' GPU')
            r[COL['link_ebay']] = f'https://www.ebay.com/sch/i.html?_nkw={q}&LH_Sold=1'
            print(f"  Used price: ${used_price}")

    # Generate search links for all cards
    q = quote(name)
    r[COL['link_newegg']] = f'https://www.newegg.com/p/pl?d={q}'
    r[COL['link_amazon']] = f'https://www.amazon.com/s?k={q}'
    r[COL['link_bh']] = f'https://www.bhphotovideo.com/c/search?q={q}'

    r[COL['last_modified']] = ts
    time.sleep(2)  # Be nice to Google

    # Save every 15 entries
    if updated % 15 == 0:
        with open('gpu_database.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for row in rows:
                writer.writerow(row)
        print(f"\n=== Saved progress at {updated} entries ===\n")

# Recalculate derived fields
for r in rows:
    price_new = None
    price_used = None
    vram = None
    fp32 = None
    try:
        v = r[COL['price_usd_new_current']]
        price_new = float(v) if v not in ('null', '') else None
    except: pass
    try:
        v = r[COL['price_usd_ebay_used']]
        price_used = float(v) if v not in ('null', '') else None
    except: pass
    try:
        v = r[COL['vram_gb']]
        vram = float(v) if v not in ('null', '') else None
    except: pass
    try:
        v = r[COL['fp32_tflops']]
        fp32 = float(v) if v not in ('null', '') else None
    except: pass

    if price_new and vram and vram > 0:
        r[COL['cost_per_gb_vram_new_usd']] = str(round(price_new / vram, 2))
    if price_used and vram and vram > 0:
        r[COL['cost_per_gb_vram_used_usd']] = str(round(price_used / vram, 2))
    if price_new and fp32 and fp32 > 0:
        r[COL['fp32_per_dollar_new']] = str(round(fp32 / price_new, 4))
    if price_used and fp32 and fp32 > 0:
        r[COL['fp32_per_dollar_used']] = str(round(fp32 / price_used, 4))

# Final save
with open('gpu_database.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)

print(f"\nDone. Updated {updated} GPUs.")
print(f"New current: {sum(1 for r in rows if r[COL['price_usd_new_current']] not in ('null',''))}/{len(rows)}")
print(f"eBay used: {sum(1 for r in rows if r[COL['price_usd_ebay_used']] not in ('null',''))}/{len(rows)}")
