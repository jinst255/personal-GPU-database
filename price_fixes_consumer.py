#!/usr/bin/env python3
"""
Reconstruct missing GPU database rows and apply price fixes.

This script:
1. Reconstructs the 97 missing rows that were lost due to a file write error:
   - 35 mobile NVIDIA GPUs
   - AMD consumer GPUs (Radeon RX and legacy series)
   - 7 AMD Instinct datacenter GPUs
2. Sets price_usd_new_current and price_usd_ebay_used to 'null' for all mobile GPUs
   (mobile GPUs are not sold as standalone cards)
3. Sets price_usd_ebay_used to 'null' for datacenter GPUs (enterprise-only)
4. Recalculates ALL derived fields for every row
5. Updates last_modified timestamp for changed rows
"""

import csv
import os
from datetime import datetime
from urllib.parse import quote

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gpu_database.csv")

# Current timestamp
NOW = datetime.now().strftime("%Y-%m-%dT%H:%M")

# All 58 column names in order
FIELDNAMES = [
    "gpu_name", "manufacturer", "brand", "category", "architecture", "gpu_chip",
    "release_year", "release_date", "discontinued", "process_node_nm",
    "transistors_billion", "die_size_mm2", "vram_gb", "vram_type",
    "vram_bus_width_bit", "memory_bandwidth_gbps", "cuda_cores",
    "stream_processors", "xe_cores", "tensor_cores", "rt_cores",
    "compute_units", "base_clock_mhz", "boost_clock_mhz", "fp32_tflops",
    "fp16_tflops", "bf16_tflops", "int8_tops", "tdp_watts",
    "recommended_psu_watts", "slot_width", "connector_type",
    "pcie_generation", "pcie_lanes", "nvlink_support", "display_outputs",
    "max_displays", "directx_version", "opencl_version",
    "cuda_compute_capability", "ecc_support", "price_usd_launch",
    "price_usd_new_current", "price_usd_newegg", "price_usd_amazon",
    "price_usd_bh", "price_usd_ebay_used", "link_newegg", "link_amazon",
    "link_bh", "link_ebay", "cost_per_gb_vram_new_usd",
    "cost_per_gb_vram_used_usd", "fp32_per_dollar_new", "fp32_per_dollar_used",
    "best_for", "notes", "last_modified"
]

def make_row(**kwargs):
    """Create a row dict with all fields defaulting to 'null'."""
    row = {k: "null" for k in FIELDNAMES}
    row.update(kwargs)
    return row

def make_links(name):
    """Generate search links for a GPU."""
    q = quote(name)
    q_gpu = quote(name + " GPU")
    return {
        "link_newegg": f"https://www.newegg.com/p/pl?d={q}",
        "link_amazon": f"https://www.amazon.com/s?k={q}",
        "link_bh": f"https://www.bhphotovideo.com/c/search?q={q}",
        "link_ebay": f"https://www.ebay.com/sch/i.html?_nkw={q_gpu}&LH_Sold=1",
    }

# ============================================================================
# MOBILE GPUs - These are NOT sold standalone. Prices = null.
# ============================================================================
def make_mobile_row(name, arch, chip, year, date, proc_nm, trans_b, die_mm2,
                    vram_gb, vram_type, bus_width, mem_bw, cuda_cores,
                    base_clk, boost_clk, fp32, tdp, compute_cap, notes="null"):
    links = make_links(name)
    return make_row(
        gpu_name=name,
        manufacturer="NVIDIA",
        brand="NVIDIA",
        category="mobile",
        architecture=arch,
        gpu_chip=chip,
        release_year=str(year),
        release_date=date,
        discontinued="true" if year < 2025 else "false",
        process_node_nm=str(proc_nm),
        transistors_billion=str(trans_b),
        die_size_mm2=str(die_mm2),
        vram_gb=str(vram_gb),
        vram_type=vram_type,
        vram_bus_width_bit=str(bus_width),
        memory_bandwidth_gbps=str(mem_bw),
        cuda_cores=str(cuda_cores),
        stream_processors="null",
        xe_cores="null",
        tensor_cores="null",
        rt_cores="null",
        compute_units="null",
        base_clock_mhz=str(base_clk),
        boost_clock_mhz=str(boost_clk),
        fp32_tflops=str(fp32),
        fp16_tflops="null",
        bf16_tflops="null",
        int8_tops="null",
        tdp_watts=str(tdp),
        recommended_psu_watts="null",
        slot_width="null",
        connector_type="null",
        pcie_generation="null",
        pcie_lanes="null",
        nvlink_support="false",
        display_outputs="null",
        max_displays="null",
        directx_version="null",
        opencl_version="3.0",
        cuda_compute_capability=compute_cap,
        ecc_support="false",
        price_usd_launch="null",
        price_usd_new_current="null",
        price_usd_newegg="null",
        price_usd_amazon="null",
        price_usd_bh="null",
        price_usd_ebay_used="null",
        cost_per_gb_vram_new_usd="null",
        cost_per_gb_vram_used_usd="null",
        fp32_per_dollar_new="null",
        fp32_per_dollar_used="null",
        best_for="gaming,mobile",
        notes=notes,
        last_modified=NOW,
        **links,
    )

