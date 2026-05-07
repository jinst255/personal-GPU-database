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

    # Search for the GPU on TechPowerUp
    search_q = f"{gpu_name} techpowerup gpu specs"
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


def _parse_tpu_og_description(html_content):
    """Parse specs from TechPowerUp's og:description meta tag.

    Format: "NVIDIA AD102, 2520 MHz, 16384 Cores, 512 TMUs, 176 ROPs,
             24576 MB GDDR6X, 1313 MHz, 384 bit"
    Also extracts name from og:title.
    """
    specs = {}

    # Extract title
    title_match = re.search(r'property="og:title"[^>]*content="([^"]*)"', html_content)
    if title_match:
        specs["name"] = title_match.group(1).replace(" Specs", "")

    # Extract og:description
    desc_match = re.search(r'property="og:description"[^>]*content="([^"]*)"', html_content)
    if not desc_match:
        return specs

    desc = desc_match.group(1)
    parts = [p.strip() for p in desc.split(",")]

    if len(parts) < 3:
        return specs

    specs["og_description_raw"] = desc

    # First part is GPU chip name (e.g., "NVIDIA AD102")
    specs["gpu_chip"] = parts[0].strip()

    # Parse remaining parts
    for part in parts[1:]:
        part = part.strip()
        # Clock speed: "2520 MHz" or "1313 MHz"
        if "MHz" in part:
            mhz_val = re.search(r'([\d.]+)\s*MHz', part)
            if mhz_val:
                mhz = float(mhz_val.group(1))
                # First MHz is typically GPU clock, second is memory clock
                if "gpu_clock_mhz" not in specs:
                    specs["gpu_clock_mhz"] = str(int(mhz))
                else:
                    specs["memory_clock_mhz"] = str(int(mhz))
        # Cores: "16384 Cores"
        elif "Cores" in part or "cores" in part:
            specs["cores"] = re.sub(r"[^\d]", "", part.split()[0])
        # TMUs: "512 TMUs"
        elif "TMU" in part:
            specs["tmus"] = re.sub(r"[^\d]", "", part.split()[0])
        # ROPs: "176 ROPs"
        elif "ROP" in part:
            specs["rops"] = re.sub(r"[^\d]", "", part.split()[0])
        # Memory: "24576 MB GDDR6X" or "24576 MB GDDR6"
        elif "MB" in part or "GB" in part:
            mem_match = re.search(r'([\d]+)\s*(MB|GB)\s*(\S+)', part)
            if mem_match:
                mem_size = int(mem_match.group(1))
                mem_unit = mem_match.group(2)
                mem_type = mem_match.group(3)
                if mem_unit == "MB":
                    specs["vram_mb"] = str(mem_size)
                    specs["vram_gb"] = str(mem_size / 1024)
                else:
                    specs["vram_gb"] = str(mem_size)
                    specs["vram_mb"] = str(mem_size * 1024)
                specs["memory_type"] = mem_type
        # Bus width: "384 bit"
        elif "bit" in part:
            specs["bus_width"] = re.sub(r"[^\d]", "", part.split()[0]) + " bit"

    return specs


