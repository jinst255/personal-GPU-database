#!/usr/bin/env python3
"""web_fetch_v3.py - Enhanced GPU data/pricing fetcher with enterprise support.

Extends web_fetch.py with per-domain rate limiting, GPU classification,
enterprise GPU price fetching, and improved eBay/consumer price fetching.

REQUIRES: web_fetch.py in the same directory.

USAGE:
  python3 web_fetch_v3.py <command> [args]

COMMANDS:

  price <gpu>
    Fetch pricing for a GPU. Auto-detects whether it's consumer, professional,
    or datacenter and uses the appropriate search strategy.
      $ python3 web_fetch_v3.py price "GeForce RTX 4090"
      $ python3 web_fetch_v3.py price "NVIDIA H100 SXM5 80 GB"
      $ python3 web_fetch_v3.py price "Quadro GV100"

  price-dc <gpu>
    Same as price but forces datacenter/enterprise mode. Use for cards that
    might not auto-detect correctly (e.g., older Tesla cards).
      $ python3 web_fetch_v3.py price-dc "Tesla M40 24 GB"

  batch <gpu1>,<gpu2>,<gpu3>
    Process multiple GPUs in one run. Separate names with commas. Each GPU
    is auto-classified and priced with the appropriate strategy. Outputs a
    JSON array with all results plus a summary.
      $ python3 web_fetch_v3.py batch "Tesla M40 24 GB,GeForce RTX 4090,Quadro GV100"

  listings <gpu>
    Search for GPU listings with full details (title, price, condition).
    Searches eBay and Newegg via search engine intermediary.
      $ python3 web_fetch_v3.py listings "GeForce RTX 4090"

  listings-ebay <gpu>
    Same as listings but only searches eBay.

  techpowerup <gpu>
    Fetch TechPowerUp GPU specs as structured data (VRAM, cores, clocks, etc.)
    Also supplements with Wikipedia data when available.
      $ python3 web_fetch_v3.py techpowerup "GeForce RTX 5090"

  search <query>
    Search the web and print results.
      $ python3 web_fetch_v3.py search "RTX 5090 price"

  fetch <url>
    Fetch a URL and print its content.

OUTPUT:
  All commands output JSON to stdout. Diagnostic messages (rate limiting,
  fetch errors, parser warnings) go to stderr. To capture just the JSON:
      $ python3 web_fetch_v3.py price "RTX 4090" 2>/dev/null
  To see what the tool is doing behind the scenes:
      $ python3 web_fetch_v3.py price "RTX 4090" 1>/dev/null

GPU CLASSIFICATION:
  Cards are auto-classified as consumer, professional, or datacenter:
    consumer:     GeForce RTX, GTX, Radeon RX, etc.
    professional: Quadro, RTX Ada, Radeon Pro, RTX A-series
    datacenter:   H100, A100, Tesla, Instinct MI, L4, L40, etc.
  Classification drives price range filtering and source selection.

CACHING:
  Uses a separate cache from web_fetch.py (prefix "v3" vs "fetch") to
  avoid cross-contamination. Cached entries last 4 hours. Cache is stored
  in web_cache.json in the same directory.

RATE LIMITING:
  Per-domain rate limiting with domain-specific delays:
    ebay.com:         3.0s    amazon.com:      2.5s
    newegg.com:       2.5s    search engines:  1.0-1.5s
    enterprise sites: 2.0s    default:         1.5s
"""

import sys
import os
import re
import json
import time
import html as html_module
from urllib.parse import urlparse, quote, unquote
from urllib.request import Request, build_opener, HTTPCookieProcessor
from urllib.error import URLError, HTTPError
from http.client import IncompleteRead
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple, Dict

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
    CACHE_FILE,
    CACHE_TTL,
    SCRIPT_DIR,
    HEADERS,
    cmd_search,
    cmd_techpowerup,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Per-domain rate limit delays (seconds)
