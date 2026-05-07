#!/usr/bin/env python3
"""Web fetching helper for GPU database project.

Subcommands:
  fetch <url>          - Fetch a URL and print its content
  search <query>       - Search the web and print results
  techpowerup <gpu>    - Fetch TechPowerUp GPU specs as structured data
  price <gpu>          - Search for GPU pricing from multiple sources

Uses only Python standard library. Caches results in web_cache.json.
"""

import sys
import os
import re
import json
import time
import html
import hashlib
import codecs
from urllib.request import urlopen, Request, build_opener, HTTPCookieProcessor
from urllib.parse import quote, urlencode, urljoin, urlparse, unquote
from urllib.error import URLError, HTTPError
from http.client import IncompleteRead
from html.parser import HTMLParser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(SCRIPT_DIR, "web_cache.json")
CACHE_TTL = 3600 * 4  # 4 hours default cache lifetime
REQUEST_DELAY = 2.0  # seconds between requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",  # avoid compressed responses we can't handle
    "DNT": "1",
    "Connection": "keep-alive",
}

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _load_cache():
    """Load cache from disk. Returns dict or empty dict."""
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(cache):
    """Persist cache to disk."""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=1)
    except OSError as e:
        print(f"Warning: could not save cache: {e}", file=sys.stderr)


def _cache_key(url_or_query, prefix=""):
    """Generate a deterministic cache key."""
    raw = f"{prefix}:{url_or_query}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _get_cached(key, cache, ttl=CACHE_TTL):
    """Return cached value if fresh enough, else None."""
    entry = cache.get(key)
    if entry is None:
        return None
    if time.time() - entry.get("ts", 0) > ttl:
        return None
    return entry.get("data")


def _set_cached(key, cache, data):
    """Store data in cache with current timestamp."""
    cache[key] = {"ts": time.time(), "data": data}
    _save_cache(cache)

# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------

_last_request_time = 0.0