def _parse_wikipedia_gpu_table(html_content, gpu_name):
    """Parse GPU specs from Wikipedia tables.

    Strategy: Wikipedia GPU tables have complex multi-row headers and
    rowspan/colspan merging. Instead of trying to resolve column indices,
    we find the matching row and extract values by format recognition:
    - TDP always ends with "W"
    - Clock speeds have "base(boost)" format
    - MSRP is a dollar-like number in position 2-3
    - The last cell is often TDP
    - We also scan preceding rows for transistors/die size (rowspan shared values)
    """
    specs = {}
    gpu_lower = gpu_name.lower().replace("\xa0", " ").replace("  ", " ")

    # Extract distinctive search terms
    search_terms = []
    skip_words = {"geforce", "radeon", "nvidia", "amd", "graphics", "card",
                  "gpu", "series", "desktop", "laptop"}
    for word in gpu_lower.split():
        if len(word) > 2 and word not in skip_words:
            search_terms.append(word)

    if not search_terms:
        return specs

    # Build a "must not contain" list to avoid matching variant models
    # e.g., "RTX 4090" should not match "RTX 4090 D" or "RTX 4090 Ti"
    gpu_model_id = gpu_lower.replace("geforce ", "").replace("radeon ", "").strip()

    # Find wikitable tables
    tables = re.findall(
        r'<table[^>]*class="[^"]*wikitable[^"]*"[^>]*>(.*?)</table>',
        html_content, re.DOTALL
    )

    for table_html in tables:
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL)
        if not rows:
            continue

        all_parsed_rows = []
        for row in rows:
            cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row, re.DOTALL)
            cells_text = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            all_parsed_rows.append(cells_text)

        # Find the best matching row
        best_idx = None
        best_score = -1
        for idx, cells_text in enumerate(all_parsed_rows):
            if not cells_text:
                continue
            row_text = " ".join(cells_text).lower().replace("\xa0", " ")

            if not all(term in row_text for term in search_terms):
                continue
            # Skip laptop rows when searching for desktop
            if "laptop" in row_text and "laptop" not in gpu_lower:
                continue

            # Check for exact model match in the first cell
            first_cell = cells_text[0].lower().replace("\xa0", " ")
            # Clean up reference markers like [81][82]
            first_cell_clean = re.sub(r'\[.*?\]', '', first_cell).strip()

            # Score: prefer exact matches over partial matches
            score = 0
            # Normalize: remove common prefix words for comparison
            model_in_cell = gpu_model_id.replace(" ", "")
            cell_cleaned = first_cell_clean.replace(" ", "")
            # Remove "geforce" and "radeon" prefix for comparison
            for prefix in ("geforce", "radeon"):
                if cell_cleaned.startswith(prefix):
                    cell_cleaned = cell_cleaned[len(prefix):]
                if model_in_cell.startswith(prefix):
                    model_in_cell = model_in_cell[len(prefix):]

            if model_in_cell == cell_cleaned:
                score = 100  # Exact match
            elif model_in_cell in cell_cleaned:
                # Partial match - check if there's an extra letter/suffix
                remainder = cell_cleaned.replace(model_in_cell, "").strip()
                if not remainder:
                    score = 90
                elif remainder in ("ti", "super"):
                    # Only match Ti/Super variants if explicitly requested
                    if remainder in gpu_model_id:
                        score = 95
                    else:
                        score = 0
                else:
                    # Has additional suffix (D, Laptop, etc.) - lower score
                    score = 20
            else:
                score = 10

            if score > best_score:
                best_score = score
                best_idx = idx

        if best_idx is None:
            continue

        target_idx = best_idx

        if target_idx is None:
            continue

        cells_text = all_parsed_rows[target_idx]

        # --- Extract by format recognition ---

        # TDP: look for "X W" pattern (often in last cell)
        for val in reversed(cells_text):
            clean = re.sub(r'\[.*?\]', '', val).strip()
            tdp_match = re.match(r'^([\d,.]+(?:\s*[-–]\s*[\d,.]+)?)\s*W$', clean)
            if tdp_match:
                specs["tdp"] = tdp_match.group(1).replace(" ", "") + " W"
                break

        # Clock: "base(boost)" or "base-boost(max)" pattern
        for val in cells_text:
            clean = re.sub(r'\[.*?\]', '', val).strip()
            clock_match = re.match(r'^([\d.]+(?:\s*[-–]\s*[\d.]+)?)\s*\(([\d.]+)\)$', clean)
            if clock_match:
                specs["base_clock_mhz"] = clock_match.group(1).replace(" ", "")
                specs["boost_clock_mhz"] = clock_match.group(2)
                break

        # MSRP: check all cells for price pattern
        for i, val in enumerate(cells_text):
            clean = re.sub(r'\[.*?\]', '', val).strip()
            # Check for "$XXX USD" or "$XXX" pattern anywhere in the cell
            msrp_match = re.search(r'\$([\d,]+)\s*(?:USD)?', clean)
            if msrp_match:
                specs["msrp"] = msrp_match.group(1)
                break
        # If no $ price found, look for standalone price in position 2-4
        if 'msrp' not in specs:
            for i, val in enumerate(cells_text):
                if i < 2:
                    continue
                clean = re.sub(r'\[.*?\]', '', val).strip()
                msrp_match = re.match(r'^(?:[\$¥€])?([\d,]+)(?:\s*\([^)]*([\d,]+)\))?(?:\s*$)', clean)
                if msrp_match:
                    dollar_val = msrp_match.group(2) or msrp_match.group(1)
                    specs["msrp"] = dollar_val
                    break

        # For transistors and die size, scan nearby rows since these values
        # are often shared via rowspan from a related variant row.
        header_row_1 = all_parsed_rows[0] if all_parsed_rows else []

        # Find column indices for transistors and die size from header
        trans_col = None
        die_col = None
        for i, h in enumerate(header_row_1):
            hl = h.lower()
            if 'transistor' in hl:
                trans_col = i
            elif 'die size' in hl or 'die area' in hl:
                die_col = i

        # Check if target row has full columns (including trans/die)
        # The header row has all column definitions; data rows with rowspan
        # will have fewer cells than the total column count
        full_column_count = len(header_row_1)
        target_cell_count = len(cells_text)
        # If target has fewer cells than the header, it's missing columns due to rowspan
        has_full_columns = target_cell_count >= full_column_count

        if has_full_columns:
            # Extract directly from target row
            if trans_col is not None and trans_col < len(cells_text):
                val = re.sub(r'\[.*?\]', '', cells_text[trans_col]).strip()
                try:
                    v = float(val)
                    # Validate: transistors should be 0.1-200 billion
                    if 0.1 <= v <= 200:
                        specs['transistors_billions'] = val
                except ValueError:
                    pass
            if die_col is not None and die_col < len(cells_text):
                val = re.sub(r'\[.*?\]', '', cells_text[die_col]).strip()
                try:
                    v = float(val)
                    # Validate: die size should be 50-1000 mm2
                    if 50 <= v <= 1000:
                        specs['die_size_mm2'] = val
                except ValueError:
                    pass
        else:
            # Scan rows above for a row with more cells (shared via rowspan)
            for scan_idx in range(target_idx - 1, max(0, target_idx - 10), -1):
                scan_cells = all_parsed_rows[scan_idx]
                scan_text = " ".join(scan_cells).lower()
                # Only use rows from the same GPU family
                if not any(t in scan_text for t in search_terms[:1]):
                    continue
                if len(scan_cells) <= len(cells_text):
                    continue

                if trans_col is not None and trans_col < len(scan_cells) and 'transistors_billions' not in specs:
                    val = re.sub(r'\[.*?\]', '', scan_cells[trans_col]).strip()
                    try:
                        v = float(val)
                        if 0.1 <= v <= 200:
                            specs['transistors_billions'] = val
                    except ValueError:
                        pass
                if die_col is not None and die_col < len(scan_cells) and 'die_size_mm2' not in specs:
                    val = re.sub(r'\[.*?\]', '', scan_cells[die_col]).strip()
                    try:
                        v = float(val)
                        if 50 <= v <= 1000:
                            specs['die_size_mm2'] = val
                    except ValueError:
                        pass

                if 'transistors_billions' in specs and 'die_size_mm2' in specs:
                    break

        # Extract launch date from position 1 (usually column index 1)
        if len(cells_text) > 1:
            launch = re.sub(r'\[.*?\]', '', cells_text[1]).strip()
            # Handle "Dec 13, 2022$999 USD" pattern (date and price merged)
            date_match = re.match(r'([A-Z][a-z]+ \d{1,2},? \d{4})', launch)
            if date_match:
                specs['launch'] = date_match.group(1)
            elif re.search(r'\d{4}', launch):
                specs['launch'] = launch

        # Extract codename from position 3 (usually column index 3)
        for i, val in enumerate(cells_text):
            clean = re.sub(r'\[.*?\]', '', val).strip()
            if re.match(r'^[A-Z][A-Z]\d', clean):  # e.g., "AD102-300"
                specs['codename'] = clean
                break

        if specs:
            return specs

    return specs