DOMAIN_DELAYS = {
    "ebay.com": 3.0,
    "newegg.com": 2.5,
    "amazon.com": 2.5,
    "servermonkey.com": 2.0,
    "enterasource.com": 2.0,
    "serversdirect.com": 2.0,
    "cdw.com": 2.0,
    "connection.com": 2.0,
    "insight.com": 2.0,
    "ipcstore.com": 2.0,
    "techpowerup.com": 1.0,
    "wikipedia.org": 1.0,
    "duckduckgo.com": 1.0,
    "bing.com": 1.0,
    "google.com": 1.5,
}
DEFAULT_DELAY = 1.5
MAX_CONTENT_SIZE = 2 * 1024 * 1024  # 2 MB - skip oversized pages

# Enterprise GPU reseller domains to filter search results
ENTERPRISE_RESELLERS = [
    "servermonkey.com",
    "enterasource.com",
    "serversdirect.com",
    "cdw.com",
    "connection.com",
    "insight.com",
    "ipcstore.com",
    "amazon.com",
    "harddrivesforsale.com",
    "unixsurplus.com",
]

# Ordered by specificity (longer/more specific patterns first)
ENTERPRISE_PRICE_RANGES = [
    ("gb200", 30000, 80000),
    ("b200", 20000, 60000),
    ("b100", 15000, 40000),
    ("h200", 10000, 50000),
    ("h100 sxm", 8000, 35000),
    ("h100 nvl", 10000, 40000),
    ("h100", 5000, 35000),
    ("h800", 5000, 25000),
    ("a100 80", 3000, 15000),
    ("a100 40", 1500, 8000),
    ("a100", 1500, 15000),
    ("a800", 2000, 12000),
    ("a40", 1500, 6000),
    ("a30", 1000, 5000),
    ("a10g", 1000, 5000),
    ("a16", 1500, 6000),
    ("l40s", 3000, 8000),
    ("l40", 2500, 7000),
    ("l4", 1000, 4000),
    ("tesla v100", 500, 5000),
    ("tesla p100", 200, 2000),
    ("tesla p40", 200, 1500),
    ("tesla m40", 100, 800),
    ("instinct mi300", 5000, 20000),
    ("instinct mi250", 3000, 15000),
    ("instinct mi210", 2000, 8000),
    ("instinct mi100", 1000, 5000),
    ("instinct mi60", 200, 1500),
    ("instinct mi50", 100, 800),
    ("gaudi", 2000, 15000),
    ("gh200", 15000, 60000),
]

PROFESSIONAL_PRICE_RANGES = [
    ("rtx 6000 ada", 4000, 8000),
    ("rtx 5000 ada", 2000, 5000),
    ("rtx 4500 ada", 1500, 3500),
    ("rtx 4000 ada", 800, 2000),
    ("rtx a6000", 2500, 6000),
    ("rtx a5000", 1000, 3000),
    ("quadro rtx 8000", 3000, 8000),
    ("quadro rtx 6000", 2000, 6000),
    ("quadro rtx 5000", 1000, 3500),
    ("quadro rtx 4000", 600, 2000),
    ("quadro gv100", 1000, 4000),
    ("radeon pro w7900", 3000, 6000),
    ("radeon pro w7800", 1500, 4000),
    ("radeon pro w6800", 800, 2500),
    ("radeon pro w6600", 400, 1200),
    ("radeon pro vega ii", 300, 2000),
]

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
# Per-domain rate limiter
# ---------------------------------------------------------------------------

_domain_last_request: Dict[str, float] = {}


def _extract_root_domain(url: str) -> str:
    """Extract root domain from URL (e.g. 'ebay.com' from 'www.ebay.com')."""
    netloc = urlparse(url).netloc.lower().split(":")[0]
    parts = netloc.split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "ac"):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else netloc


def _get_domain_delay(url: str) -> float:
    domain = urlparse(url).netloc.lower()
    for domain_key, delay in DOMAIN_DELAYS.items():
        if domain_key in domain:
            return delay
    return DEFAULT_DELAY


def _domain_rate_limit(url: str):
    domain = _extract_root_domain(url)
    delay = _get_domain_delay(url)
    now = time.time()
    last = _domain_last_request.get(domain, 0.0)
    elapsed = now - last
    if elapsed < delay:
        wait = delay - elapsed
        print(f"  [rate-limit] {domain}: waiting {wait:.1f}s", file=sys.stderr)
        time.sleep(wait)
    _domain_last_request[domain] = time.time()