def _rate_limit():
    """Enforce minimum delay between requests."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)
    _last_request_time = time.time()


def fetch_url(url, timeout=20, raw=False, use_cache=True):
    """Fetch a URL with proper headers. Returns decoded text or None on error.

    If raw=True, return the full HTML. Otherwise return a stripped text version.
    """
    cache = _load_cache()
    key = _cache_key(url, prefix="fetch")

    if use_cache:
        cached = _get_cached(key, cache)
        if cached is not None:
            return cached

    _rate_limit()

    try:
        req = Request(url, headers=HEADERS)
        opener = build_opener(HTTPCookieProcessor())
        resp = opener.open(req, timeout=timeout)

        # Handle encoding
        charset = "utf-8"
        ct = resp.headers.get("Content-Type", "")
        m = re.search(r"charset=([\w-]+)", ct)
        if m:
            charset = m.group(1)

        raw_bytes = resp.read()
        try:
            text = raw_bytes.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            text = raw_bytes.decode("utf-8", errors="replace")

        # Decode HTML entities
        text = html.unescape(text)

        if use_cache:
            _set_cached(key, cache, text)

        return text

    except HTTPError as e:
        print(f"HTTP error {e.code} fetching {url}: {e.reason}", file=sys.stderr)
        return None
    except (URLError, IncompleteRead, TimeoutError, OSError) as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return None

# ---------------------------------------------------------------------------
# HTML text extraction
# ---------------------------------------------------------------------------

class _TextExtractor(HTMLParser):
    """Strip tags and extract visible text from HTML."""

    _SKIP_TAGS = frozenset(["script", "style", "noscript", "head"])

    def __init__(self):
        super().__init__()
        self._pieces = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS and self._skip > 0:
            self._skip -= 1
        # Add newlines for block elements
        if tag in ("p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._pieces.append("\n")

    def handle_data(self, data):
        if self._skip == 0:
            self._pieces.append(data)

    def get_text(self):
        return " ".join("".join(self._pieces).split())


def html_to_text(html_str):
    """Convert HTML to readable plain text."""
    parser = _TextExtractor()
    try:
        parser.feed(html_str)
        return parser.get_text()
    except Exception:
        # Fallback: crude regex strip
        text = re.sub(r"<[^>]+>", " ", html_str)
        return " ".join(text.split())

# ---------------------------------------------------------------------------
# Search engine
# ---------------------------------------------------------------------------

def _extract_ddg_results(html_content):
    """Extract (title, url) pairs from DuckDuckGo HTML search results.

    DDG HTML uses: <a class="result__a" href="//duckduckgo.com/l/?uddg=<encoded_url>">
    The actual URL is URL-encoded in the uddg parameter.
    """
    results = []
    for m in re.finditer(
        r'<a[^>]+class="result__a"[^>]+href="([^"]*)"[^>]*>(.*?)</a>',
        html_content, re.DOTALL
    ):
        raw_href = m.group(1)
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()

        # Extract the uddg parameter which contains the actual URL
        uddg_match = re.search(r'uddg=([^&"]+)', raw_href)
        if uddg_match:
            actual_url = unquote(uddg_match.group(1))
            if actual_url.startswith("http") and title:
                results.append((title, actual_url))

    return results


def _extract_bing_results(html_content):
    """Extract (title, url) pairs from Bing search results.

    Bing uses <li class="b_algo"> with links going through bing.com/ck/a redirect.
    The display URL text is embedded in the title area. We extract it from
    the cite tag or the visible URL text near the result.
    """
    results = []

    for m in re.finditer(
        r'<li[^>]*class="b_algo"[^>]*>(.*?)</li>',
        html_content, re.DOTALL
    ):
        block = m.group(1)

        # Extract title
        title_match = re.search(r'<a[^>]*>(.*?)</a>', block, re.DOTALL)
        if not title_match:
            continue
        title_raw = title_match.group(1)
        # Bing mangles the title with URL text mixed in; clean it
        title = re.sub(r"<[^>]+>", "", title_raw).strip()
        # Remove any trailing URL-like text from title
        title = re.sub(r"https?://\S+$", "", title).strip()
        if not title:
            continue

        # Extract actual URL from the <cite> tag or the display URL
        url = None

        # Try <cite> tag first (display URL)
        cite_match = re.search(r'<cite[^>]*>(.*?)</cite>', block, re.DOTALL)
        if cite_match:
            cite_text = re.sub(r"<[^>]+>", "", cite_match.group(1)).strip()
            if cite_text and not cite_text.startswith("http"):
                cite_text = "https://" + cite_text
            # Convert display URL to a real URL (strip path arrows)
            cite_text = cite_text.replace(" › ", "/")
            url = cite_text

        # Also try to follow the redirect link and extract from href
        href_match = re.search(r'<a[^>]+href="(https?://www\.bing\.com/ck/a\?[^"]*)"', block)
        if href_match and not url:
            # We can't easily resolve Bing redirect without following it,
            # but we can try to get the URL from the block's text
            pass

        if url and title:
            results.append((title, url))

    return results


def _extract_google_results(html_content):
    """Extract results from Google search HTML.

    Google often requires JavaScript, but sometimes returns classic HTML.
    """
    results = []

    # Pattern for classic Google: <a href="/url?q=<url>&...">
    for m in re.finditer(
        r'<a[^>]+href="/url\?q=([^&"]+)[^"]*"[^>]*>(.*?)</a>',
        html_content, re.DOTALL
    ):
        url = unquote(m.group(1))
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if title and url.startswith("http") and "google.com" not in url:
            results.append((title, url))

    return results


def search(query, num_results=10):
    """Search the web and return list of (title, url) tuples.

    Tries multiple search engines in order until one works.
    DuckDuckGo HTML is tried first as it's most reliable without JS.
    """
    cache = _load_cache()
    key = _cache_key(query, prefix="search")
    cached = _get_cached(key, cache, ttl=1800)  # 30 min cache for searches
    if cached is not None:
        return cached[:num_results]

    q_encoded = quote(query)

    # Try engines in order of reliability without JavaScript
    engines = [
        ("duckduckgo", f"https://html.duckduckgo.com/html/?q={q_encoded}", _extract_ddg_results),
        ("bing", f"https://www.bing.com/search?q={q_encoded}&count={num_results + 5}", _extract_bing_results),
        ("google", f"https://www.google.com/search?q={q_encoded}&num={num_results + 5}&hl=en", _extract_google_results),
    ]

    for engine_name, url, extractor in engines:
        content = fetch_url(url, use_cache=False)
        if content is None:
            continue

        results = extractor(content)
        if results:
            _set_cached(key, cache, results)
            return results[:num_results]

    print("Warning: all search engines failed to return structured results", file=sys.stderr)
    return []


def cmd_search(query):
    """Run a search and print results to stdout."""
    results = search(query)
    if not results:
        print("No results found.")
        return

    for i, (title, url) in enumerate(results, 1):
        title_display = title if title else "(no title)"
        print(f"{i}. {title_display}")
        print(f"   {url}")

# ---------------------------------------------------------------------------
# TechPowerUp GPU specs parser
# ---------------------------------------------------------------------------

def _find_tpu_url(gpu_name):
    """Find the TechPowerUp GPU specs URL for a given GPU name."""
    # Try direct search on TechPowerUp first
    cache = _load_cache()
    key = _cache_key(gpu_name, prefix="tpu_url")
    cached = _get_cached(key, cache, ttl=86400 * 7)  # cache URL for 7 days
    if cached:
        return cached

    # Search TechPowerUp directly via their search
    search_q = f"site:techpowerup.com/gpu-specs {gpu_name}"
    results = search(search_q)
    for title, url in results:
        if "techpowerup.com/gpu-specs/" in url:
            _set_cached(key, cache, url)
            return url

    # Fallback: try to construct the URL
    slug = gpu_name.lower().replace(" ", "-").replace("(", "").replace(")", "")
    # This is a guess; TechPowerUp uses specific IDs
    guess_url = f"https://www.techpowerup.com/gpu-specs/{slug}.cxxxx"
    return None


def parse_tpu_specs(html_content):
    """Parse TechPowerUp GPU specs page into a dict of key-value pairs."""
    specs = {}

    # Extract the GPU name from the page title
    title_match = re.search(r"<h1[^>]*class=\"[^\"]*gpu-name[^\"]*\"[^>]*>(.*?)</h1>", html_content, re.DOTALL)
    if not title_match:
        title_match = re.search(r"<title>(.*?)</title>", html_content, re.DOTALL)
    if title_match:
        specs["name"] = re.sub(r"<[^>]+>", "", title_match.group(1)).strip()
        # Clean up title suffix
        specs["name"] = re.sub(r"\s*\|\s*TechPowerUp.*", "", specs["name"])
        specs["name"] = re.sub(r"\s*Specifications\s*$", "", specs["name"])

    # TechPowerUp specs are in a <dl> or table with label-value pairs
    # Pattern 1: <dt>Label</dt><dd>Value</dd>
    for m in re.finditer(
        r"<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>",
        html_content, re.DOTALL
    ):
        label = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        value = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if label and value:
            specs[label] = value

    # Pattern 2: table rows <tr><td>Label</td><td>Value</td></tr>
    for m in re.finditer(
        r"<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>",
        html_content, re.DOTALL
    ):
        label = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        value = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if label and value:
            specs[label] = value

    # Pattern 3: TechPowerUp specific - specs in <div class="gpudb-specs-large__..."> blocks
    for m in re.finditer(
        r'<div[^>]*class="[^"]*gpudb-specs-large__[^"]*label[^"]*"[^>]*>(.*?)</div>\s*<div[^>]*class="[^"]*gpudb-specs-large__[^"]*value[^"]*"[^>]*>(.*?)</div>',
        html_content, re.DOTALL
    ):
        label = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        value = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if label and value:
            specs[label] = value

    # Pattern 4: Generic key-value pattern in spans/divs
    for m in re.finditer(
        r'<span[^>]*class="[^"]*(?:label|key|prop)[^"]*"[^>]*>(.*?)</span>\s*<span[^>]*class="[^"]*(?:value|data)[^"]*"[^>]*>(.*?)</span>',
        html_content, re.DOTALL
    ):
        label = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        value = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if label and value:
            specs[label] = value

    # Try to normalize common fields
    normalized = {}
    for label, value in specs.items():
        ll = label.lower()

        if any(k in ll for k in ("vram", "memory size", "memory amount")):
            normalized["vram"] = value
        elif "memory type" in ll or "memory bus" in ll and "width" not in ll:
            if "type" in ll:
                normalized["memory_type"] = value
        elif "bus width" in ll or "memory bus" in ll:
            normalized["bus_width"] = value
        elif "gpu clock" in ll or "base clock" in ll or "core clock" in ll:
            if "boost" not in ll:
                normalized["base_clock"] = value
        elif "boost clock" in ll:
            normalized["boost_clock"] = value
        elif "cuda cores" in ll or "shading units" in ll or "stream processors" in ll:
            normalized["cores"] = value
        elif "fp32" in ll and ("tflops" in ll or "performance" in ll or "float" in ll):
            normalized["fp32_tflops"] = value
        elif "tdp" in ll or "tbp" in ll or "total board power" in ll or "power draw" in ll:
            normalized["tdp"] = value
        elif "die size" in ll or "die area" in ll:
            normalized["die_size"] = value
        elif "process" in ll and ("size" in ll or "node" in ll or "nm" in ll or "technology" in ll):
            normalized["process"] = value
        elif "transistor" in ll or "transistors" in ll or "mosfet" in ll:
            normalized["transistors"] = value
        elif "texture mapping" in ll or "tmus" in ll:
            normalized["tmus"] = value
        elif "render output" in ll or "rops" in ll:
            normalized["rops"] = value
        elif "pixel rate" in ll:
            normalized["pixel_rate"] = value
        elif "texture rate" in ll or "texel rate" in ll:
            normalized["texture_rate"] = value
        elif "memory bandwidth" in ll or "bandwidth" in ll:
            normalized["bandwidth"] = value
        elif "release date" in ll or "launched" in ll:
            normalized["release_date"] = value
        elif "architecture" in ll or "gpu" in ll and "variant" in ll:
            normalized["architecture"] = value
        elif "pcie" in ll and ("version" in ll or "bus" in ll or "interface" in ll):
            normalized["pcie_interface"] = value
        elif "recommended" in ll and "power" in ll:
            normalized["psu_recommendation"] = value
        elif "length" in ll or "dimensions" in ll:
            normalized["dimensions"] = value

    # Merge normalized into the raw specs
    if normalized:
        specs["_normalized"] = normalized

    return specs


def cmd_techpowerup(gpu_name):
    """Fetch and display TechPowerUp specs for a GPU."""
    # First, try if the user gave a direct URL
    if gpu_name.startswith("http"):
        url = gpu_name
    else:
        url = _find_tpu_url(gpu_name)
        if not url:
            print(f"Could not find TechPowerUp page for '{gpu_name}'.")
            print(f"Try searching manually at https://www.techpowerup.com/gpu-specs/")
            return

    content = fetch_url(url)
    if not content:
        print(f"Failed to fetch {url}")
        return

    specs = parse_tpu_specs(content)
    if not specs:
        print(f"Could not parse specs from {url}")
        print("The page may have changed its structure. Printing raw text:")
        print(html_to_text(content)[:3000])
        return

    # Print normalized fields first
    normalized = specs.pop("_normalized", {})
    if normalized:
        print("=== Normalized Specs ===")
        for key in sorted(normalized.keys()):
            print(f"  {key}: {normalized[key]}")
        print()

    # Print all raw specs
    print("=== All Specs ===")
    for key in sorted(specs.keys()):
        print(f"  {key}: {specs[key]}")

# ---------------------------------------------------------------------------
# Price lookup
# ---------------------------------------------------------------------------

def _extract_prices(text, min_price=10, max_price=15000):
    """Extract dollar amounts from text, filtering by range.

    Looks for patterns like $1,299, $399, 1499.99, etc.
    """
    prices = set()

    # Match $X,XXX or $XXX patterns
    for m in re.finditer(r"\$\s*([\d,]+\.?\d{0,2})", text):
        try:
            v = float(m.group(1).replace(",", ""))
            if min_price <= v <= max_price:
                prices.add(round(v, 2))
        except ValueError:
            pass

    # Match "X,XXX.XX" near price keywords when $ is stripped (Google does this)
    for m in re.finditer(
        r"(?:price|cost|buy|sale|deal|sold|listing|now|was|for)\s*[:\s]*([\d,]{3,5}\.?\d{0,2})\b",
        text, re.IGNORECASE
    ):
        try:
            v = float(m.group(1).replace(",", ""))
            if min_price <= v <= max_price:
                prices.add(round(v, 2))
        except ValueError:
            pass

    # Standalone 3-5 digit numbers (potential prices without $ or context)
    for m in re.finditer(r"\b([\d,]{3,5}(?:\.\d{1,2})?)\b", text):
        try:
            v = float(m.group(1).replace(",", ""))
            if min_price <= v <= max_price:
                prices.add(round(v, 2))
        except ValueError:
            pass

    return sorted(prices)


def _get_price_range(gpu_name):
    """Estimate expected price range based on GPU name."""
    n = gpu_name.lower()

    # Newer and high-end cards first
    ranges = [
        # NVIDIA RTX 50 series
        ("rtx 5090", 1500, 5000),
        ("rtx 5080", 800, 2000),
        ("rtx 5070 ti", 600, 1200),
        ("rtx 5070", 400, 900),
        ("rtx 5060 ti", 300, 600),
        ("rtx 5060", 250, 500),
        # NVIDIA RTX 40 series
        ("rtx 4090", 1500, 3500),
        ("rtx 4080", 800, 1600),
        ("rtx 4070 ti", 600, 1000),
        ("rtx 4070", 400, 700),
        ("rtx 4060 ti", 250, 550),
        ("rtx 4060", 200, 400),
        # NVIDIA RTX 30 series
        ("rtx 3090", 500, 1500),
        ("rtx 3080", 400, 900),
        ("rtx 3070", 300, 600),
        ("rtx 3060 ti", 200, 450),
        ("rtx 3060", 200, 450),
        ("rtx 3050", 150, 300),
        # NVIDIA RTX 20 series
        ("rtx 2080 ti", 400, 900),
        ("rtx 2080", 300, 700),
        ("rtx 2070", 200, 600),
        ("rtx 2060", 200, 400),
        # NVIDIA GTX 16 series
        ("gtx 1660", 100, 300),
        ("gtx 1650", 80, 200),
        # NVIDIA GTX 10 series
        ("gtx 1080 ti", 200, 500),
        ("gtx 1080", 100, 400),
        ("gtx 1070 ti", 100, 350),
        ("gtx 1070", 80, 300),
        ("gtx 1060", 60, 200),
        ("gtx 1050 ti", 50, 150),
        ("gtx 1050", 40, 150),
        # NVIDIA GTX 900 series
        ("gtx 980 ti", 80, 300),
        ("gtx 980", 50, 200),
        ("gtx 970", 40, 150),
        ("gtx 960", 30, 100),
        ("gtx 950", 25, 80),
        # NVIDIA older
        ("gtx 780", 30, 150),
        ("gtx 770", 25, 100),
        ("gtx 760", 20, 80),
        ("gtx 750 ti", 20, 80),
        ("gtx 680", 20, 80),
        ("gtx 580", 20, 80),
        ("titan", 200, 5000),
        # AMD RX 9000 series
        ("rx 9070 xt", 400, 800),
        ("rx 9070", 400, 700),
        ("rx 9060", 250, 500),
        # AMD RX 7000 series
        ("rx 7900 xtx", 600, 1400),
        ("rx 7900 xt", 500, 1200),
        ("rx 7900 gre", 400, 900),
        ("rx 7800 xt", 350, 600),
        ("rx 7800", 350, 600),
        ("rx 7700 xt", 300, 500),
        ("rx 7700", 300, 500),
        ("rx 7600 xt", 200, 400),
        ("rx 7600", 200, 400),
        ("rx 7500", 150, 300),
        # AMD RX 6000 series
        ("rx 6950 xt", 400, 800),
        ("rx 6900 xt", 350, 700),
        ("rx 6900", 350, 700),
        ("rx 6800 xt", 300, 600),
        ("rx 6800", 300, 600),
        ("rx 6750 xt", 250, 500),
        ("rx 6700 xt", 200, 450),
        ("rx 6700", 200, 450),
        ("rx 6650 xt", 150, 350),
        ("rx 6600 xt", 150, 350),
        ("rx 6600", 150, 300),
        ("rx 6500 xt", 80, 200),
        ("rx 6400", 60, 150),
        # AMD RX 5000 series
        ("rx 5700 xt", 200, 500),
        ("rx 5700", 150, 400),
        ("rx 5600 xt", 120, 300),
        ("rx 5600", 100, 250),
        ("rx 5500 xt", 80, 200),
        # AMD RX 500/400 series
        ("rx 590", 80, 200),
        ("rx 580", 60, 180),
        ("rx 570", 50, 150),
        ("rx 560", 30, 100),
        ("rx 550", 20, 80),
        ("rx 480", 50, 150),
        ("rx 470", 40, 120),
        ("rx 460", 30, 80),
        # AMD older
        ("r9 fury", 50, 300),
        ("r9 390", 50, 250),
        ("r9 290", 40, 200),
        ("r9 280", 30, 150),
        ("r9 270", 25, 100),
        ("vega 64", 100, 400),
        ("vega 56", 80, 350),
        ("vega", 80, 400),
        ("radeon vii", 100, 400),
        ("radeon pro", 200, 10000),
        ("hd 7970", 20, 80),
    ]

    for pattern, lo, hi in ranges:
        if pattern in n:
            return lo, hi

    return 10, 5000


def cmd_price(gpu_name):
    """Search for GPU prices from multiple sources."""
    min_p, max_p = _get_price_range(gpu_name)
    results = {"gpu": gpu_name, "new_prices": [], "used_prices": [], "sources": []}

    # --- Source 1: Google search for new price ---
    queries = [
        f'{gpu_name} price buy',
        f'{gpu_name} newegg price',
    ]

    for query in queries:
        search_results = search(query)
        for title, url in search_results[:3]:
            # Only fetch from useful domains
            useful_domains = ["newegg.com", "amazon.com", "bhphotovideo.com",
                              "bestbuy.com", "microcenter.com", "walmart.com",
                              "adorama.com", "pcpartpicker.com"]
            domain = urlparse(url).netloc.lower()
            if not any(d in domain for d in useful_domains):
                continue

            content = fetch_url(url)
            if content:
                text = html_to_text(content)
                prices = _extract_prices(text, min_p, max_p)
                if prices:
                    results["new_prices"].extend(prices)
                    results["sources"].append({
                        "url": url,
                        "title": title,
                        "prices_found": prices[:5]
                    })
                break  # Got prices from this query, move to next
        if results["new_prices"]:
            break

    # --- Source 2: Google search for used/eBay price ---
    used_min = max(10, int(min_p * 0.3))
    used_queries = [
        f'{gpu_name} ebay sold price',
        f'{gpu_name} used price',
    ]

    for query in used_queries:
        search_results = search(query)
        for title, url in search_results[:3]:
            domain = urlparse(url).netloc.lower()
            if "ebay" not in domain and "swappa" not in domain:
                continue

            content = fetch_url(url)
            if content:
                text = html_to_text(content)
                prices = _extract_prices(text, used_min, max_p)
                if prices:
                    results["used_prices"].extend(prices)
                    results["sources"].append({
                        "url": url,
                        "title": title,
                        "prices_found": prices[:5]
                    })
                break
        if results["used_prices"]:
            break

    # --- Source 3: Extract prices directly from search results snippets ---
    for query in [f'{gpu_name} price', f'{gpu_name} buy cost']:
        search_results = search(query)
        for title, url in search_results[:5]:
            combined_text = f"{title} {url}"
            prices = _extract_prices(combined_text, min_p, max_p)
            results["new_prices"].extend(prices)

    # Deduplicate and sort
    results["new_prices"] = sorted(set(results["new_prices"]))
    results["used_prices"] = sorted(set(results["used_prices"]))

    # Pick best estimates
    if results["new_prices"]:
        prices = results["new_prices"]
        # Lower quartile as the "typical new price"
        idx = max(0, len(prices) // 4)
        results["best_new_price"] = prices[idx]

    if results["used_prices"]:
        prices = results["used_prices"]
        mid = len(prices) // 2
        results["best_used_price"] = prices[mid]

    # Output
    print(json.dumps(results, indent=2))

# ---------------------------------------------------------------------------
# Main CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "fetch":
        if len(sys.argv) < 3:
            print("Usage: web_fetch.py fetch <url>", file=sys.stderr)
            sys.exit(1)
        url = sys.argv[2]
        content = fetch_url(url)
        if content is None:
            sys.exit(1)
        print(content)

    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: web_fetch.py search <query>", file=sys.stderr)
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        cmd_search(query)

    elif cmd == "techpowerup" or cmd == "tpu":
        if len(sys.argv) < 3:
            print("Usage: web_fetch.py techpowerup <gpu_name_or_url>", file=sys.stderr)
            sys.exit(1)
        gpu = " ".join(sys.argv[2:])
        cmd_techpowerup(gpu)

    elif cmd == "price":
        if len(sys.argv) < 3:
            print("Usage: web_fetch.py price <gpu_name>", file=sys.stderr)
            sys.exit(1)
        gpu = " ".join(sys.argv[2:])
        cmd_price(gpu)

    elif cmd == "--help" or cmd == "-h":
        print(__doc__)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