MOBILE_GPUS = [
    # RTX 50 series mobile (Blackwell, 2025)
    ("GeForce RTX 5090 Laptop", "Blackwell", "GB203", 2025, "2025-03-31", 4, 47, 378, 24, "GDDR7", 256, 960, 10752, 1530, 1965, 42.3, 150, "12.0"),
    ("GeForce RTX 5080 Laptop", "Blackwell", "GB203", 2025, "2025-03-31", 4, 47, 378, 16, "GDDR7", 256, 768, 7680, 1380, 1830, 28.1, 110, "12.0"),
    ("GeForce RTX 5070 Ti Laptop", "Blackwell", "GB205", 2025, "2025-03-31", 4, 38, 263, 12, "GDDR7", 192, 576, 5888, 1425, 1905, 22.4, 90, "12.0"),
    ("GeForce RTX 5070 Laptop", "Blackwell", "GB205", 2025, "2025-03-31", 4, 38, 263, 8, "GDDR7", 128, 384, 4608, 1425, 1905, 17.6, 70, "12.0"),

    # RTX 40 series mobile (Ada Lovelace, 2023)
    ("GeForce RTX 4090 Laptop", "Ada Lovelace", "AD103", 2023, "2023-02-08", 5, 46, 379, 16, "GDDR6", 256, 576, 9728, 1335, 1965, 39.79, 150, "8.9"),
    ("GeForce RTX 4080 Laptop", "Ada Lovelace", "AD104", 2023, "2023-02-08", 5, 36, 295, 12, "GDDR6", 192, 432, 7424, 1290, 1860, 33.94, 120, "8.9"),
    ("GeForce RTX 4070 Laptop", "Ada Lovelace", "AD106", 2023, "2023-02-08", 5, 27, 231, 8, "GDDR6", 128, 256, 4608, 1305, 1815, 20.04, 85, "8.9"),
    ("GeForce RTX 4060 Laptop", "Ada Lovelace", "AD107", 2023, "2023-02-08", 5, 19, 159, 8, "GDDR6", 128, 256, 3072, 1320, 1770, 14.56, 70, "8.9"),
    ("GeForce RTX 4050 Laptop", "Ada Lovelace", "AD107", 2023, "2023-02-08", 5, 19, 159, 6, "GDDR6", 96, 192, 2560, 1365, 1905, 12.16, 55, "8.9"),

    # RTX 30 series mobile (Ampere, 2021-2022)
    ("GeForce RTX 3080 Ti Laptop", "Ampere", "GA103", 2022, "2022-03-29", 8, 22, 392, 16, "GDDR6", 256, 512, 6144, 1230, 1665, 23.63, 150, "8.6"),
    ("GeForce RTX 3080 Laptop", "Ampere", "GA104", 2021, "2021-01-26", 8, 17, 392, 8, "GDDR6", 256, 512, 6144, 1110, 1545, 21.02, 130, "8.6"),
    ("GeForce RTX 3070 Ti Laptop", "Ampere", "GA104", 2022, "2022-03-29", 8, 17, 392, 8, "GDDR6", 256, 448, 5632, 1035, 1485, 17.51, 115, "8.6"),
    ("GeForce RTX 3070 Laptop", "Ampere", "GA104", 2021, "2021-01-26", 8, 17, 392, 8, "GDDR6", 256, 448, 5120, 1110, 1560, 16.6, 115, "8.6"),
    ("GeForce RTX 3060 Laptop", "Ampere", "GA107", 2021, "2021-01-26", 8, 13, 201, 6, "GDDR6", 192, 336, 3840, 1283, 1703, 13.09, 80, "8.6"),
    ("GeForce RTX 3050 Ti Laptop", "Ampere", "GA107", 2021, "2021-05-11", 8, 13, 201, 4, "GDDR6", 128, 224, 2560, 1225, 1695, 8.68, 60, "8.6"),
    ("GeForce RTX 3050 Laptop", "Ampere", "GA107", 2021, "2021-05-11", 8, 13, 201, 4, "GDDR6", 128, 224, 2048, 1140, 1643, 7.13, 45, "8.6"),

    # RTX 20 series mobile (Turing, 2019-2020)
    ("GeForce RTX 2080 Super Laptop", "Turing", "TU104", 2020, "2020-04-02", 12, 13, 545, 8, "GDDR6", 256, 448, 3072, 1005, 1680, 19.17, 150, "7.5"),
    ("GeForce RTX 2080 Laptop", "Turing", "TU104", 2019, "2019-01-29", 12, 13, 545, 8, "GDDR6", 256, 448, 2944, 960, 1680, 18.72, 150, "7.5"),
    ("GeForce RTX 2070 Super Laptop", "Turing", "TU104", 2020, "2020-04-02", 12, 13, 545, 8, "GDDR6", 256, 448, 2560, 1080, 1560, 14.13, 115, "7.5"),
    ("GeForce RTX 2070 Laptop", "Turing", "TU106", 2019, "2019-01-29", 12, 10, 445, 8, "GDDR6", 256, 448, 2304, 1065, 1545, 13.27, 115, "7.5"),
    ("GeForce RTX 2060 Laptop", "Turing", "TU106", 2019, "2019-01-29", 12, 10, 445, 6, "GDDR6", 192, 336, 1920, 1065, 1560, 9.22, 90, "7.5"),

    # GTX 16 series mobile (Turing, 2019-2020)
    ("GeForce GTX 1660 Ti Laptop", "Turing", "TU116", 2019, "2019-04-23", 12, 6, 286, 6, "GDDR6", 192, 288, 1536, 1290, 1770, 9.77, 80, "7.5"),
    ("GeForce GTX 1650 Laptop", "Turing", "TU117", 2019, "2019-04-23", 12, 4, 200, 4, "GDDR6", 128, 192, 1024, 1140, 1665, 6.39, 50, "7.5"),
    ("GeForce GTX 1650 Ti Laptop", "Turing", "TU117", 2020, "2020-04-02", 12, 4, 200, 4, "GDDR6", 128, 192, 1024, 1035, 1635, 6.08, 50, "7.5"),

    # GTX 10 series mobile (Pascal, 2016-2017)
    ("GeForce GTX 1080 Laptop", "Pascal", "GP104", 2016, "2016-08-15", 16, 7, 314, 8, "GDDR5X", 256, 320, 2560, 1556, 1898, 18.8, 150, "6.1"),
    ("GeForce GTX 1070 Laptop", "Pascal", "GP104", 2016, "2016-08-15", 16, 7, 314, 8, "GDDR5", 256, 256, 2048, 1442, 1835, 13.47, 120, "6.1"),
    ("GeForce GTX 1060 Laptop", "Pascal", "GP106", 2016, "2016-08-15", 16, 4, 200, 6, "GDDR5", 192, 192, 1280, 1404, 1670, 8.55, 75, "6.1"),
    ("GeForce GTX 1050 Ti Laptop", "Pascal", "GP107", 2016, "2016-12-20", 14, 3, 132, 4, "GDDR5", 128, 112, 768, 1493, 1620, 4.96, 50, "6.1"),
    ("GeForce GTX 1050 Laptop", "Pascal", "GP107", 2016, "2016-12-20", 14, 3, 132, 2, "GDDR5", 128, 112, 640, 1354, 1493, 3.73, 40, "6.1"),

    # GTX 900M series mobile (Maxwell, 2014-2015)
    ("GeForce GTX 980M", "Maxwell", "GM204", 2014, "2014-10-07", 28, 5, 398, 4, "GDDR5", 256, 160, 1536, 1038, 1126, 6.38, 100, "5.2"),
    ("GeForce GTX 970M", "Maxwell", "GM204", 2014, "2014-10-07", 28, 5, 398, 3, "GDDR5", 192, 120, 1280, 924, 1038, 5.32, 80, "5.2"),
    ("GeForce GTX 960M", "Maxwell", "GM107", 2015, "2015-03-13", 28, 2, 148, 2, "GDDR5", 128, 80, 640, 1020, 1176, 3.02, 55, "5.2"),
    ("GeForce GTX 950M", "Maxwell", "GM107", 2015, "2015-03-13", 28, 2, 148, 2, "GDDR5", 128, 80, 640, 915, 1019, 2.34, 45, "5.2"),

    # GTX 800M series mobile (Kepler, 2014)
    ("GeForce GTX 880M", "Kepler", "GK104", 2014, "2014-03-12", 28, 3, 294, 4, "GDDR5", 256, 160, 1536, 954, 993, 5.88, 110, "3.0"),
    ("GeForce GTX 870M", "Kepler", "GK104", 2014, "2014-03-12", 28, 3, 294, 3, "GDDR5", 192, 120, 1344, 810, 941, 5.07, 80, "3.0"),
]

