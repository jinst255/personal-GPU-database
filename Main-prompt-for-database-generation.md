
**TASK OVERVIEW**

You are a data researcher and hardware expert with access to web search and code execution on the user's computer. Your job is to compile the most comprehensive GPU and accelerator database ever assembled—covering every GPU-class product ever made, from integrated graphics to data centre superchips, from legacy cards to the latest generation. Format everything for immediate use in Python with pandas, letplot, and plotnine (ggplot2 port). This database will serve as a personal GPU buying guide, a data science reference dataset, and an AI training/inference hardware reference.

**Completeness is the top priority. Include every card you can find, regardless of age, VRAM amount, or relevance to modern workloads.**

---

**YOUR CAPABILITIES — HOW TO USE THEM**

You have two tools at your disposal and must use them correctly:

**Web Search:** Use this to look up pricing and availability for every card. Do not guess prices. For each card, you must make **at least 3 independent search attempts** across different sources before concluding a price is unavailable and writing `null`. Search attempts should vary (e.g. try the product name + "price", then the retailer name directly, then a broader search). Only mark a price as `null` after exhausting these attempts.

**Code Execution:** You must use code execution for **all mathematical operations** without exception. This includes:
- Calculating `cost_per_gb_vram_usd`
- Calculating `fp32_per_dollar`
- Any unit conversions
- Any derived or computed column

Do not perform arithmetic in your head. Write and run a Python snippet for every calculation, then paste the result into the CSV.

---

**PRIMARY DATA SOURCE**

Begin with TechPowerUp's GPU Specifications database (https://www.techpowerup.com/gpu-specs/). This is your gold standard—it covers thousands of GPUs including legacy cards. Supplement with:
- NVIDIA official product pages
- AMD official product pages
- Intel Arc product pages
- AnandTech GPU benchmarks archive
- WikiChip
- Notebookcheck (for mobile GPUs)
- ServeTheHome (for data centre accelerators)
- GPU-Z database
- Videocardz.com spec sheets

---

**OUTPUT FORMAT**

Produce a single flat **CSV file** with one row per GPU. Use clean, snake_case column headers. Every field must be present in every row—use `null` (not blank, not N/A, not "-") for any unknown or unavailable value. No nested data. No sub-tables. Everything in columns.

---

**EXACT COLUMN SCHEMA**

Use these exact column names in this exact order:

| Column | Description |
|---|---|
| `gpu_name` | Full official product name (e.g. "NVIDIA GeForce RTX 4090") |
| `manufacturer` | Chip designer: `NVIDIA`, `AMD`, `Intel`, `Apple`, `Qualcomm`, `Other` |
| `brand` | AIB or OEM brand if applicable; reference/founders = same as manufacturer |
| `category` | See Category Values below |
| `architecture` | Microarchitecture name (e.g. `Ada Lovelace`, `RDNA 3`, `Hopper`, `Fermi`) |
| `gpu_chip` | Die name (e.g. `GA102`, `AD102`, `GH100`, `Barts`) |
| `release_year` | 4-digit year of release |
| `release_date` | Full date if known: `YYYY-MM-DD`, else `null` |
| `discontinued` | Boolean: `true` if no longer manufactured, `false` if still in production, `null` if unknown |
| `process_node_nm` | Fab process in nanometers as a number |
| `transistors_billion` | Transistor count in billions as a float |
| `die_size_mm2` | Die size in mm² as a number |
| `vram_gb` | VRAM in gigabytes as a number. For unified memory (Apple), use total shared memory |
| `vram_type` | Memory type: `GDDR6`, `GDDR6X`, `HBM2e`, `HBM3`, `LPDDR5`, `GDDR5`, `GDDR3`, etc. |
| `vram_bus_width_bit` | Memory bus width in bits |
| `memory_bandwidth_gbps` | Memory bandwidth in GB/s as a float |
| `cuda_cores` | CUDA core count for NVIDIA; `null` for others |
| `stream_processors` | AMD stream processor count; `null` for others |
| `xe_cores` | Intel Xe core count; `null` for others |
| `tensor_cores` | Tensor core count (NVIDIA); `null` for others |
| `rt_cores` | Ray tracing core count; `null` if not applicable |
| `compute_units` | AMD compute unit count; `null` for others |
| `base_clock_mhz` | Base clock speed in MHz |
| `boost_clock_mhz` | Boost/turbo clock in MHz |
| `fp32_tflops` | FP32 single precision compute in TFLOPS |
| `fp16_tflops` | FP16 half precision compute in TFLOPS; `null` if not rated |
| `bf16_tflops` | BF16 compute in TFLOPS; `null` if not rated |
| `int8_tops` | INT8 inference performance in TOPS; `null` if not rated |
| `tdp_watts` | Thermal design power in watts |
| `recommended_psu_watts` | Recommended PSU wattage; `null` for server cards |
| `slot_width` | Physical form: `1-slot`, `2-slot`, `2.5-slot`, `3-slot`, `HHHL`, `FHFL`, `SXM`, `OAM`, `null` |
| `connector_type` | Power connector(s): `PCIe 8-pin`, `16-pin`, `SXM`, `None`, etc. |
| `pcie_generation` | PCIe generation as a number: `1`, `2`, `3`, `4`, `5` |
| `pcie_lanes` | Number of PCIe lanes |
| `nvlink_support` | Boolean: `true`/`false` |
| `display_outputs` | Output description (e.g. `3x DP 1.4, 1x HDMI 2.1`); `null` for compute-only |
| `max_displays` | Max simultaneous displays; `null` for compute-only |
| `directx_version` | DirectX version supported; `null` for compute-only |
| `opencl_version` | OpenCL version supported |
| `cuda_compute_capability` | NVIDIA only (e.g. `8.9`, `9.0`); `null` for others |
| `ecc_support` | Boolean: `true`/`false` |
| `price_usd_launch` | MSRP at launch in USD as a float; `null` if unknown |
| `price_usd_new_current` | Current new retail price in USD (best available across all sources); `null` ONLY if card is discontinued AND no new stock exists anywhere |
| `price_usd_newegg` | Current listed price on Newegg (new condition); `null` if not listed |
| `price_usd_amazon` | Current listed price on Amazon (new condition); `null` if not listed |
| `price_usd_bh` | Current listed price on B&H Photo (new condition); `null` if not listed |
| `price_usd_ebay_used` | Current median used/secondhand price on eBay; `null` if insufficient listings |
| `link_newegg` | Direct URL to the product on Newegg; `null` if not listed |
| `link_amazon` | Direct URL to the product on Amazon; `null` if not listed |
| `link_bh` | Direct URL to the product on B&H; `null` if not listed |
| `link_ebay` | Direct URL to eBay search results for this card (used listings); `null` if none |
| `cost_per_gb_vram_usd` | **Code-calculated**: `price_usd_new_current / vram_gb`; `null` if price unavailable |
| `fp32_per_dollar` | **Code-calculated**: `fp32_tflops / price_usd_new_current`; `null` if unavailable |
| `best_for` | Comma-separated tags: `gaming`, `ai_inference`, `ai_training`, `rendering`, `compute`, `workstation`, `budget`, `mobile`, `server` |
| `notes` | Free text: discontinued, server-only, requires special cooling, EoL, unified memory, etc. |

---

**PRICING RULES**

- **Search at least 3 times** per retailer per card before writing `null`. Vary your search queries each attempt.
- `price_usd_new_current`: Leave `null` only if the card is confirmed discontinued AND no new-condition stock exists on any platform. If even a single retailer has new stock, populate this field.
- `price_usd_ebay_used`: Pull the median of recent sold listings, not the asking price. If fewer than 3 sold listings exist, write `null`.
- Links must be direct product page URLs, not search result pages—except for eBay, where a filtered search URL is acceptable.
- Do not fabricate prices or links. If a link cannot be confirmed, write `null`.