# ---------------------------------------------------------------------------
# Domain-aware fetch
# ---------------------------------------------------------------------------

def _fetch(url: str, timeout: int = 20, use_cache: bool = True) -> Optional[str]:
    """Fetch a URL with per-domain rate limiting.

    All diagnostics go to stderr. Returns decoded text or None.
    Uses separate cache prefix ("v3") from web_fetch.py's fetch_url()
    to avoid cross-contamination (double entity decoding, truncated pages).
    Respects 429 (Too Many Requests) by logging and returning None.
    Truncates pages exceeding MAX_CONTENT_SIZE (not cached when truncated).
    """
    cache = _load_cache()
    key = _cache_key(url, prefix="v3")

    if use_cache:
        cached = _get_cached(key, cache)
        if cached is not None:
            return cached

    _domain_rate_limit(url)

    try:
        req = Request(url, headers=HEADERS)
        opener = build_opener(HTTPCookieProcessor())
        resp = opener.open(req, timeout=timeout)

        # Check content length before downloading
        content_length = resp.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > MAX_CONTENT_SIZE * 2:
                    print(f"[fetch-skip] {url}: too large ({int(content_length)//1024}KB)", file=sys.stderr)
                    return None
            except ValueError:
                pass

        charset = "utf-8"
        ct = resp.headers.get("Content-Type", "")
        m = re.search(r"charset=([\w-]+)", ct)
        if m:
            charset = m.group(1)

        raw_bytes = resp.read(MAX_CONTENT_SIZE)
        is_truncated = len(raw_bytes) >= MAX_CONTENT_SIZE
        if is_truncated:
            print(f"[fetch-warn] {url}: truncated at {MAX_CONTENT_SIZE//1024}KB", file=sys.stderr)

        try:
            text = raw_bytes.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            text = raw_bytes.decode("utf-8", errors="replace")

        text = html_module.unescape(text)

        # Only cache complete (non-truncated) pages
        if use_cache and not is_truncated:
            _set_cached(key, cache, text)

        return text

    except HTTPError as e:
        if e.code == 429:
            retry_after = e.headers.get("Retry-After", "60")
            print(f"[rate-limited] {url}: server asked to wait {retry_after}s", file=sys.stderr)
        else:
            print(f"[HTTP {e.code}] {url}: {e.reason}", file=sys.stderr)
        return None
    except (URLError, IncompleteRead, TimeoutError, OSError) as e:
        print(f"[fetch-error] {url}: {e}", file=sys.stderr)
        return None


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
    title_lower = title.lower()
    gpu_lower = gpu_name.lower()

    for kw in NON_GPU_KEYWORDS:
        if kw in title_lower:
            return False, 0.1

    is_parts = any(p in title_lower for p in [
        "for parts", "not working", "as-is", "as is",
        "defective", "untested", "for repair",
    ])
    parts_penalty = 0.3 if is_parts else 0.0

    skip_words = {"nvidia", "amd", "radeon", "geforce", "the", "a", "an"}
    gpu_words = [w for w in gpu_lower.split() if w not in skip_words and len(w) > 1]

    if not gpu_words:
        return False, 0.0

    matches = sum(1 for w in gpu_words if w in title_lower)
    word_ratio = matches / len(gpu_words)

    has_positive = any(kw in title_lower for kw in GPU_POSITIVE_KEYWORDS)

    gpu_numbers = re.findall(r'\b(\d{2,}[a-z]?)\b', gpu_lower)
    number_match = any(n in title_lower for n in gpu_numbers) if gpu_numbers else False

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
    listings = []

    cards = re.findall(
        r'<div[^>]*class="[^"]*s-card[^"]*"[^>]*>(.*?)(?=<div[^>]*class="[^"]*s-card[^"]*"|$)',
        html_content, re.DOTALL,
    )

    for card_html in cards:
        listing = Listing(source="ebay")

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

        price_match = re.search(
            r's-card__price[^>]*>\$?([\d,]+\.?\d{0,2})<',
            card_html,
        )
        if price_match:
            try:
                listing.price = float(price_match.group(1).replace(",", ""))
            except ValueError:
                pass

        cond_match = re.search(
            r'class=s-card__subtitle><span[^>]*>(.*?)</span>',
            card_html,
        )
        if cond_match:
            listing.condition = re.sub(r'<[^>]+>', '', cond_match.group(1)).strip().rstrip(" ·")

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

        url_match = re.search(
            r'<a[^>]*class="[^"]*s-card__link[^"]*"[^>]*href="([^"]*)"',
            card_html,
        )
        if url_match:
            listing.url = url_match.group(1)

        if gpu_name:
            listing.is_gpu, listing.confidence = is_gpu_listing(listing.title, gpu_name)

        listings.append(listing)

    # Staleness warning: page loaded but parser found nothing
    if not listings and html_content and "ebay" in html_content[:5000].lower():
        print("[parser-warn] eBay page loaded but s-card parser found 0 listings — site layout may have changed", file=sys.stderr)

    return listings