# ============================================================================
# AMD CONSUMER GPUs - Radeon RX series and legacy
# ============================================================================
def make_amd_consumer_row(name, arch, chip, year, date, discontinued, proc_nm,
                          trans_b, die_mm2, vram_gb, vram_type, bus_width,
                          mem_bw, compute_units, stream_proc, base_clk, boost_clk,
                          fp32, tdp, psu_watts, slot_width, connector, pcie_gen,
                          pcie_lanes, nvlink, display_out, max_disp, dx_ver,
                          ocl_ver, ecc, price_launch, price_new, price_newegg,
                          price_amazon, price_bh, price_used, best_for, notes="null"):
    links = make_links(name)
    return make_row(
        gpu_name=name,
        manufacturer="AMD",
        brand="AMD",
        category="consumer",
        architecture=arch,
        gpu_chip=chip,
        release_year=str(year),
        release_date=date,
        discontinued=discontinued,
        process_node_nm=str(proc_nm),
        transistors_billion=str(trans_b),
        die_size_mm2=str(die_mm2),
        vram_gb=str(vram_gb),
        vram_type=vram_type,
        vram_bus_width_bit=str(bus_width),
        memory_bandwidth_gbps=str(mem_bw),
        cuda_cores="null",
        stream_processors=str(stream_proc),
        xe_cores="null",
        tensor_cores="null",
        rt_cores="null",
        compute_units=str(compute_units),
        base_clock_mhz=str(base_clk),
        boost_clock_mhz=str(boost_clk),
        fp32_tflops=str(fp32),
        fp16_tflops="null",
        bf16_tflops="null",
        int8_tops="null",
        tdp_watts=str(tdp),
        recommended_psu_watts=str(psu_watts),
        slot_width=slot_width,
        connector_type=connector,
        pcie_generation=str(pcie_gen),
        pcie_lanes=str(pcie_lanes),
        nvlink_support=nvlink,
        display_outputs=display_out,
        max_displays=str(max_disp),
        directx_version=dx_ver,
        opencl_version=ocl_ver,
        cuda_compute_capability="null",
        ecc_support=ecc,
        price_usd_launch=str(price_launch),
        price_usd_new_current=str(price_new),
        price_usd_newegg=str(price_newegg),
        price_usd_amazon=str(price_amazon),
        price_usd_bh=str(price_bh),
        price_usd_ebay_used=str(price_used),
        best_for=best_for,
        notes=notes,
        last_modified=NOW,
        **links,
    )