def _get_wikipedia_url(gpu_name):
    """Guess the Wikipedia article URL for a GPU series."""
    n = gpu_name.lower()
    if "rtx 50" in n:
        return "https://en.wikipedia.org/wiki/GeForce_50_series"
    elif "rtx 40" in n:
        return "https://en.wikipedia.org/wiki/GeForce_40_series"
    elif "rtx 30" in n:
        return "https://en.wikipedia.org/wiki/GeForce_30_series"
    elif "rtx 20" in n:
        return "https://en.wikipedia.org/wiki/GeForce_20_series"
    elif "gtx 16" in n:
        return "https://en.wikipedia.org/wiki/GeForce_16_series"
    elif "gtx 10" in n:
        return "https://en.wikipedia.org/wiki/GeForce_10_series"
    elif "gtx 900" in n or "gtx 9" in n:
        return "https://en.wikipedia.org/wiki/GeForce_900_series"
    elif "gtx 700" in n or "gtx 7" in n:
        return "https://en.wikipedia.org/wiki/GeForce_700_series"
    elif "gtx 600" in n or "gtx 6" in n:
        return "https://en.wikipedia.org/wiki/GeForce_600_series"
    elif "gtx 500" in n or "gtx 5" in n:
        return "https://en.wikipedia.org/wiki/GeForce_500_series"
    elif "rx 9070" in n or "rx 9060" in n:
        return "https://en.wikipedia.org/wiki/Radeon_RX_9000_series"
    elif "rx 7000" in n or "rx 79" in n or "rx 78" in n or "rx 77" in n or "rx 76" in n or "rx 75" in n:
        return "https://en.wikipedia.org/wiki/Radeon_RX_7000_series"
    elif "rx 6000" in n or "rx 69" in n or "rx 68" in n or "rx 67" in n or "rx 66" in n or "rx 65" in n or "rx 64" in n:
        return "https://en.wikipedia.org/wiki/Radeon_RX_6000_series"
    elif "rx 5000" in n or "rx 57" in n or "rx 56" in n or "rx 55" in n:
        return "https://en.wikipedia.org/wiki/Radeon_RX_5000_series"
    elif "rx 500" in n or "rx 590" in n or "rx 580" in n or "rx 570" in n or "rx 560" in n or "rx 550" in n:
        return "https://en.wikipedia.org/wiki/Radeon_RX_500_series"
    elif "rx 400" in n or "rx 480" in n or "rx 470" in n or "rx 460" in n:
        return "https://en.wikipedia.org/wiki/Radeon_RX_400_series"
    elif "r9" in n or "r7" in n or "r5" in n:
        return "https://en.wikipedia.org/wiki/AMD_Radeon_RX_500_series"
    return None