def _parse_newegg_listings(html_content, gpu_name=""):
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

    if not listings and html_content and "newegg" in html_content[:5000].lower():
        print("[parser-warn] Newegg page loaded but item-cell parser found 0 listings — site layout may have changed", file=sys.stderr)

    return listings
# ---------------------------------------------------------------------------

def _classify_gpu(gpu_name: str) -> str:
    n = gpu_name.lower()

    dc_patterns = [
        r'\bh100\b', r'\bh200\b', r'\bb100\b', r'\bb200\b', r'\bgb200\b',
        r'\ba100\b', r'\ba800\b', r'\bh800\b',
        r'\bgh200\b',
        r'\btesla\b',
        r'instinct mi',
        r'\bsxm\d?\b', r'\bnvl\b',
        r'\bdgx\b',
        r'\bgaudi\b',
        r'data center gpu',
        r'\ba30\b', r'\ba10g\b', r'\ba16\b',
        r'\bl4\b(?!0)',    # L4 but not L40
        r'\bl40s?\b',      # L40, L40S
    ]
    for pattern in dc_patterns:
        if re.search(pattern, n):
            return "datacenter"

    pro_patterns = [
        r'\bquadro\b',
        r'\brtx a\d{4}\b',
        r'\brtx \d{4} ada\b',
        r'\bradeon pro\b',
        r'\bfirepro\b',
    ]
    for pattern in pro_patterns:
        if re.search(pattern, n):
            return "professional"

    return "consumer"


# ---------------------------------------------------------------------------
# Price range detection (v3 with enterprise support)
# ---------------------------------------------------------------------------

def _get_price_range_v3(gpu_name: str) -> Tuple[int, int]:
    n = gpu_name.lower()

    for pattern, lo, hi in ENTERPRISE_PRICE_RANGES:
        # Single-word patterns need word boundaries to avoid substring matches
        # e.g., "l4" must not match "l40"
        if ' ' not in pattern:
            regex = r'\b' + re.escape(pattern) + r'\b'
        else:
            regex = r'\b' + re.escape(pattern)
        if re.search(regex, n):
            return lo, hi

    for pattern, lo, hi in PROFESSIONAL_PRICE_RANGES:
        if ' ' not in pattern:
            regex = r'\b' + re.escape(pattern) + r'\b'
        else:
            regex = r'\b' + re.escape(pattern)
        if re.search(regex, n):
            return lo, hi

    return _get_price_range(gpu_name)