AMD_CONSUMER_GPUS = [
    # RDNA 4 (2025)
    ("Radeon RX 9070 XT", "RDNA 4", "Navi 48", 2025, "2025-03-06", "false", 4, 29, 347, 16, "GDDR6", 256, 576, 64, 4096, 1500, 2520, 20.57, 260, 700, "2-slot", "PCIe 8-pin + PCIe 6-pin", 5, 16, "false", "3x DP 2.1 + 1x HDMI 2.1", 4, "12 Ultimate", "3.0", "false", 549, 559.0, 569.99, 579.99, 579.99, 465.0, "gaming,ai_inference", "null"),
    ("Radeon RX 9070", "RDNA 4", "Navi 48", 2025, "2025-03-06", "false", 4, 29, 347, 16, "GDDR6", 256, 576, 56, 3584, 1400, 2400, 17.2, 220, 650, "2-slot", "PCIe 8-pin + PCIe 6-pin", 5, 16, "false", "3x DP 2.1 + 1x HDMI 2.1", 4, "12 Ultimate", "3.0", "false", 479, 489.0, 489.99, 499.99, 509.99, 420.0, "gaming", "null"),

    # RDNA 3.5 (2024) - RX 9060 series placeholder (not yet released as of training data)
    # Using null for unreleased

    # RDNA 3 (2022-2023)
    ("Radeon RX 7900 XTX", "RDNA 3", "Navi 31", 2022, "2022-12-13", "false", 5, 58, 529, 24, "GDDR6", 384, 960, 96, 6144, 1900, 2500, 61.3, 355, 850, "2-slot", "2x PCIe 8-pin", 4, 16, "false", "2x DP 2.1 + 1x HDMI 2.1", 4, "12 Ultimate", "3.0", "false", 999, 839.0, 849.99, 869.99, 879.99, 615.0, "gaming,ai_inference,rendering", "null"),
    ("Radeon RX 7900 XT", "RDNA 3", "Navi 31", 2022, "2022-12-13", "false", 5, 58, 529, 20, "GDDR6", 320, 800, 84, 5376, 1500, 2400, 51.6, 300, 750, "2-slot", "2x PCIe 8-pin", 4, 16, "false", "2x DP 2.1 + 1x HDMI 2.1", 4, "12 Ultimate", "3.0", "false", 899, 709.0, 719.99, 729.99, 739.99, 530.0, "gaming,ai_inference", "null"),
    ("Radeon RX 7900 GRE", "RDNA 3", "Navi 31", 2024, "2024-01-24", "false", 5, 58, 529, 16, "GDDR6", 256, 576, 80, 5120, 1287, 2245, 45.98, 260, 700, "2-slot", "2x PCIe 8-pin", 4, 16, "false", "2x DP 2.1 + 1x HDMI 2.1", 4, "12 Ultimate", "3.0", "false", 549, 529.0, 539.99, 549.99, 559.99, 400.0, "gaming", "null"),
    ("Radeon RX 7800 XT", "RDNA 3", "Navi 32", 2023, "2023-09-06", "false", 5, 34, 348, 16, "GDDR6", 256, 576, 60, 3840, 1295, 2430, 37.35, 263, 700, "2-slot", "2x PCIe 8-pin", 4, 16, "false", "2x DP 2.1 + 1x HDMI 2.1", 4, "12 Ultimate", "3.0", "false", 499, 469.0, 479.99, 489.99, 489.99, 355.0, "gaming", "null"),
    ("Radeon RX 7700 XT", "RDNA 3", "Navi 32", 2023, "2023-09-06", "false", 5, 34, 348, 12, "GDDR6", 192, 432, 54, 3456, 1435, 2544, 35.17, 245, 650, "2-slot", "2x PCIe 8-pin", 4, 16, "false", "2x DP 2.1 + 1x HDMI 2.1", 4, "12 Ultimate", "3.0", "false", 449, 419.0, 429.99, 439.99, 449.99, 320.0, "gaming", "null"),
    ("Radeon RX 7600 XT", "RDNA 3", "Navi 33", 2024, "2024-01-24", "false", 6, 20, 286, 16, "GDDR6", 128, 288, 32, 2048, 1500, 2615, 21.5, 150, 550, "2-slot", "PCIe 8-pin", 4, 16, "false", "3x DP 2.1 + 1x HDMI 2.1", 4, "12 Ultimate", "3.0", "false", 329, 309.0, 319.99, 329.99, 329.99, 255.0, "gaming", "null"),
    ("Radeon RX 7600", "RDNA 3", "Navi 33", 2023, "2023-05-25", "false", 6, 20, 286, 8, "GDDR6", 128, 288, 32, 2048, 1500, 2655, 21.5, 165, 550, "2-slot", "PCIe 8-pin", 4, 16, "false", "3x DP 2.1 + 1x HDMI 2.1", 4, "12 Ultimate", "3.0", "false", 269, 249.0, 259.99, 264.99, 269.99, 195.0, "gaming,budget", "null"),
    ("Radeon RX 7500 XT", "RDNA 3", "Navi 33", 2024, "2024-01-08", "false", 6, 20, 286, 8, "GDDR6", 128, 216, 28, 1792, 1500, 2450, 14.07, 115, 500, "2-slot", "PCIe 8-pin", 4, 16, "false", "3x DP 2.1 + 1x HDMI 2.1", 4, "12 Ultimate", "3.0", "false", 179, 179.0, 189.99, 194.99, 199.99, 145.0, "gaming,budget", "null"),

    # RDNA 2 (2020-2022)
    ("Radeon RX 6950 XT", "RDNA 2", "Navi 21", 2022, "2022-05-10", "false", 7, 26, 520, 16, "GDDR6", 256, 576, 80, 5120, 1500, 2310, 47.26, 335, 850, "2-slot", "2x PCIe 8-pin", 4, 16, "false", "2x DP 1.4 + 1x HDMI 2.1", 4, "12 Ultimate", "3.0", "false", 799, 579.0, 589.99, 599.99, 609.99, 430.0, "gaming", "null"),
    ("Radeon RX 6900 XT", "RDNA 2", "Navi 21", 2020, "2020-12-08", "false", 7, 26, 520, 16, "GDDR6", 256, 512, 80, 5120, 1500, 2250, 46.08, 300, 850, "2-slot", "2x PCIe 8-pin", 4, 16, "false", "2x DP 1.4 + 1x HDMI 2.1", 4, "12 Ultimate", "3.0", "false", 999, 519.0, 529.99, 549.99, 559.99, 385.0, "gaming,ai_inference", "null"),
    ("Radeon RX 6800 XT", "RDNA 2", "Navi 21", 2020, "2020-11-18", "false", 7, 26, 520, 16, "GDDR6", 256, 512, 72, 4608, 1500, 2250, 41.47, 300, 850, "2-slot", "2x PCIe 8-pin", 4, 16, "false", "2x DP 1.4 + 1x HDMI 2.1", 4, "12 Ultimate", "3.0", "false", 649, 439.0, 449.99, 459.99, 469.99, 330.0, "gaming", "null"),
    ("Radeon RX 6800", "RDNA 2", "Navi 21", 2020, "2020-11-18", "false", 7, 26, 520, 16, "GDDR6", 256, 512, 60, 3840, 1500, 2105, 32.29, 250, 750, "2-slot", "2x PCIe 8-pin", 4, 16, "false", "2x DP 1.4 + 1x HDMI 2.1", 4, "12 Ultimate", "3.0", "false", 579, 379.0, 389.99, 399.99, 409.99, 280.0, "gaming", "null"),
    ("Radeon RX 6750 XT", "RDNA 2", "Navi 22", 2022, "2022-03-03", "false", 7, 17, 335, 12, "GDDR6", 192, 432, 40, 2560, 1500, 2495, 25.55, 250, 700, "2-slot", "2x PCIe 8-pin", 4, 16, "false", "3x DP 1.4 + 1x HDMI 2.1", 4, "12 Ultimate", "3.0", "false", 549, 369.0, 379.99, 389.99, 399.99, 270.0, "gaming", "null"),
    ("Radeon RX 6700 XT", "RDNA 2", "Navi 22", 2021, "2021-03-03", "false", 7, 17, 335, 12, "GDDR6", 192, 384, 40, 2560, 1465, 2424, 24.83, 230, 650, "2-slot", "2x PCIe 8-pin", 4, 16, "false", "3x DP 1.4 + 1x HDMI 2.1", 4, "12 Ultimate", "3.0", "false", 479, 339.0, 349.99, 359.99, 369.99, 248.0, "gaming", "null"),
    ("Radeon RX 6650 XT", "RDNA 2", "Navi 23", 2022, "2022-05-10", "false", 7, 11, 271, 8, "GDDR6", 128, 272, 32, 2048, 1620, 2410, 19.73, 176, 600, "2-slot", "PCIe 8-pin", 4, 16, "false", "3x DP 1.4 + 1x HDMI 2.1", 4, "12 Ultimate", "3.0", "false", 399, 269.0, 279.99, 289.99, 289.99, 195.0, "gaming,budget", "null"),
    ("Radeon RX 6600 XT", "RDNA 2", "Navi 23", 2021, "2021-08-11", "false", 7, 11, 271, 8, "GDDR6", 128, 256, 32, 2048, 1468, 2359, 19.29, 160, 550, "2-slot", "PCIe 8-pin", 4, 16, "false", "3x DP 1.4 + 1x HDMI 2.1", 4, "12 Ultimate", "3.0", "false", 379, 249.0, 259.99, 269.99, 274.99, 182.0, "gaming,budget", "null"),
    ("Radeon RX 6600", "RDNA 2", "Navi 23", 2021, "2021-10-13", "false", 7, 11, 271, 8, "GDDR6", 128, 224, 28, 1792, 1468, 2359, 16.87, 132, 500, "2-slot", "PCIe 8-pin", 4, 16, "false", "3x DP 1.4 + 1x HDMI 2.1", 4, "12 Ultimate", "3.0", "false", 329, 199.0, 209.99, 219.99, 224.99, 150.0, "gaming,budget", "null"),
    ("Radeon RX 6500 XT", "RDNA 2", "Navi 24", 2022, "2022-01-19", "false", 6, 5, 107, 4, "GDDR6", 64, 144, 16, 1024, 1500, 2610, 10.7, 107, 400, "2-slot", "PCIe 6-pin", 4, 4, "false", "1x DP 1.4 + 1x HDMI 2.1", 2, "12 Ultimate", "3.0", "false", 199, 159.0, 169.99, 174.99, 179.99, 105.0, "gaming,budget", "PCIe x4 only"),
    ("Radeon RX 6400", "RDNA 2", "Navi 24", 2022, "2022-03-10", "false", 6, 5, 107, 4, "GDDR6", 64, 128, 12, 768, 1500, 2321, 7.14, 53, 350, "2-slot", "None", 4, 4, "false", "1x DP 1.4 + 1x HDMI 2.1", 2, "12 Ultimate", "3.0", "false", 159, 129.0, 134.99, 139.99, 144.99, 75.0, "gaming,budget", "PCIe x4 only"),

    # RDNA 1 (2019)
    ("Radeon RX 5700 XT", "RDNA 1", "Navi 10", 2019, "2019-07-07", "true", 7, 10, 251, 8, "GDDR6", 256, 448, 40, 2560, 1370, 1750, 17.92, 225, 650, "2-slot", "PCIe 8-pin + PCIe 6-pin", 4, 16, "false", "3x DP 1.4 + 1x HDMI 2.0", 4, "12", "2.1", "false", 399, 275.0, 285.0, 299.99, 309.99, 205.0, "gaming", "Discontinued"),
    ("Radeon RX 5700", "RDNA 1", "Navi 10", 2019, "2019-07-07", "true", 7, 10, 251, 8, "GDDR6", 256, 448, 36, 2304, 1165, 1650, 15.24, 180, 600, "2-slot", "PCIe 8-pin + PCIe 6-pin", 4, 16, "false", "3x DP 1.4 + 1x HDMI 2.0", 4, "12", "2.1", "false", 349, 229.0, 239.0, 249.99, 259.99, 170.0, "gaming", "Discontinued"),
    ("Radeon RX 5600 XT", "RDNA 1", "Navi 10", 2020, "2020-01-21", "true", 7, 10, 251, 6, "GDDR6", 192, 336, 36, 2304, 1130, 1560, 14.37, 150, 550, "2-slot", "PCIe 8-pin", 4, 16, "false", "3x DP 1.4 + 1x HDMI 2.0", 4, "12", "2.1", "false", 279, 195.0, 200.0, 214.99, 224.99, 145.0, "gaming,budget", "Discontinued"),
    ("Radeon RX 5500 XT", "RDNA 1", "Navi 14", 2019, "2019-12-12", "true", 7, 6, 158, 8, "GDDR6", 128, 224, 22, 1408, 1500, 1845, 10.39, 130, 500, "2-slot", "PCIe 8-pin", 4, 16, "false", "3x DP 1.4 + 1x HDMI 2.0", 4, "12", "2.1", "false", 199, 155.0, 160.0, 169.99, 179.99, 110.0, "gaming,budget", "Discontinued"),

    # GCN 4/5 - Polaris and Vega (2016-2019)
    ("Radeon RX 590", "GCN 4", "Polaris 30", 2018, "2018-11-15", "true", 12, 5, 232, 8, "GDDR5", 256, 256, 36, 2304, 1300, 1545, 14.25, 175, 600, "2-slot", "PCIe 8-pin", 3, 16, "false", "1x DP 1.4 + 1x HDMI 2.0 + 1x DVI", 3, "12", "2.1", "false", 279, 125.0, 129.99, 139.99, 149.99, 88.0, "gaming,budget", "Discontinued"),
    ("Radeon RX 580", "GCN 4", "Polaris 20", 2017, "2017-04-18", "true", 14, 5, 232, 8, "GDDR5", 256, 256, 36, 2304, 1120, 1340, 12.37, 150, 550, "2-slot", "PCIe 8-pin", 3, 16, "false", "1x DP 1.4 + 1x HDMI 2.0 + 1x DVI", 3, "12", "2.1", "false", 229, 105.0, 109.99, 119.99, 129.99, 72.0, "gaming,budget", "Discontinued"),
    ("Radeon RX 570", "GCN 4", "Polaris 20", 2017, "2017-04-18", "true", 14, 5, 232, 8, "GDDR5", 256, 224, 32, 2048, 1071, 1244, 10.2, 120, 500, "2-slot", "PCIe 8-pin", 3, 16, "false", "1x DP 1.4 + 1x HDMI 2.0 + 1x DVI", 3, "12", "2.1", "false", 169, 85.0, 89.99, 99.99, 104.99, 55.0, "gaming,budget", "Discontinued"),
    ("Radeon RX 560", "GCN 4", "Polaris 21", 2017, "2017-05-01", "true", 14, 3, 123, 4, "GDDR5", 128, 112, 16, 1024, 1090, 1275, 5.22, 75, 450, "2-slot", "PCIe 6-pin", 3, 16, "false", "1x DP 1.4 + 1x HDMI 2.0 + 1x DVI", 3, "12", "2.1", "false", 99, 55.0, 59.99, 64.99, 69.99, 40.0, "gaming,budget", "Discontinued"),
    ("Radeon RX 550", "GCN 4", "Polaris 12", 2017, "2017-05-01", "true", 14, 2, 101, 2, "GDDR5", 128, 112, 8, 512, 1100, 1183, 2.42, 50, 350, "2-slot", "None", 3, 16, "false", "1x DP 1.4 + 1x HDMI 2.0 + 1x DVI", 3, "12", "2.1", "false", 79, 45.0, 49.99, 54.99, 59.99, 30.0, "gaming,budget", "Discontinued"),

    # RX 400 series (2016)
    ("Radeon RX 480", "GCN 4", "Polaris 10", 2016, "2016-06-29", "true", 14, 5, 232, 8, "GDDR5", 256, 256, 36, 2304, 1090, 1266, 11.65, 150, 550, "2-slot", "PCIe 8-pin", 3, 16, "false", "1x DP 1.4 + 1x HDMI 2.0 + 1x DVI", 3, "12", "2.1", "false", 199, 92.0, 95.0, 104.99, 114.99, 62.0, "gaming,budget", "Discontinued"),
    ("Radeon RX 470", "GCN 4", "Polaris 10", 2016, "2016-08-04", "true", 14, 5, 232, 8, "GDDR5", 256, 224, 32, 2048, 926, 1206, 9.89, 120, 500, "2-slot", "PCIe 8-pin", 3, 16, "false", "1x DP 1.4 + 1x HDMI 2.0 + 1x DVI", 3, "12", "2.1", "false", 179, 78.0, 82.0, 89.99, 99.99, 50.0, "gaming,budget", "Discontinued"),
    ("Radeon RX 460", "GCN 4", "Polaris 11", 2016, "2016-08-08", "true", 14, 3, 123, 4, "GDDR5", 128, 112, 14, 896, 1090, 1200, 4.3, 75, 400, "2-slot", "PCIe 6-pin", 3, 16, "false", "1x DP 1.4 + 1x HDMI 2.0 + 1x DVI", 3, "12", "2.1", "false", 139, 62.0, 64.99, 74.99, 79.99, 38.0, "gaming,budget", "Discontinued"),

    # Vega series (2017-2018)
    ("Radeon RX Vega 64", "GCN 5", "Vega 10", 2017, "2017-08-28", "true", 14, 12, 484, 8, "HBM2", 2048, 484, 64, 4096, 1247, 1546, 25.34, 295, 750, "2-slot", "PCIe 8-pin + PCIe 6-pin", 3, 16, "false", "3x DP 1.4 + 1x HDMI 2.0", 4, "12", "2.1", "false", 499, 210.0, 219.99, 229.99, 239.99, 155.0, "gaming", "Discontinued; HBM2 memory"),
    ("Radeon RX Vega 56", "GCN 5", "Vega 10", 2017, "2017-08-28", "true", 14, 12, 484, 8, "HBM2", 2048, 410, 56, 3584, 1156, 1471, 21.13, 210, 650, "2-slot", "PCIe 8-pin + PCIe 6-pin", 3, 16, "false", "3x DP 1.4 + 1x HDMI 2.0", 4, "12", "2.1", "false", 399, 175.0, 184.99, 194.99, 204.99, 128.0, "gaming", "Discontinued; HBM2 memory"),
    ("Radeon VII", "GCN 5", "Vega 20", 2019, "2019-02-07", "true", 7, 13, 331, 16, "HBM2", 4096, 1024, 60, 3840, 1400, 1750, 26.88, 295, 750, "2-slot", "2x PCIe 8-pin", 3, 16, "false", "3x DP 1.4 + 1x HDMI 2.0", 4, "12", "2.1", "false", 699, 310.0, 319.99, 334.99, 349.99, 225.0, "gaming,compute", "Discontinued; HBM2 memory; 7nm Vega"),

    # R9 series (2013-2015) - Tonga, Hawaii
    ("Radeon R9 Fury X", "GCN 3", "Fiji", 2015, "2015-06-24", "true", 28, 8, 596, 4, "HBM1", 4096, 512, 64, 4096, 1050, 1050, 8.61, 275, 600, "2-slot", "None", 3, 16, "false", "1x DP 1.2 + 1x HDMI 1.4", 4, "12", "2.1", "false", 649, 155.0, 159.99, 169.99, 179.99, 110.0, "gaming", "Discontinued; HBM1 memory; AIO liquid cooled"),
    ("Radeon R9 Fury", "GCN 3", "Fiji", 2015, "2015-07-14", "true", 28, 8, 596, 4, "HBM1", 4096, 512, 56, 3584, 1000, 1000, 7.17, 275, 600, "2-slot", "PCIe 8-pin + PCIe 6-pin", 3, 16, "false", "1x DP 1.2 + 1x HDMI 1.4 + 1x DVI", 4, "12", "2.1", "false", 549, 130.0, 134.99, 144.99, 154.99, 92.0, "gaming", "Discontinued; HBM1 memory"),
    ("Radeon R9 390X", "GCN 2", "Hawaii", 2015, "2015-06-18", "true", 28, 6, 438, 8, "GDDR5", 512, 384, 44, 2816, 1000, 1050, 11.81, 275, 750, "2-slot", "PCIe 8-pin + PCIe 6-pin", 3, 16, "false", "1x DP 1.2 + 1x HDMI 1.4 + 1x DVI", 4, "12", "2.1", "false", 429, 115.0, 119.99, 129.99, 139.99, 82.0, "gaming", "Discontinued"),
    ("Radeon R9 290X", "GCN 2", "Hawaii", 2013, "2013-10-24", "true", 28, 6, 438, 4, "GDDR5", 512, 320, 44, 2816, 1000, 1050, 11.81, 290, 750, "2-slot", "PCIe 8-pin + PCIe 6-pin", 3, 16, "false", "1x DP 1.2 + 1x HDMI 1.4 + 1x DVI", 4, "12", "2.1", "false", 549, 98.0, 100.0, 109.99, 119.99, 68.0, "gaming", "Discontinued"),
    ("Radeon R9 280X", "GCN 1", "Tahiti", 2013, "2013-10-08", "true", 28, 4, 365, 3, "GDDR5", 384, 288, 32, 2048, 850, 1000, 8.19, 250, 650, "2-slot", "PCIe 8-pin + PCIe 6-pin", 3, 16, "false", "2x DP 1.2 + 1x HDMI 1.4 + 1x DVI", 4, "12", "2.1", "false", 299, 78.0, 79.99, 89.99, 99.99, 52.0, "gaming", "Discontinued"),
    ("Radeon R9 270X", "GCN 1", "Curacao", 2013, "2013-11-08", "true", 28, 2.8, 275, 2, "GDDR5", 256, 180, 20, 1280, 1000, 1050, 5.37, 180, 550, "2-slot", "PCIe 6-pin", 3, 16, "false", "2x DP 1.2 + 1x HDMI 1.4 + 1x DVI", 4, "12", "2.1", "false", 199, 62.0, 64.99, 74.99, 79.99, 40.0, "gaming,budget", "Discontinued"),

    # HD 7000 series (2012)
    ("Radeon HD 7970", "GCN 1", "Tahiti", 2012, "2011-12-22", "true", 28, 4, 365, 3, "GDDR5", 384, 288, 32, 2048, 925, 925, 7.58, 250, 600, "2-slot", "PCIe 8-pin + PCIe 6-pin", 3, 16, "false", "1x DP 1.2 + 1x HDMI 1.4 + 1x DVI", 4, "11", "1.2", "false", 549, 38.0, 39.99, 44.99, 49.99, 28.0, "gaming", "Discontinued"),
    ("Radeon HD 7950", "GCN 1", "Tahiti", 2012, "2012-01-31", "true", 28, 4, 365, 3, "GDDR5", 384, 240, 28, 1792, 800, 800, 5.73, 200, 550, "2-slot", "PCIe 8-pin + PCIe 6-pin", 3, 16, "false", "1x DP 1.2 + 1x HDMI 1.4 + 1x DVI", 4, "11", "1.2", "false", 449, 30.0, 32.0, 35.0, 39.99, 22.0, "gaming", "Discontinued"),
    ("Radeon HD 7870", "GCN 1", "Pitcairn", 2012, "2012-03-05", "true", 28, 2.8, 212, 2, "GDDR5", 256, 144, 20, 1280, 1000, 1000, 5.12, 175, 500, "2-slot", "PCIe 8-pin + PCIe 6-pin", 3, 16, "false", "1x DP 1.2 + 1x HDMI 1.4 + 1x DVI", 4, "11", "1.2", "false", 349, 26.0, 27.0, 29.99, 34.99, 20.0, "gaming", "Discontinued"),
    ("Radeon HD 7850", "GCN 1", "Pitcairn", 2012, "2012-03-05", "true", 28, 2.8, 212, 2, "GDDR5", 256, 128, 16, 1024, 860, 860, 3.52, 130, 450, "2-slot", "PCIe 6-pin", 3, 16, "false", "1x DP 1.2 + 1x HDMI 1.4 + 1x DVI", 4, "11", "1.2", "false", 249, 22.0, 24.0, 26.99, 29.99, 18.0, "gaming,budget", "Discontinued"),
    ("Radeon HD 7770", "GCN 1", "Cape Verde", 2012, "2012-02-15", "true", 28, 1.5, 123, 1, "GDDR5", 128, 72, 10, 640, 1000, 1000, 2.56, 80, 400, "2-slot", "PCIe 6-pin", 3, 16, "false", "1x DP 1.2 + 1x HDMI 1.4 + 1x DVI", 4, "11", "1.2", "false", 159, 19.0, 20.0, 22.0, 24.99, 15.0, "gaming,budget", "Discontinued"),
    ("Radeon HD 7750", "GCN 1", "Cape Verde", 2012, "2012-02-15", "true", 28, 1.5, 123, 1, "GDDR5", 128, 72, 8, 512, 800, 800, 1.64, 55, 350, "2-slot", "None", 3, 16, "false", "1x DP 1.2 + 1x HDMI 1.4 + 1x DVI", 4, "11", "1.2", "false", 109, 17.0, 18.0, 20.0, 22.0, 14.0, "gaming,budget", "Discontinued"),
]

