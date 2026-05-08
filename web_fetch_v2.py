#!/usr/bin/env python3
"""web_fetch_v2.py - Enhanced web fetching with structured listing extraction.

Extends web_fetch.py with listing-level data extraction (title, price,
condition, shipping, etc.) so you can distinguish real GPU cards from
backplates, fans, and other accessories.

New subcommands:
  listings <gpu>         - Search for GPU listings with full details
  listings-ebay <gpu>    - Search eBay sold listings specifically

All original subcommands from web_fetch.py are also available:
  fetch <url>            - Fetch a URL and print its content
  search <query>         - Search the web and print results
  techpowerup <gpu>      - Fetch TechPowerUp GPU specs as structured data
  price <gpu>            - Search for GPU pricing from multiple sources

Uses only Python standard library. Shares cache with web_fetch.py.
"""

import sys
import os
import re
import json
from urllib.parse import urlparse, unquote, quote
from dataclasses import dataclass, asdict
from typing import List, Optional

# Import shared infrastructure from web_fetch
from web_fetch import (
    fetch_url,
    search,
    html_to_text,
    _load_cache,
    _save_cache,
    _cache_key,
    _get_cached,
    _set_cached,
    _extract_prices,
    _get_price_range,
    _rate_limit,
    CACHE_FILE,
    CACHE_TTL,
    SCRIPT_DIR,
    HEADERS,
    cmd_search,
    cmd_techpowerup,
    cmd_price,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NON_GPU_KEYWORDS = [
    "backplate", "back plate", "heat spreader",
    "heatsink", "heat sink",
    "fan only", "fans for",
    "shroud", "bracket only",
    "screw", "screws",
    "thermal pad", "thermal paste",
    "power cable", "pcie cable", "adapter cable",
    "riser cable", "extension cable",
    "i/o shield", "io shield",
    "replacement fan", "replacement cooler",
    "box only", "empty box", "no gpu", "no card",
    "waterblock", "water block",
    "slot cover", "blank plate",
    "antenna", "remote",
    "broken for", "salvage",
]

GPU_POSITIVE_KEYWORDS = [
    "graphics card", "video card", "gpu card",
    "graphics adapter",
]


# ---------------------------------------------------------------------------
# Listing data structure
# ---------------------------------------------------------------------------

@dataclass
class Listing:
    title: str = ""
    price: Optional[float] = None
    condition: str = ""
    shipping: str = ""
    shipping_cost: Optional[float] = None
    url: str = ""
    sold_date: str = ""
    source: str = ""
    seller: str = ""
    bids: str = ""
    is_gpu: bool = False
    confidence: float = 0.0

    def to_dict(self):
        return asdict(self)


# ---------------------------------------------------------------------------
# GPU listing detection
# ---------------------------------------------------------------------------

def is_gpu_listing(title: str, gpu_name: str) -> tuple:
    """Check if a listing title is likely the actual GPU card.

    Returns (is_gpu, confidence) where confidence is 0.0-1.0.
    """
    title_lower = title.lower()
    gpu_lower = gpu_name.lower()

    for kw in NON_GPU_KEYWORDS:
        if kw in title_lower:
            return False, 0.1

    # "For parts" listings are still GPUs, just not working ones
    is_parts = any(p in title_lower for p in [
        "for parts", "not working", "as-is", "as is",
        "defective", "untested", "for repair",
    ])
    parts_penalty = 0.3 if is_parts else 0.0

    # Check how many GPU name words appear in the title
    skip_words = {"nvidia", "amd", "radeon", "geforce", "the", "a", "an"}
    gpu_words = [w for w in gpu_lower.split() if w not in skip_words and len(w) > 1]

    if not gpu_words:
        return False, 0.0

    matches = sum(1 for w in gpu_words if w in title_lower)
    word_ratio = matches / len(gpu_words)

    has_positive = any(kw in title_lower for kw in GPU_POSITIVE_KEYWORDS)

    # Model number match (most reliable)
    gpu_numbers = re.findall(r'\b(\d{2,}[a-z]?)\b', gpu_lower)
    number_match = any(n in title_lower for n in gpu_numbers) if gpu_numbers else False

    # Watch for wrong-generation matches
    # e.g. "Radeon RX 6800 XT" should not match "GeForce 6800 XT"
    # Check if the manufacturer matches
    manufacturer_match = False
    if "geforce" in gpu_lower or "gtx" in gpu_lower or "rtx" in gpu_lower:
        manufacturer_match = any(m in title_lower for m in ["geforce", "gtx", "rtx", "nvidia"])
    elif "radeon" in gpu_lower or "rx" in gpu_lower:
        manufacturer_match = any(m in title_lower for m in ["radeon", "rx", "amd"])

    confidence = 0.0
    if number_match:
        confidence += 0.35
    if word_ratio >= 0.8:
        confidence += 0.3
    elif word_ratio >= 0.5:
        confidence += 0.15
    if has_positive:
        confidence += 0.15
    if manufacturer_match:
        confidence += 0.2

    confidence = min(1.0, confidence) - parts_penalty

    if confidence >= 0.4:
        return True, max(0.0, confidence)

    return False, confidence


# ---------------------------------------------------------------------------
# eBay listing parser
# ---------------------------------------------------------------------------

def _parse_ebay_listings(html_content, gpu_name=""):
    """Parse eBay shop/search listing page into structured Listing objects.

    eBay uses s-card containers with:
    - s-card__title for listing titles
    - s-card__price for prices
    - s-card__subtitle for condition (Brand New, Pre-Owned, etc.)
    - s-card__link for URLs
    """
    listings = []

    # Extract all s-card blocks
    cards = re.findall(
        r'<div[^>]*class="[^"]*s-card[^"]*"[^>]*>(.*?)(?=<div[^>]*class="[^"]*s-card[^"]*"|$)',
        html_content, re.DOTALL,
    )

    for card_html in cards:
        listing = Listing(source="ebay")

        # Title - inside s-card__title > span
        title_match = re.search(
            r'class=s-card__title[^>]*><span[^>]*>(.*?)</span>',
            card_html,
        )
        if not title_match:
            title_match = re.search(
                r'class="[^"]*s-card__title[^"]*"[^>]*>(.*?)</(?:div|h[23])>',
                card_html, re.DOTALL,
            )
        if title_match:
            listing.title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()

        if not listing.title or listing.title.lower() in ("shop on ebay", "new listing"):
            continue

        # Price
        price_match = re.search(
            r's-card__price[^>]*>\$?([\d,]+\.?\d{0,2})<',
            card_html,
        )
        if price_match:
            try:
                listing.price = float(price_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # Condition (subtitle)
        cond_match = re.search(
            r'class=s-card__subtitle><span[^>]*>(.*?)</span>',
            card_html,
        )
        if cond_match:
            listing.condition = re.sub(r'<[^>]+>', '', cond_match.group(1)).strip().rstrip(" ·")

        # Shipping
        ship_match = re.search(r'\+([\d,.]+)\s*delivery', card_html)
        if ship_match:
            try:
                listing.shipping_cost = float(ship_match.group(1))
                listing.shipping = f"+${listing.shipping_cost} delivery"
            except ValueError:
                pass
        elif re.search(r'free\s*(?:delivery|shipping)', card_html, re.IGNORECASE):
            listing.shipping_cost = 0.0
            listing.shipping = "Free delivery"

        # URL
        url_match = re.search(
            r'<a[^>]*class="[^"]*s-card__link[^"]*"[^>]*href="([^"]*)"',
            card_html,
        )
        if url_match:
            listing.url = url_match.group(1)

        # GPU detection
        if gpu_name:
            listing.is_gpu, listing.confidence = is_gpu_listing(listing.title, gpu_name)

        listings.append(listing)

    return listings


def _parse_newegg_listings(html_content, gpu_name=""):
    """Parse Newegg search page into structured Listing objects."""
    listings = []

    items = re.findall(
        r'<div[^>]*class="[^"]*item-cell[^"]*"[^>]*>(.*?)</div>\s*(?=<div[^>]*class="[^"]*item-cell|$)',
        html_content, re.DOTALL,
    )

    for item_html in items:
        listing = Listing(source="newegg", condition="New")

        title_match = re.search(
            r'<a[^>]*class="[^"]*item-title[^"]*"[^>]*>(.*?)</a>',
            item_html, re.DOTALL,
        )
        if title_match:
            listing.title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()

        if not listing.title:
            continue

        price_match = re.search(
            r'<(?:li|span)[^>]*class="[^"]*price-[^"]*"[^>]*>.*?\$([\d,]+\.?\d*)',
            item_html, re.DOTALL,
        )
        if price_match:
            try:
                listing.price = float(price_match.group(1).replace(",", "").strip())
            except ValueError:
                pass

        url_match = re.search(
            r'<a[^>]*class="[^"]*item-title[^"]*"[^>]*href="([^"]*)"',
            item_html,
        )
        if url_match:
            listing.url = url_match.group(1)

        ship_match = re.search(
            r'<li[^>]*class="[^"]*price-ship[^"]*"[^>]*>(.*?)</li>',
            item_html, re.DOTALL,
        )
        if ship_match:
            ship_text = re.sub(r'<[^>]+>', '', ship_match.group(1)).strip()
            listing.shipping = ship_text
            if "free" in ship_text.lower():
                listing.shipping_cost = 0.0

        if gpu_name:
            listing.is_gpu, listing.confidence = is_gpu_listing(listing.title, gpu_name)

        listings.append(listing)

    return listings


# ---------------------------------------------------------------------------
# Enhanced listings command
# ---------------------------------------------------------------------------

def cmd_listings(gpu_name, ebay_only=False):
    """Search for GPU listings and return structured results."""
    min_p, max_p = _get_price_range(gpu_name)
    results = {
        "gpu": gpu_name,
        "listings": [],
        "best_used": None,
        "best_used_gpu": None,
        "summary": "",
    }

    all_listings = []

    # --- eBay listings via shop page (search/sch pages return 403) ---
    # Build shop URL slug from GPU name
    slug = gpu_name.lower().replace(" ", "-")
    shop_url = f"https://www.ebay.com/shop/{slug}?_nkw={quote(gpu_name)}"
    content = fetch_url(shop_url)
    if content:
        listings = _parse_ebay_listings(content, gpu_name)
        if listings:
            all_listings.extend(listings)

    # Fallback: search engine -> eBay pages
    if not all_listings:
        for query in [f'{gpu_name} site:ebay.com -fan -backplate']:
            search_results = search(query, num_results=5)
            for title, url in search_results:
                if "ebay.com" in url:
                    content = fetch_url(url)
                    if content:
                        listings = _parse_ebay_listings(content, gpu_name)
                        all_listings.extend(listings)
                        if listings:
                            break
            if all_listings:
                break

    # --- Newegg (if not ebay_only) ---
    if not ebay_only:
        newegg_url = f"https://www.newegg.com/p/pl?d={quote(gpu_name)}"
        content = fetch_url(newegg_url)
        if content:
            listings = _parse_newegg_listings(content, gpu_name)
            all_listings.extend(listings)

    # --- Classify and rank ---
    gpu_listings = [l for l in all_listings if l.is_gpu and l.price is not None]
    non_gpu_listings = [l for l in all_listings if not l.is_gpu and l.price is not None]

    gpu_listings.sort(key=lambda l: (-l.confidence, l.price or 99999))

    # Build output
    results["listings"] = [l.to_dict() for l in all_listings[:30]]
    results["gpu_listings"] = [l.to_dict() for l in gpu_listings[:20]]
    results["non_gpu_listings"] = [l.to_dict() for l in non_gpu_listings[:10]]
    results["total_listings"] = len(all_listings)
    results["gpu_listing_count"] = len(gpu_listings)

    # Best used price from GPU-only listings
    if gpu_listings:
        prices = sorted([l.price for l in gpu_listings if l.price])
        if prices:
            idx = max(0, len(prices) // 4)
            results["best_used_gpu"] = prices[idx]
            results["best_used"] = prices[len(prices) // 2]

    # Fallback: best used from all listings
    if not results["best_used"] and all_listings:
        all_prices = sorted(set(l.price for l in all_listings if l.price is not None))
        if all_prices:
            results["best_used"] = all_prices[len(all_prices) // 2]

    # Summary
    if gpu_listings:
        prices = [l.price for l in gpu_listings if l.price]
        sample = gpu_listings[0]
        results["summary"] = (
            f"Found {len(gpu_listings)} GPU listings. "
            f"Prices: ${min(prices):.2f} - ${max(prices):.2f}. "
            f"Best used (GPU-only): ${results.get('best_used_gpu', 'N/A')}. "
            f"Top: \"{sample.title}\" @ ${sample.price}"
        )
    else:
        results["summary"] = (
            f"No GPU listings found for '{gpu_name}'. "
            f"{len(all_listings)} total listings."
        )

    print(json.dumps(results, indent=2))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()

    # New v2 commands
    if cmd == "listings":
        if len(sys.argv) < 3:
            print("Usage: web_fetch_v2.py listings <gpu_name>", file=sys.stderr)
            sys.exit(1)
        gpu = " ".join(sys.argv[2:])
        cmd_listings(gpu)

    elif cmd == "listings-ebay":
        if len(sys.argv) < 3:
            print("Usage: web_fetch_v2.py listings-ebay <gpu_name>", file=sys.stderr)
            sys.exit(1)
        gpu = " ".join(sys.argv[2:])
        cmd_listings(gpu, ebay_only=True)

    # Original commands (delegate to web_fetch)
    elif cmd == "fetch":
        if len(sys.argv) < 3:
            print("Usage: web_fetch_v2.py fetch <url>", file=sys.stderr)
            sys.exit(1)
        content = fetch_url(sys.argv[2])
        if content is None:
            sys.exit(1)
        print(content)

    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: web_fetch_v2.py search <query>", file=sys.stderr)
            sys.exit(1)
        cmd_search(" ".join(sys.argv[2:]))

    elif cmd in ("techpowerup", "tpu"):
        if len(sys.argv) < 3:
            print("Usage: web_fetch_v2.py techpowerup <gpu_name_or_url>", file=sys.stderr)
            sys.exit(1)
        cmd_techpowerup(" ".join(sys.argv[2:]))

    elif cmd == "price":
        if len(sys.argv) < 3:
            print("Usage: web_fetch_v2.py price <gpu_name>", file=sys.stderr)
            sys.exit(1)
        cmd_price(" ".join(sys.argv[2:]))

    elif cmd in ("--help", "-h"):
        print(__doc__)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