def _extract_prices_v3(text: str, min_price: int = 10, max_price: int = 60000) -> List[float]:
    """Extract dollar amounts from text with tiered confidence.

    Tier 1: $-prefixed prices (always reliable)
    Tier 2: Prices adjacent to price keywords (usually reliable)
    Tier 3: Standalone numbers (noisy for cheap cards, only used when min >= 1000)
    """
    prices = set()

    # Tier 1: $-prefixed (highest confidence)
    for m in re.finditer(r"\$\s*([\d,]+\.?\d{0,2})", text):
        try:
            v = float(m.group(1).replace(",", ""))
            if min_price <= v <= max_price:
                prices.add(round(v, 2))
        except ValueError:
            pass

    # Tier 2: keyword-adjacent (medium confidence)
    # Note: "for", "now", "unit" excluded — too common in non-price contexts
    for m in re.finditer(
        r"(?:price|cost|buy|sale|deal|sold|listing|was|each)\s*[:\s]*([\d,]{3,5}\.?\d{0,2})\b",
        text, re.IGNORECASE
    ):
        try:
            v = float(m.group(1).replace(",", ""))
            if min_price <= v <= max_price:
                prices.add(round(v, 2))
        except ValueError:
            pass

    # Tier 3: standalone numbers (only for expensive ranges where spec numbers
    # like 250W, 384-bit fall below the minimum threshold)
    if min_price >= 1000:
        for m in re.finditer(r"\b([\d,]{3,5}(?:\.\d{1,2})?)\b", text):
            try:
                v = float(m.group(1).replace(",", ""))
                if min_price <= v <= max_price:
                    prices.add(round(v, 2))
            except ValueError:
                pass

    return sorted(prices)


# ---------------------------------------------------------------------------
# Enterprise GPU price fetcher
# ---------------------------------------------------------------------------