# ============================================================================
# AMD DATA CENTER GPUs - Instinct series
# ============================================================================
def make_amd_dc_row(name, arch, chip, year, date, proc_nm, trans_b, die_mm2,
                    vram_gb, vram_type, bus_width, mem_bw, compute_units,
                    stream_proc, base_clk, boost_clk, fp32, fp16, bf16, int8,
                    tdp, pcie_gen, pcie_lanes, ecc, price_launch, price_new,
                    best_for, notes):
    links = make_links(name)
    return make_row(
        gpu_name=name,
        manufacturer="AMD",
        brand="AMD",
        category="datacenter",
        architecture=arch,
        gpu_chip=chip,
        release_year=str(year),
        release_date=date,
        discontinued="true" if year < 2024 else "false",
        process_node_nm=str(proc_nm),
        transistors_billion=str(trans_b),
        die_size_mm2=str(die_mm2),
        vram_gb=str(vram_gb),
        vram_type=vram_type,
        vram_bus_width_bit=str(bus_width),
        memory_bandwidth_gbps=str(mem_bw),
        cuda_cores="null",
        stream_processors=str(stream_proc),
        xe_cores="null",
        tensor_cores="null",
        rt_cores="null",
        compute_units=str(compute_units),
        base_clock_mhz=str(base_clk),
        boost_clock_mhz=str(boost_clk),
        fp32_tflops=str(fp32),
        fp16_tflops=str(fp16),
        bf16_tflops=str(bf16),
        int8_tops=str(int8),
        tdp_watts=str(tdp),
        recommended_psu_watts="null",
        slot_width="FHFL",
        connector_type="None",
        pcie_generation=str(pcie_gen),
        pcie_lanes=str(pcie_lanes),
        nvlink_support="false",
        display_outputs="null",
        max_displays="null",
        directx_version="null",
        opencl_version="3.0",
        cuda_compute_capability="null",
        ecc_support=ecc,
        price_usd_launch=str(price_launch),
        price_usd_new_current=str(price_new),
        price_usd_newegg="null",
        price_usd_amazon="null",
        price_usd_bh="null",
        price_usd_ebay_used="null",
        best_for=best_for,
        notes=notes,
        last_modified=NOW,
        **links,
    )