---

**CALCULATION RULES**

Every derived numeric value must be computed using code execution. Do not do arithmetic mentally or estimate. Example workflow:

```python
# Run this for each card where both values are available
price = 399.99
vram_gb = 8
fp32 = 12.29

cost_per_gb = round(price / vram_gb, 2)
fp32_per_dollar = round(fp32 / price, 4)

print(cost_per_gb, fp32_per_dollar)
```

Paste the printed output into the CSV. Never skip this step.

---

**CATEGORY VALUES**

The `category` column must use **only** these exact strings:

- `consumer` — Retail gaming cards (GTX, RTX consumer, RX series, Arc)
- `professional` — Workstation cards (Quadro, RTX Axxx workstation, Radeon Pro, Arc Pro)
- `datacenter` — Server/HPC accelerators (H100, A100, MI300X, Gaudi, V100, etc.)
- `mobile` — Laptop/mobile discrete GPUs
- `integrated` — Integrated graphics (Intel Iris Xe, AMD Radeon on APUs, Apple M-series)

---

**SCOPE — INCLUDE EVERYTHING**

Cast the net as wide as possible. There is no minimum VRAM threshold. Include cards with 512MB, 1GB, 2GB—everything.

- **NVIDIA**: Tesla/Fermi/Kepler/Maxwell/Pascal/Volta/Turing/Ampere/Ada/Blackwell across all tiers—consumer, mobile, workstation, datacenter. Include Titan series, Quadro series, Tesla compute cards, Jetson if relevant.
- **AMD**: HD 5000 series through RX 9000 series. All Radeon Pro workstation lines. All Instinct MI datacenter series (MI50 through MI300X).
- **Intel**: All Arc Alchemist and Battlemage consumer cards, Arc Pro workstation cards, Gaudi 1/2/3 accelerators, older Larrabee/Xe lines if applicable.
- **Apple**: M1 through M4 GPU cores (integrated, note unified memory in `notes`).
- **Other accelerators**: Habana Gaudi series, any other notable AI accelerators.
- **Legacy cards still common on used market**: GTX 1080 Ti, RTX 2080 Ti, Titan RTX, Titan V, V100, K80, P100, Vega 64, RX 580—these are highly relevant for budget AI builders.

Do **not** include:
- Console GPUs (PS5, Xbox) unless they have a PC equivalent
- Multi-GPU system entries (list individual cards only)

---

**DATA QUALITY RULES**

1. All numeric columns: numbers or `null` only. No units in the cell (`256` not `256-bit`).
2. Boolean columns: `true`, `false`, or `null` only.
3. No thousand-separator commas in numbers (`45900` not `45,900`).
4. `best_for` tags must be from the approved list, comma-separated, no spaces (`gaming,ai_inference`).
5. If a spec is genuinely not applicable, use `null`—not zero.
6. First row is the header. All subsequent rows are data. No summary rows at the bottom.

---

**GGPLOT / LETPLOT COMPATIBILITY**

The CSV must load cleanly and support immediate plotting:

```python
import pandas as pd
from plotnine import ggplot, aes, geom_point

df = pd.read_csv("gpu_database.csv")

# Example: all cards with 16+ GB VRAM by price vs FP32 performance
df_ai = df[df["vram_gb"] >= 16]
ggplot(df_ai, aes(x="price_usd_new_current", y="fp32_tflops", color="category")) + geom_point()

# Example: cheapest cost per GB of VRAM
df.sort_values("cost_per_gb_vram_usd").head(20)

# Example: filter to used market deals under $300
df[df["price_usd_ebay_used"] < 300].sort_values("fp32_tflops", ascending=False)
```

All of the above must work without any preprocessing.

---

**DELIVERABLE**

Return the complete CSV. Aim for **1,000+ rows**—more is better. If you cannot finish in one pass, clearly state the last card you completed and offer to continue so rows can be appended cleanly without duplicates.