def _fetch_enterprise_prices(gpu_name: str) -> dict:
    min_p, max_p = _get_price_range_v3(gpu_name)

    results = {
        "gpu": gpu_name,
        "classification": _classify_gpu(gpu_name),
        "min_expected": min_p,
        "max_expected": max_p,
        "prices": [],
        "sources": [],
        "best_price": None,
        "summary": "",
    }

    # Phase 1: Search engine -> enterprise reseller pages
    queries = [
        f'{gpu_name} price buy used',
        f'{gpu_name} refurbished server GPU',
        f'{gpu_name} enterprise GPU price',
    ]

    for query in queries:
        if results["prices"]:
            break
        print(f"  [enterprise] searching: {query}", file=sys.stderr)
        search_results = search(query, num_results=10)
        for title, url in search_results[:6]:
            domain = urlparse(url).netloc.lower()
            is_enterprise = any(d in domain for d in ENTERPRISE_RESELLERS)
            if not is_enterprise:
                continue

            print(f"  [enterprise] fetching: {domain}", file=sys.stderr)
            content = _fetch(url)
            if not content:
                continue

            text = html_to_text(content)
            prices = _extract_prices_v3(text, min_p, max_p)
            if prices:
                results["prices"].extend(prices)
                results["sources"].append({
                    "url": url,
                    "title": title,
                    "domain": domain,
                    "prices_found": prices[:8],
                })

    # Phase 2: eBay via search engine intermediary
    ebay_queries = [
        f'site:ebay.com {gpu_name} -fan -backplate -cable',
        f'{gpu_name} ebay server GPU price',
    ]

    for query in ebay_queries:
        if results["prices"]:
            break
        print(f"  [ebay] searching: {query}", file=sys.stderr)
        search_results = search(query, num_results=8)
        for title, url in search_results[:5]:
            if "ebay.com" not in url:
                continue
            if "/sch/" in url:
                continue

            print(f"  [ebay] fetching listing: {url[:80]}", file=sys.stderr)
            content = _fetch(url)
            if not content:
                continue

            text = html_to_text(content)
            prices = _extract_prices_v3(text, min_p, max_p)
            if prices:
                results["prices"].extend(prices)
                results["sources"].append({
                    "url": url,
                    "title": title,
                    "domain": "ebay.com",
                    "prices_found": prices[:8],
                })

    # Phase 2b: Broader eBay search (find shop/store pages or aggregates)
    if not results["prices"]:
        for query in [f'{gpu_name} ebay price buy', f'{gpu_name} server GPU for sale']:
            print(f"  [ebay-broad] searching: {query}", file=sys.stderr)
            search_results = search(query, num_results=5)
            for title, url in search_results[:3]:
                if "/sch/" in url:
                    continue
                content = _fetch(url)
                if not content:
                    continue
                text = html_to_text(content)
                prices = _extract_prices_v3(text, min_p, max_p)
                if prices:
                    results["prices"].extend(prices)
                    results["sources"].append({
                        "url": url,
                        "title": title,
                        "domain": urlparse(url).netloc.lower(),
                        "prices_found": prices[:8],
                    })
                    break
            if results["prices"]:
                break

    # Phase 3: Fallback to non-reseller pages (blogs, reviews, aggregators)
    if not results["prices"]:
        for query in [f'{gpu_name} price']:
            print(f"  [fallback] searching: {query}", file=sys.stderr)
            search_results = search(query, num_results=5)
            for title, url in search_results[:3]:
                domain = urlparse(url).netloc.lower()
                if any(d in domain for d in ENTERPRISE_RESELLERS):
                    continue  # Already tried in Phase 1

                content = _fetch(url)
                if not content:
                    continue

                text = html_to_text(content)
                prices = _extract_prices_v3(text, min_p, max_p)
                if prices:
                    results["prices"].extend(prices)
                    results["sources"].append({
                        "url": url,
                        "title": title,
                        "domain": domain,
                        "prices_found": prices[:8],
                    })
                    break
            if results["prices"]:
                break

    # Deduplicate and compute best price
    results["prices"] = sorted(set(results["prices"]))

    if results["prices"]:
        prices = results["prices"]
        idx = max(0, len(prices) // 4)
        results["best_price"] = prices[idx]
        results["summary"] = (
            f"Found {len(prices)} prices for {gpu_name}: "
            f"${min(prices):.0f}-${max(prices):.0f}. "
            f"Best estimate: ${results['best_price']:.0f}"
        )
    else:
        results["summary"] = f"No enterprise prices found for {gpu_name}"

    return results


# ---------------------------------------------------------------------------
# Consumer/professional GPU price fetcher
# ---------------------------------------------------------------------------

def _fetch_consumer_prices(gpu_name: str) -> dict:
    min_p, max_p = _get_price_range_v3(gpu_name)

    results = {
        "gpu": gpu_name,
        "classification": _classify_gpu(gpu_name),
        "new_prices": [],
        "used_prices": [],
        "sources": [],
        "best_new_price": None,
        "best_used_price": None,
        "summary": "",
    }

    useful_domains = [
        "newegg.com", "amazon.com", "bhphotovideo.com",
        "bestbuy.com", "microcenter.com", "walmart.com",
        "adorama.com", "pcpartpicker.com",
    ]

    # Phase 1: New prices from retailers
    queries = [
        f'{gpu_name} price buy',
        f'{gpu_name} newegg price',
    ]

    for query in queries:
        if results["new_prices"]:
            break
        print(f"  [retail] searching: {query}", file=sys.stderr)
        search_results = search(query)
        for title, url in search_results[:4]:
            domain = urlparse(url).netloc.lower()
            if not any(d in domain for d in useful_domains):
                continue

            print(f"  [retail] fetching: {domain}", file=sys.stderr)
            content = _fetch(url)
            if not content:
                continue

            text = html_to_text(content)
            prices = _extract_prices_v3(text, min_p, max_p)
            if prices:
                results["new_prices"].extend(prices)
                results["sources"].append({
                    "url": url,
                    "title": title,
                    "domain": domain,
                    "type": "new",
                    "prices_found": prices[:5],
                })
                break

    # Phase 2: eBay via search engine intermediary
    used_min = max(10, int(min_p * 0.3))
    ebay_queries = [
        f'site:ebay.com {gpu_name} sold -fan -backplate',
        f'{gpu_name} ebay sold price',
    ]

    for query in ebay_queries:
        if results["used_prices"]:
            break
        print(f"  [ebay-used] searching: {query}", file=sys.stderr)
        search_results = search(query, num_results=8)
        for title, url in search_results[:4]:
            if "ebay.com" not in url:
                continue
            if "/sch/" in url:
                continue

            print(f"  [ebay-used] fetching: {url[:80]}", file=sys.stderr)
            content = _fetch(url)
            if not content:
                continue

            text = html_to_text(content)
            prices = _extract_prices_v3(text, used_min, max_p)
            if prices:
                results["used_prices"].extend(prices)
                results["sources"].append({
                    "url": url,
                    "title": title,
                    "domain": "ebay.com",
                    "type": "used",
                    "prices_found": prices[:5],
                })
                break

    # Phase 3: Extract from search result snippets
    for query in [f'{gpu_name} price', f'{gpu_name} buy cost']:
        search_results = search(query)
        for title, url in search_results[:5]:
            combined = f"{title} {url}"
            prices = _extract_prices_v3(combined, min_p, max_p)
            results["new_prices"].extend(prices)

    # Deduplicate and compute best prices
    results["new_prices"] = sorted(set(results["new_prices"]))
    results["used_prices"] = sorted(set(results["used_prices"]))

    if results["new_prices"]:
        prices = results["new_prices"]
        idx = max(0, len(prices) // 4)
        results["best_new_price"] = prices[idx]

    if results["used_prices"]:
        prices = results["used_prices"]
        results["best_used_price"] = prices[len(prices) // 2]

    parts = []
    if results["best_new_price"]:
        parts.append(f"New: ~${results['best_new_price']:.0f}")
    if results["best_used_price"]:
        parts.append(f"Used: ~${results['best_used_price']:.0f}")
    if parts:
        results["summary"] = f"{gpu_name} ({results['classification']}): {'; '.join(parts)}"
    else:
        results["summary"] = f"No prices found for {gpu_name}"

    return results


# ---------------------------------------------------------------------------
# Listings command (v3)
# ---------------------------------------------------------------------------

def cmd_listings_v3(gpu_name: str, ebay_only: bool = False):
    min_p, max_p = _get_price_range_v3(gpu_name)
    results = {
        "gpu": gpu_name,
        "classification": _classify_gpu(gpu_name),
        "listings": [],
        "best_used": None,
        "best_used_gpu": None,
        "summary": "",
    }

    all_listings = []

    # eBay via search engine intermediary
    for query in [f'site:ebay.com {gpu_name} -fan -backplate -cable']:
        print(f"  [listings] searching eBay: {query}", file=sys.stderr)
        search_results = search(query, num_results=6)
        for title, url in search_results:
            if "ebay.com" not in url:
                continue
            if "/sch/" in url:
                continue  # eBay search pages return 403
            content = _fetch(url)
            if content:
                listings = _parse_ebay_listings(content, gpu_name)
                if listings:
                    all_listings.extend(listings)
                    break
        if all_listings:
            break

    # Newegg (if not ebay_only)
    if not ebay_only:
        for query in [f'site:newegg.com {gpu_name}']:
            print(f"  [listings] searching Newegg: {query}", file=sys.stderr)
            search_results = search(query, num_results=3)
            for title, url in search_results:
                if "newegg.com" not in url:
                    continue
                content = _fetch(url)
                if content:
                    listings = _parse_newegg_listings(content, gpu_name)
                    all_listings.extend(listings)
                    break

    # Classify and rank
    gpu_listings = [l for l in all_listings if l.is_gpu and l.price is not None]
    non_gpu_listings = [l for l in all_listings if not l.is_gpu and l.price is not None]

    gpu_listings.sort(key=lambda l: (-l.confidence, l.price or 99999))

    results["listings"] = [l.to_dict() for l in all_listings[:30]]
    results["gpu_listings"] = [l.to_dict() for l in gpu_listings[:20]]
    results["non_gpu_listings"] = [l.to_dict() for l in non_gpu_listings[:10]]
    results["total_listings"] = len(all_listings)
    results["gpu_listing_count"] = len(gpu_listings)

    if gpu_listings:
        prices = sorted([l.price for l in gpu_listings if l.price])
        if prices:
            idx = max(0, len(prices) // 4)
            results["best_used_gpu"] = prices[idx]
            results["best_used"] = prices[len(prices) // 2]

    if not results["best_used"] and all_listings:
        all_prices = sorted(set(l.price for l in all_listings if l.price is not None))
        if all_prices:
            results["best_used"] = all_prices[len(all_prices) // 2]

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
# Price command (v3)
# ---------------------------------------------------------------------------

def cmd_price_v3(gpu_name: str, force_datacenter: bool = False):
    gpu_class = _classify_gpu(gpu_name)

    if force_datacenter or gpu_class == "datacenter":
        results = _fetch_enterprise_prices(gpu_name)
    else:
        results = _fetch_consumer_prices(gpu_name)

    print(json.dumps(results, indent=2))


# ---------------------------------------------------------------------------
# Batch command
# ---------------------------------------------------------------------------

def cmd_batch(gpu_names: List[str], force_datacenter: bool = False):
    batch_results = []

    for i, gpu_name in enumerate(gpu_names):
        gpu_class = _classify_gpu(gpu_name)
        print(f"\n[{i+1}/{len(gpu_names)}] {gpu_name} ({gpu_class})", file=sys.stderr)

        try:
            if force_datacenter or gpu_class == "datacenter":
                result = _fetch_enterprise_prices(gpu_name)
            else:
                result = _fetch_consumer_prices(gpu_name)
        except Exception as e:
            print(f"[batch-error] {gpu_name}: {e}", file=sys.stderr)
            result = {
                "gpu": gpu_name,
                "classification": gpu_class,
                "error": str(e),
                "prices": [],
                "summary": f"Error: {e}",
            }

        result["index"] = i
        batch_results.append(result)

        if i < len(gpu_names) - 1:
            time.sleep(0.5)

    found = sum(1 for r in batch_results
                if r.get("best_price") or r.get("best_new_price") or r.get("best_used_price"))

    print(json.dumps({
        "batch": batch_results,
        "total": len(gpu_names),
        "found_prices": found,
        "missing_prices": len(gpu_names) - found,
    }, indent=2))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()

    # v3 commands
    if cmd == "price":
        if len(sys.argv) < 3:
            print("Usage: web_fetch_v3.py price <gpu_name>", file=sys.stderr)
            sys.exit(1)
        gpu = " ".join(sys.argv[2:])
        cmd_price_v3(gpu)

    elif cmd == "price-dc":
        if len(sys.argv) < 3:
            print("Usage: web_fetch_v3.py price-dc <gpu_name>", file=sys.stderr)
            sys.exit(1)
        gpu = " ".join(sys.argv[2:])
        cmd_price_v3(gpu, force_datacenter=True)

    elif cmd == "listings":
        if len(sys.argv) < 3:
            print("Usage: web_fetch_v3.py listings <gpu_name>", file=sys.stderr)
            sys.exit(1)
        gpu = " ".join(sys.argv[2:])
        cmd_listings_v3(gpu)

    elif cmd == "listings-ebay":
        if len(sys.argv) < 3:
            print("Usage: web_fetch_v3.py listings-ebay <gpu_name>", file=sys.stderr)
            sys.exit(1)
        gpu = " ".join(sys.argv[2:])
        cmd_listings_v3(gpu, ebay_only=True)

    elif cmd == "batch":
        if len(sys.argv) < 3:
            print("Usage: web_fetch_v3.py batch <gpu1,gpu2,...>", file=sys.stderr)
            print("   or: web_fetch_v3.py batch <single_gpu>", file=sys.stderr)
            sys.exit(1)
        args = " ".join(sys.argv[2:])
        if "," in args:
            gpus = [g.strip() for g in args.split(",") if g.strip()]
        else:
            gpus = [args.strip()]
        cmd_batch(gpus)

    # Delegated commands (from web_fetch.py)
    elif cmd == "fetch":
        if len(sys.argv) < 3:
            print("Usage: web_fetch_v3.py fetch <url>", file=sys.stderr)
            sys.exit(1)
        content = fetch_url(sys.argv[2])
        if content is None:
            sys.exit(1)
        print(content)

    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: web_fetch_v3.py search <query>", file=sys.stderr)
            sys.exit(1)
        cmd_search(" ".join(sys.argv[2:]))

    elif cmd in ("techpowerup", "tpu"):
        if len(sys.argv) < 3:
            print("Usage: web_fetch_v3.py techpowerup <gpu_name_or_url>", file=sys.stderr)
            sys.exit(1)
        cmd_techpowerup(" ".join(sys.argv[2:]))

    elif cmd in ("--help", "-h"):
        print(__doc__)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