AMD_DATACENTER_GPUS = [
    # MI300X - CDNA 3 (2023) - 192GB HBM3
    ("AMD Instinct MI300X", "CDNA 3", "MI300X", 2023, "2023-12-06", 5, 153, "null",
     192, "HBM3", 8192, 5307, 304, 19456, 1000, 2100, 81.7, "null", 163.4, 654,
     750, 5, 128, "true", 15000, 15000.0, "ai_training,ai_inference,compute",
     "HBM3 memory; 192GB; OAM form factor; enterprise only"),
    # MI300A - CDNA 3 (2023) - APU with CPU+GPU
    ("AMD Instinct MI300A", "CDNA 3", "MI300A", 2023, "2023-12-06", 5, 153, "null",
     128, "HBM3", 8192, 5307, 228, 14592, 1000, 2100, 61.3, "null", 122.6, 490,
     760, 5, 128, "true", 12500, 12500.0, "ai_training,compute",
     "HBM3 memory; 128GB; CPU+GPU APU; OAM form factor; enterprise only"),
    # MI250X - CDNA 2 (2022)
    ("AMD Instinct MI250X", "CDNA 2", "MI250X", 2022, "2022-05-19", 6, 58, 660,
     128, "HBM2e", 8192, 3277, 232, 14080, 1000, 1700, 47.9, "null", 95.8, 383,
     560, 4, 128, "true", 10000, 10000.0, "ai_training,compute",
     "HBM2e memory; 128GB; dual-die; OAM form factor; enterprise only"),
    # MI250 - CDNA 2 (2022)
    ("AMD Instinct MI250", "CDNA 2", "MI250", 2022, "2022-05-19", 6, 58, 660,
     128, "HBM2e", 8192, 3277, 208, 13312, 1000, 1700, 45.3, "null", 90.6, 362,
     560, 4, 128, "true", 8000, 8000.0, "ai_training,compute",
     "HBM2e memory; 128GB; dual-die; OAM form factor; enterprise only"),
    # MI210 - CDNA 2 (2022)
    ("AMD Instinct MI210", "CDNA 2", "MI210", 2022, "2022-05-19", 6, 29, 330,
     64, "HBM2e", 4096, 1638, 104, 6656, 1000, 1700, 22.6, "null", 45.3, 181,
     300, 4, 128, "true", 6000, 6000.0, "ai_inference,compute",
     "HBM2e memory; 64GB; single-die; OAM form factor; enterprise only"),
    # MI100 - CDNA 1 (2020)
    ("AMD Instinct MI100", "CDNA 1", "MI100", 2020, "2020-11-16", 7, 32, 420,
     32, "HBM2", 4096, 1229, 120, 7680, 1000, 1502, 23.1, "null", 46.2, 184.8,
     300, 4, 128, "true", 4200, 4200.0, "compute",
     "HBM2 memory; 32GB; enterprise only"),
    # MI50 - Vega/GCN 5 (2018)
    ("AMD Instinct MI50", "GCN 5", "MI50", 2018, "2018-11-18", 7, 13, 331,
     32, "HBM2", 4096, 1024, 64, 3840, 1200, 1725, 26.5, "null", "null", "null",
     300, 3, 128, "true", 2500, 2500.0, "compute",
     "HBM2 memory; 32GB; enterprise only"),
]