def cmd_techpowerup(gpu_name):
    """Fetch and display TechPowerUp specs for a GPU.

    Since TechPowerUp renders specs via JavaScript, we extract what we can
    from the og:description meta tag, then supplement with Wikipedia data.
    """
    # First, try if the user gave a direct URL
    if gpu_name.startswith("http"):
        url = gpu_name
    else:
        url = _find_tpu_url(gpu_name)
        if not url:
            # Direct URL lookup failed, try TechPowerUp with the GPU name as slug
            slug = gpu_name.lower().replace(" ", "-")
            url = f"https://www.techpowerup.com/gpu-specs/{slug}.cXXXX"
            print(f"Could not find TechPowerUp page for '{gpu_name}'.", file=sys.stderr)
            print(f"Try searching manually at https://www.techpowerup.com/gpu-specs/", file=sys.stderr)
            # Still try Wikipedia below
            url = None

    specs = {}

    # Source 1: TechPowerUp og:description
    if url:
        content = fetch_url(url)
        if content:
            tpu_specs = _parse_tpu_og_description(content)
            specs.update(tpu_specs)

    # Source 2: Wikipedia for additional specs (die size, transistors, TDP, etc.)
    wiki_url = _get_wikipedia_url(gpu_name)
    if wiki_url:
        wiki_content = fetch_url(wiki_url)
        if wiki_content:
            wiki_specs = _parse_wikipedia_gpu_table(wiki_content, gpu_name)
            # Wikipedia supplements TPU data (adds die size, transistors, TDP, etc.)
            for key, val in wiki_specs.items():
                if key not in specs:
                    specs[key] = val

    if not specs:
        print(f"Could not find specs for '{gpu_name}' from any source.")
        return

    # Print organized output
    print("=== GPU Specs ===")
    priority_keys = [
        "name", "gpu_chip", "codename", "launch", "msrp",
        "cores", "sm_count", "tmus", "rops", "core_config",
        "gpu_clock_mhz", "memory_clock_mhz",
        "vram_gb", "vram_mb", "memory_type", "bus_width", "bandwidth",
        "transistors", "die_size", "l2_cache",
        "tdp",
    ]

    printed = set()
    for key in priority_keys:
        if key in specs:
            val = specs[key]
            # Clean up the value
            val = re.sub(r'\[.*?\]', '', val).strip()
            if val:
                print(f"  {key}: {val}")
                printed.add(key)

    # Print remaining keys
    for key in sorted(specs.keys()):
        if key not in printed and key != "og_description_raw":
            val = specs[key]
            val = re.sub(r'\[.*?\]', '', val).strip()
            if val:
                print(f"  {key}: {val}")

    # Also output as JSON for programmatic use
    output = {k: v for k, v in specs.items() if k != "og_description_raw"}
    print("\n=== JSON ===")
    print(json.dumps(output, indent=2))

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