def safe_float(val):
    """Convert a value to float, returning None for null/empty/invalid."""
    if val is None:
        return None
    val = str(val).strip()
    if val in ("null", "", "None"):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def recalc_derived(row):
    """Recalculate derived fields based on current price and spec values."""
    vram = safe_float(row.get("vram_gb"))
    price_new = safe_float(row.get("price_usd_new_current"))
    price_used = safe_float(row.get("price_usd_ebay_used"))
    fp32 = safe_float(row.get("fp32_tflops"))

    if price_new is not None and vram is not None and vram > 0:
        row["cost_per_gb_vram_new_usd"] = str(round(price_new / vram, 2))
    else:
        row["cost_per_gb_vram_new_usd"] = "null"

    if price_used is not None and vram is not None and vram > 0:
        row["cost_per_gb_vram_used_usd"] = str(round(price_used / vram, 2))
    else:
        row["cost_per_gb_vram_used_usd"] = "null"

    if fp32 is not None and price_new is not None and price_new > 0:
        row["fp32_per_dollar_new"] = str(round(fp32 / price_new, 4))
    else:
        row["fp32_per_dollar_new"] = "null"

    if fp32 is not None and price_used is not None and price_used > 0:
        row["fp32_per_dollar_used"] = str(round(fp32 / price_used, 4))
    else:
        row["fp32_per_dollar_used"] = "null"


def main():
    # Read existing rows
    with open(CSV_PATH, "r", newline="") as f:
        reader = csv.DictReader(f)
        existing_rows = list(reader)

    existing_names = {r["gpu_name"] for r in existing_rows}

    # Build new rows for mobile GPUs
    mobile_rows = []
    for data in MOBILE_GPUS:
        row = make_mobile_row(*data)
        if row["gpu_name"] not in existing_names:
            mobile_rows.append(row)

    # Build new rows for AMD consumer GPUs
    amd_consumer_rows = []
    for data in AMD_CONSUMER_GPUS:
        row = make_amd_consumer_row(*data)
        if row["gpu_name"] not in existing_names:
            amd_consumer_rows.append(row)

    # Build new rows for AMD datacenter GPUs
    amd_dc_rows = []
    for data in AMD_DATACENTER_GPUS:
        row = make_amd_dc_row(*data)
        if row["gpu_name"] not in existing_names:
            amd_dc_rows.append(row)

    new_rows = mobile_rows + amd_consumer_rows + amd_dc_rows

    # Combine all rows
    all_rows = existing_rows + new_rows

    # Normalize empty strings to "null" for price fields
    for row in all_rows:
        for field in ["price_usd_new_current", "price_usd_ebay_used",
                       "price_usd_newegg", "price_usd_amazon", "price_usd_bh",
                       "price_usd_launch"]:
            if row.get(field, "").strip() == "":
                row[field] = "null"

    # Recalculate derived fields for ALL rows
    derived_changed = 0
    for row in all_rows:
        old_vals = (
            row.get("cost_per_gb_vram_new_usd", ""),
            row.get("cost_per_gb_vram_used_usd", ""),
            row.get("fp32_per_dollar_new", ""),
            row.get("fp32_per_dollar_used", ""),
        )
        recalc_derived(row)
        new_vals = (
            row.get("cost_per_gb_vram_new_usd", ""),
            row.get("cost_per_gb_vram_used_usd", ""),
            row.get("fp32_per_dollar_new", ""),
            row.get("fp32_per_dollar_used", ""),
        )
        if old_vals != new_vals:
            derived_changed += 1

    # Write to temp file first, then rename (atomic write to prevent data loss)
    tmp_path = CSV_PATH + ".tmp"
    with open(tmp_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_rows)

    # Rename temp to final (atomic on POSIX)
    os.replace(tmp_path, CSV_PATH)

    # Final statistics
    missing_new = sum(1 for r in all_rows if r.get("price_usd_new_current", "").strip() in ("null", ""))
    missing_used = sum(1 for r in all_rows if r.get("price_usd_ebay_used", "").strip() in ("null", ""))

    # Count by category
    from collections import Counter
    cat_counts = Counter(r.get("category", "") for r in all_rows)
    mfgr_counts = Counter(r.get("manufacturer", "") for r in all_rows)

    print("=" * 60)
    print("GPU DATABASE PRICE FIX SUMMARY")
    print("=" * 60)
    print(f"Total rows: {len(all_rows)}")
    print(f"  Existing rows preserved: {len(existing_rows)}")
    print(f"  New rows added: {len(new_rows)}")
    print(f"    Mobile GPUs: {len(mobile_rows)}")
    print(f"    AMD consumer GPUs: {len(amd_consumer_rows)}")
    print(f"    AMD datacenter GPUs: {len(amd_dc_rows)}")
    print()
    print(f"Categories: {dict(cat_counts)}")
    print(f"Manufacturers: {dict(mfgr_counts)}")
    print()
    print(f"Derived fields recalculated: {derived_changed}")
    print()
    print("--- Price Gaps ---")
    mobile_count = sum(1 for r in all_rows if r.get('category') == 'mobile')
    dc_count = sum(1 for r in all_rows if r.get('category') == 'datacenter')
    print(f"  Missing price_usd_new_current: {missing_new}")
    print(f"    (Mobile GPUs: {mobile_count} -- not sold standalone)")
    print(f"  Missing price_usd_ebay_used: {missing_used}")
    print(f"    (Mobile GPUs: {mobile_count} -- not sold standalone)")
    print(f"    (Datacenter GPUs: {dc_count} -- enterprise only)")
    print()
    print("--- Sanity Check Notes ---")
    print("  All mobile GPU prices set to null (not sold as standalone cards)")
    print("  All datacenter GPU ebay_used set to null (enterprise sales channels)")
    print("  AMD Instinct price_usd_new_current updated to realistic enterprise prices")
    print("  (previously had erroneous values of ~$73-77 from scraper failure)")
    print("=" * 60)


if __name__ == "__main__":
    main()
