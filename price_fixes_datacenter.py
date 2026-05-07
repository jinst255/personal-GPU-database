#!/usr/bin/env python3
"""
Price fixes for datacenter and professional GPUs in the GPU database.

PROBLEM: A price scraper put garbage prices on datacenter and professional cards.
- AMD Instinct cards all had garbage new prices (~$73-77 instead of thousands)
- Radeon Pro cards all had wrong new prices (~$329-331 instead of thousands)

This script:
1. Adds missing datacenter (AMD Instinct) and professional (Radeon Pro) cards
   if they don't exist in the CSV, with correct pricing
2. Fixes the wrong price_usd_new_current values for any already-present cards
3. Sets price_usd_launch (MSRP) for cards where it's missing
4. Fixes retailer prices (newegg, amazon, bh) that are clearly garbage
5. Sets appropriate ebay_used values (null for datacenter, real for professional)
6. Recalculates derived fields for all updated rows
7. Updates last_modified timestamp

PRICING SOURCES:
- Radeon Pro launch MSRPs: Wikipedia "Radeon Pro" article (verified)
  W7900: $3,999 (full-height), W7900 Dual Slot: $3,499
  W7800: $2,499, W6800: $2,249, W6600: $649
- Radeon Pro current pricing: Newegg retail data (verified May 2026)
  W7900: ~$3,499 (Newegg), W7800: ~$2,499 (B&H), W6800: ~$2,249, W6600: ~$469
- AMD Instinct pricing: Enterprise/OEM channel commodity pricing
  These cards are not sold at retail; prices reflect OEM/channel costs.
- Laptop GPUs: No MSRP (OEM-only), kept as null
"""

import csv
import os
from datetime import datetime

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gpu_database.csv")


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

    # cost_per_gb_vram_new_usd
    if price_new is not None and vram is not None and vram > 0:
        row["cost_per_gb_vram_new_usd"] = str(round(price_new / vram, 2))
    else:
        row["cost_per_gb_vram_new_usd"] = "null"

    # cost_per_gb_vram_used_usd
    if price_used is not None and vram is not None and vram > 0:
        row["cost_per_gb_vram_used_usd"] = str(round(price_used / vram, 2))
    else:
        row["cost_per_gb_vram_used_usd"] = "null"

    # fp32_per_dollar_new
    if fp32 is not None and price_new is not None and price_new > 0:
        row["fp32_per_dollar_new"] = str(round(fp32 / price_new, 4))
    else:
        row["fp32_per_dollar_new"] = "null"

    # fp32_per_dollar_used
    if fp32 is not None and price_used is not None and price_used > 0:
        row["fp32_per_dollar_used"] = str(round(fp32 / price_used, 4))
    else:
        row["fp32_per_dollar_used"] = "null"


# =============================================================================
# COMPLETE ROW DATA FOR CARDS TO ADD/FIX
# =============================================================================
# Each entry contains the full spec data plus corrected pricing.
# Specs sourced from Wikipedia, AMD product pages, and TechPowerUp.

NEW_CARDS = [
    # --- AMD Instinct datacenter GPUs ---
    {
        "gpu_name": "AMD Instinct MI300X",
        "manufacturer": "AMD",
        "brand": "Instinct",
        "category": "datacenter",
        "architecture": "CDNA 3",
        "gpu_chip": "Aqua Vanjaram",
        "release_year": "2023",
        "release_date": "2023-12-06",
        "discontinued": "false",
        "process_node_nm": "5",
        "transistors_billion": "153",
        "die_size_mm2": "null",
        "vram_gb": "192",
        "vram_type": "HBM3",
        "vram_bus_width_bit": "8192",
        "memory_bandwidth_gbps": "5300",
        "cuda_cores": "null",
        "stream_processors": "19456",
        "xe_cores": "null",
        "tensor_cores": "null",
        "rt_cores": "null",
        "compute_units": "304",
        "base_clock_mhz": "2100",
        "boost_clock_mhz": "2100",
        "fp32_tflops": "163.4",
        "fp16_tflops": "1307.4",
        "bf16_tflops": "null",
        "int8_tops": "2614.9",
        "tdp_watts": "750",
        "recommended_psu_watts": "null",
        "slot_width": "FHFL",
        "connector_type": "null",
        "pcie_generation": "5",
        "pcie_lanes": "16",
        "nvlink_support": "false",
        "display_outputs": "null",
        "max_displays": "0",
        "directx_version": "null",
        "opencl_version": "null",
        "cuda_compute_capability": "null",
        "ecc_support": "true",
        "price_usd_launch": "15000",
        "price_usd_new_current": "15000",
        "price_usd_newegg": "null",
        "price_usd_amazon": "null",
        "price_usd_bh": "null",
        "price_usd_ebay_used": "null",
        "link_newegg": "null",
        "link_amazon": "null",
        "link_bh": "null",
        "link_ebay": "null",
        "best_for": "ai_training,ai_inference,compute,server",
        "notes": "Server/HPC accelerator",
    },
    {
        "gpu_name": "AMD Instinct MI300A",
        "manufacturer": "AMD",
        "brand": "Instinct",
        "category": "datacenter",
        "architecture": "CDNA 3",
        "gpu_chip": "Antares",
        "release_year": "2023",
        "release_date": "2023-12-06",
        "discontinued": "APU with 24 Zen 4 CPU cores",
        "process_node_nm": "5",
        "transistors_billion": "146",
        "die_size_mm2": "null",
        "vram_gb": "128",
        "vram_type": "HBM3",
        "vram_bus_width_bit": "8192",
        "memory_bandwidth_gbps": "5300",
        "cuda_cores": "null",
        "stream_processors": "14592",
        "xe_cores": "null",
        "tensor_cores": "null",
        "rt_cores": "null",
        "compute_units": "228",
        "base_clock_mhz": "2100",
        "boost_clock_mhz": "2100",
        "fp32_tflops": "122.6",
        "fp16_tflops": "980.6",
        "bf16_tflops": "null",
        "int8_tops": "1961.2",
        "tdp_watts": "550",
        "recommended_psu_watts": "null",
        "slot_width": "FHFL",
        "connector_type": "null",
        "pcie_generation": "5",
        "pcie_lanes": "16",
        "nvlink_support": "false",
        "display_outputs": "null",
        "max_displays": "0",
        "directx_version": "null",
        "opencl_version": "null",
        "cuda_compute_capability": "null",
        "ecc_support": "true",
        "price_usd_launch": "12500",
        "price_usd_new_current": "12500",
        "price_usd_newegg": "null",
        "price_usd_amazon": "null",
        "price_usd_bh": "null",
        "price_usd_ebay_used": "null",
        "link_newegg": "null",
        "link_amazon": "null",
        "link_bh": "null",
        "link_ebay": "null",
        "best_for": "ai_training,ai_inference,compute,server",
        "notes": "Server/HPC accelerator",
    },
    {
        "gpu_name": "AMD Instinct MI250X",
        "manufacturer": "AMD",
        "brand": "Instinct",
        "category": "datacenter",
        "architecture": "CDNA 2",
        "gpu_chip": "Aldebaran",
        "release_year": "2021",
        "release_date": "2021-11-08",
        "discontinued": "false",
        "process_node_nm": "6",
        "transistors_billion": "58.2",
        "die_size_mm2": "null",
        "vram_gb": "128",
        "vram_type": "HBM2e",
        "vram_bus_width_bit": "8192",
        "memory_bandwidth_gbps": "3277",
        "cuda_cores": "null",
        "stream_processors": "14080",
        "xe_cores": "null",
        "tensor_cores": "null",
        "rt_cores": "null",
        "compute_units": "220",
        "base_clock_mhz": "1000",
        "boost_clock_mhz": "1700",
        "fp32_tflops": "47.87",
        "fp16_tflops": "383",
        "bf16_tflops": "null",
        "int8_tops": "383",
        "tdp_watts": "560",
        "recommended_psu_watts": "null",
        "slot_width": "FHFL",
        "connector_type": "null",
        "pcie_generation": "4",
        "pcie_lanes": "16",
        "nvlink_support": "false",
        "display_outputs": "null",
        "max_displays": "0",
        "directx_version": "null",
        "opencl_version": "null",
        "cuda_compute_capability": "null",
        "ecc_support": "true",
        "price_usd_launch": "15000",
        "price_usd_new_current": "12000",
        "price_usd_newegg": "null",
        "price_usd_amazon": "null",
        "price_usd_bh": "null",
        "price_usd_ebay_used": "null",
        "link_newegg": "null",
        "link_amazon": "null",
        "link_bh": "null",
        "link_ebay": "null",
        "best_for": "ai_training,ai_inference,compute,server",
        "notes": "Server/HPC accelerator",
    },
    {
        "gpu_name": "AMD Instinct MI250",
        "manufacturer": "AMD",
        "brand": "Instinct",
        "category": "datacenter",
        "architecture": "CDNA 2",
        "gpu_chip": "Aldebaran",
        "release_year": "2021",
        "release_date": "2021-11-08",
        "discontinued": "false",
        "process_node_nm": "6",
        "transistors_billion": "58.2",
        "die_size_mm2": "null",
        "vram_gb": "128",
        "vram_type": "HBM2e",
        "vram_bus_width_bit": "8192",
        "memory_bandwidth_gbps": "3277",
        "cuda_cores": "null",
        "stream_processors": "13312",
        "xe_cores": "null",
        "tensor_cores": "null",
        "rt_cores": "null",
        "compute_units": "208",
        "base_clock_mhz": "1000",
        "boost_clock_mhz": "1700",
        "fp32_tflops": "45.26",
        "fp16_tflops": "362.1",
        "bf16_tflops": "null",
        "int8_tops": "362.1",
        "tdp_watts": "500",
        "recommended_psu_watts": "null",
        "slot_width": "FHFL",
        "connector_type": "null",
        "pcie_generation": "4",
        "pcie_lanes": "16",
        "nvlink_support": "false",
        "display_outputs": "null",
        "max_displays": "0",
        "directx_version": "null",
        "opencl_version": "null",
        "cuda_compute_capability": "null",
        "ecc_support": "true",
        "price_usd_launch": "12000",
        "price_usd_new_current": "10000",
        "price_usd_newegg": "null",
        "price_usd_amazon": "null",
        "price_usd_bh": "null",
        "price_usd_ebay_used": "null",
        "link_newegg": "null",
        "link_amazon": "null",
        "link_bh": "null",
        "link_ebay": "null",
        "best_for": "ai_training,ai_inference,compute,server",
        "notes": "Server/HPC accelerator",
    },
    {
        "gpu_name": "AMD Instinct MI210",
        "manufacturer": "AMD",
        "brand": "Instinct",
        "category": "datacenter",
        "architecture": "CDNA 2",
        "gpu_chip": "Aldebaran",
        "release_year": "2022",
        "release_date": "2022-03-22",
        "discontinued": "false",
        "process_node_nm": "6",
        "transistors_billion": "28",
        "die_size_mm2": "null",
        "vram_gb": "64",
        "vram_type": "HBM2e",
        "vram_bus_width_bit": "4096",
        "memory_bandwidth_gbps": "1638",
        "cuda_cores": "null",
        "stream_processors": "6656",
        "xe_cores": "null",
        "tensor_cores": "null",
        "rt_cores": "null",
        "compute_units": "104",
        "base_clock_mhz": "1000",
        "boost_clock_mhz": "1700",
        "fp32_tflops": "22.63",
        "fp16_tflops": "181",
        "bf16_tflops": "null",
        "int8_tops": "181",
        "tdp_watts": "300",
        "recommended_psu_watts": "null",
        "slot_width": "FHFL",
        "connector_type": "null",
        "pcie_generation": "4",
        "pcie_lanes": "16",
        "nvlink_support": "false",
        "display_outputs": "null",
        "max_displays": "0",
        "directx_version": "null",
        "opencl_version": "null",
        "cuda_compute_capability": "null",
        "ecc_support": "true",
        "price_usd_launch": "6000",
        "price_usd_new_current": "6000",
        "price_usd_newegg": "null",
        "price_usd_amazon": "null",
        "price_usd_bh": "null",
        "price_usd_ebay_used": "null",
        "link_newegg": "null",
        "link_amazon": "null",
        "link_bh": "null",
        "link_ebay": "null",
        "best_for": "ai_inference,compute,server",
        "notes": "Server/HPC accelerator",
    },
    {
        "gpu_name": "AMD Instinct MI100",
        "manufacturer": "AMD",
        "brand": "Instinct",
        "category": "datacenter",
        "architecture": "CDNA 1",
        "gpu_chip": "Arcturus",
        "release_year": "2020",
        "release_date": "2020-11-16",
        "discontinued": "true",
        "process_node_nm": "7",
        "transistors_billion": "25.6",
        "die_size_mm2": "null",
        "vram_gb": "32",
        "vram_type": "HBM2",
        "vram_bus_width_bit": "4096",
        "memory_bandwidth_gbps": "1229",
        "cuda_cores": "null",
        "stream_processors": "7680",
        "xe_cores": "null",
        "tensor_cores": "null",
        "rt_cores": "null",
        "compute_units": "120",
        "base_clock_mhz": "1000",
        "boost_clock_mhz": "1502",
        "fp32_tflops": "23.07",
        "fp16_tflops": "184.6",
        "bf16_tflops": "null",
        "int8_tops": "184.6",
        "tdp_watts": "300",
        "recommended_psu_watts": "null",
        "slot_width": "FHFL",
        "connector_type": "null",
        "pcie_generation": "4",
        "pcie_lanes": "16",
        "nvlink_support": "false",
        "display_outputs": "null",
        "max_displays": "0",
        "directx_version": "null",
        "opencl_version": "null",
        "cuda_compute_capability": "null",
        "ecc_support": "true",
        "price_usd_launch": "5000",
        "price_usd_new_current": "3800",
        "price_usd_newegg": "null",
        "price_usd_amazon": "null",
        "price_usd_bh": "null",
        "price_usd_ebay_used": "null",
        "link_newegg": "null",
        "link_amazon": "null",
        "link_bh": "null",
        "link_ebay": "null",
        "best_for": "ai_inference,compute,server",
        "notes": "Server/HPC accelerator; Discontinued",
    },
    {
        "gpu_name": "AMD Instinct MI50",
        "manufacturer": "AMD",
        "brand": "Instinct",
        "category": "datacenter",
        "architecture": "GCN 5",
        "gpu_chip": "Vega 20",
        "release_year": "2018",
        "release_date": "2018-11-18",
        "discontinued": "true",
        "process_node_nm": "7",
        "transistors_billion": "13.2",
        "die_size_mm2": "null",
        "vram_gb": "32",
        "vram_type": "HBM2",
        "vram_bus_width_bit": "4096",
        "memory_bandwidth_gbps": "1024",
        "cuda_cores": "null",
        "stream_processors": "4096",
        "xe_cores": "null",
        "tensor_cores": "null",
        "rt_cores": "null",
        "compute_units": "64",
        "base_clock_mhz": "1450",
        "boost_clock_mhz": "1725",
        "fp32_tflops": "14.75",
        "fp16_tflops": "26.5",
        "bf16_tflops": "null",
        "int8_tops": "53",
        "tdp_watts": "300",
        "recommended_psu_watts": "null",
        "slot_width": "FHFL",
        "connector_type": "null",
        "pcie_generation": "4",
        "pcie_lanes": "16",
        "nvlink_support": "false",
        "display_outputs": "null",
        "max_displays": "0",
        "directx_version": "null",
        "opencl_version": "null",
        "cuda_compute_capability": "null",
        "ecc_support": "true",
        "price_usd_launch": "5000",
        "price_usd_new_current": "3000",
        "price_usd_newegg": "null",
        "price_usd_amazon": "null",
        "price_usd_bh": "null",
        "price_usd_ebay_used": "null",
        "link_newegg": "null",
        "link_amazon": "null",
        "link_bh": "null",
        "link_ebay": "null",
        "best_for": "compute,server",
        "notes": "Server/HPC accelerator; First 7nm GPU; Discontinued",
    },
    # --- Radeon Pro professional workstation GPUs ---
    {
        "gpu_name": "Radeon Pro W7900",
        "manufacturer": "AMD",
        "brand": "Radeon Pro",
        "category": "professional",
        "architecture": "RDNA 3",
        "gpu_chip": "Navi 31",
        "release_year": "2023",
        "release_date": "2023-06-13",
        "discontinued": "false",
        "process_node_nm": "5",
        "transistors_billion": "57.7",
        "die_size_mm2": "null",
        "vram_gb": "48",
        "vram_type": "GDDR6",
        "vram_bus_width_bit": "384",
        "memory_bandwidth_gbps": "864",
        "cuda_cores": "null",
        "stream_processors": "6144",
        "xe_cores": "null",
        "tensor_cores": "null",
        "rt_cores": "null",
        "compute_units": "96",
        "base_clock_mhz": "1850",
        "boost_clock_mhz": "2100",
        "fp32_tflops": "96.77",
        "fp16_tflops": "null",
        "bf16_tflops": "null",
        "int8_tops": "null",
        "tdp_watts": "295",
        "recommended_psu_watts": "750",
        "slot_width": "2-slot",
        "connector_type": "16-pin",
        "pcie_generation": "4",
        "pcie_lanes": "16",
        "nvlink_support": "false",
        "display_outputs": "3x DP 2.1 + 1x USB-C",
        "max_displays": "4",
        "directx_version": "12 Ultimate",
        "opencl_version": "2.1",
        "cuda_compute_capability": "null",
        "ecc_support": "true",
        "price_usd_launch": "3999",
        "price_usd_new_current": "3499",
        "price_usd_newegg": "3499",
        "price_usd_amazon": "null",
        "price_usd_bh": "3499",
        "price_usd_ebay_used": "1900",
        "link_newegg": "https://www.newegg.com/p/pl?d=Radeon%20Pro%20W7900",
        "link_amazon": "https://www.amazon.com/s?k=Radeon%20Pro%20W7900",
        "link_bh": "https://www.bhphotovideo.com/c/search?q=Radeon%20Pro%20W7900",
        "link_ebay": "https://www.ebay.com/sch/i.html?_nkw=Radeon%20Pro%20W7900%20GPU&LH_Sold=1",
        "best_for": "rendering,workstation,ai_inference",
        "notes": "Workstation GPU",
    },
    {
        "gpu_name": "Radeon Pro W7800",
        "manufacturer": "AMD",
        "brand": "Radeon Pro",
        "category": "professional",
        "architecture": "RDNA 3",
        "gpu_chip": "Navi 32",
        "release_year": "2023",
        "release_date": "2023-05-23",
        "discontinued": "false",
        "process_node_nm": "5",
        "transistors_billion": "28.1",
        "die_size_mm2": "null",
        "vram_gb": "32",
        "vram_type": "GDDR6",
        "vram_bus_width_bit": "256",
        "memory_bandwidth_gbps": "576",
        "cuda_cores": "null",
        "stream_processors": "3840",
        "xe_cores": "null",
        "tensor_cores": "null",
        "rt_cores": "null",
        "compute_units": "60",
        "base_clock_mhz": "1850",
        "boost_clock_mhz": "2495",
        "fp32_tflops": "48.04",
        "fp16_tflops": "null",
        "bf16_tflops": "null",
        "int8_tops": "null",
        "tdp_watts": "260",
        "recommended_psu_watts": "650",
        "slot_width": "2-slot",
        "connector_type": "16-pin",
        "pcie_generation": "4",
        "pcie_lanes": "16",
        "nvlink_support": "false",
        "display_outputs": "3x DP 2.1 + 1x USB-C",
        "max_displays": "4",
        "directx_version": "12 Ultimate",
        "opencl_version": "2.1",
        "cuda_compute_capability": "null",
        "ecc_support": "true",
        "price_usd_launch": "2499",
        "price_usd_new_current": "2499",
        "price_usd_newegg": "2499",
        "price_usd_amazon": "null",
        "price_usd_bh": "2499",
        "price_usd_ebay_used": "1650",
        "link_newegg": "https://www.newegg.com/p/pl?d=Radeon%20Pro%20W7800",
        "link_amazon": "https://www.amazon.com/s?k=Radeon%20Pro%20W7800",
        "link_bh": "https://www.bhphotovideo.com/c/search?q=Radeon%20Pro%20W7800",
        "link_ebay": "https://www.ebay.com/sch/i.html?_nkw=Radeon%20Pro%20W7800%20GPU&LH_Sold=1",
        "best_for": "rendering,workstation",
        "notes": "Workstation GPU",
    },
    {
        "gpu_name": "Radeon Pro W6800",
        "manufacturer": "AMD",
        "brand": "Radeon Pro",
        "category": "professional",
        "architecture": "RDNA 2",
        "gpu_chip": "Navi 21",
        "release_year": "2021",
        "release_date": "2021-06-08",
        "discontinued": "null",
        "process_node_nm": "7",
        "transistors_billion": "26.8",
        "die_size_mm2": "null",
        "vram_gb": "32",
        "vram_type": "GDDR6",
        "vram_bus_width_bit": "256",
        "memory_bandwidth_gbps": "512",
        "cuda_cores": "null",
        "stream_processors": "3840",
        "xe_cores": "null",
        "tensor_cores": "null",
        "rt_cores": "null",
        "compute_units": "60",
        "base_clock_mhz": "2075",
        "boost_clock_mhz": "2325",
        "fp32_tflops": "35.74",
        "fp16_tflops": "null",
        "bf16_tflops": "null",
        "int8_tops": "null",
        "tdp_watts": "250",
        "recommended_psu_watts": "650",
        "slot_width": "2-slot",
        "connector_type": "PCIe 8-pin + PCIe 6-pin",
        "pcie_generation": "4",
        "pcie_lanes": "16",
        "nvlink_support": "false",
        "display_outputs": "3x DP 1.4 + 1x USB-C",
        "max_displays": "4",
        "directx_version": "12 Ultimate",
        "opencl_version": "2.1",
        "cuda_compute_capability": "null",
        "ecc_support": "true",
        "price_usd_launch": "2249",
        "price_usd_new_current": "2249",
        "price_usd_newegg": "null",
        "price_usd_amazon": "null",
        "price_usd_bh": "2249",
        "price_usd_ebay_used": "1630",
        "link_newegg": "https://www.newegg.com/p/pl?d=Radeon%20Pro%20W6800",
        "link_amazon": "https://www.amazon.com/s?k=Radeon%20Pro%20W6800",
        "link_bh": "https://www.bhphotovideo.com/c/search?q=Radeon%20Pro%20W6800",
        "link_ebay": "https://www.ebay.com/sch/i.html?_nkw=Radeon%20Pro%20W6800%20GPU&LH_Sold=1",
        "best_for": "rendering,workstation",
        "notes": "Workstation GPU",
    },
    {
        "gpu_name": "Radeon Pro W6600",
        "manufacturer": "AMD",
        "brand": "Radeon Pro",
        "category": "professional",
        "architecture": "RDNA 2",
        "gpu_chip": "Navi 23",
        "release_year": "2021",
        "release_date": "2021-11-16",
        "discontinued": "null",
        "process_node_nm": "7",
        "transistors_billion": "11.06",
        "die_size_mm2": "null",
        "vram_gb": "8",
        "vram_type": "GDDR6",
        "vram_bus_width_bit": "128",
        "memory_bandwidth_gbps": "256",
        "cuda_cores": "null",
        "stream_processors": "1792",
        "xe_cores": "null",
        "tensor_cores": "null",
        "rt_cores": "null",
        "compute_units": "28",
        "base_clock_mhz": "2331",
        "boost_clock_mhz": "2620",
        "fp32_tflops": "9.4",
        "fp16_tflops": "null",
        "bf16_tflops": "null",
        "int8_tops": "null",
        "tdp_watts": "100",
        "recommended_psu_watts": "350",
        "slot_width": "2-slot",
        "connector_type": "PCIe 6-pin",
        "pcie_generation": "4",
        "pcie_lanes": "16",
        "nvlink_support": "false",
        "display_outputs": "3x DP 1.4 + 1x USB-C",
        "max_displays": "4",
        "directx_version": "12 Ultimate",
        "opencl_version": "2.1",
        "cuda_compute_capability": "null",
        "ecc_support": "true",
        "price_usd_launch": "649",
        "price_usd_new_current": "469",
        "price_usd_newegg": "469",
        "price_usd_amazon": "null",
        "price_usd_bh": "null",
        "price_usd_ebay_used": "165",
        "link_newegg": "https://www.newegg.com/p/pl?d=Radeon%20Pro%20W6600",
        "link_amazon": "https://www.amazon.com/s?k=Radeon%20Pro%20W6600",
        "link_bh": "https://www.bhphotovideo.com/c/search?q=Radeon%20Pro%20W6600",
        "link_ebay": "https://www.ebay.com/sch/i.html?_nkw=Radeon%20Pro%20W6600%20GPU&LH_Sold=1",
        "best_for": "rendering,workstation,budget",
        "notes": "Workstation GPU",
    },
]


def main():
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")

    # Check if file exists
    if not os.path.exists(CSV_PATH):
        print(f"ERROR: CSV file not found at {CSV_PATH}")
        return

    with open(CSV_PATH, "r", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    print("=" * 70)
    print("GPU DATABASE DATACENTER/PROFESSIONAL PRICE FIX")
    print("=" * 70)
    print(f"Total rows in CSV before: {len(rows)}")
    print()

    # Check which target cards exist in the CSV
    existing_names = {row["gpu_name"] for row in rows}
    target_names = {card["gpu_name"] for card in NEW_CARDS}
    found_targets = existing_names & target_names
    missing_targets = target_names - existing_names

    # Track changes
    price_fixes_applied = 0
    launch_prices_filled = 0
    cards_added = 0
    derived_recalculated = 0
    rows_changed = 0

    # --- Step 1: Fix prices for cards that already exist ---
    for row in rows:
        name = row["gpu_name"]
        changed = False

        if name in target_names:
            # Find the correct data for this card
            card_data = None
            for card in NEW_CARDS:
                if card["gpu_name"] == name:
                    card_data = card
                    break

            if card_data:
                for field, value in card_data.items():
                    if field == "gpu_name":
                        continue
                    old_val = row.get(field, "").strip()
                    if old_val != value:
                        action = "FIXED" if old_val not in ("null", "") else "SET"
                        print(f"  {action} {name}: {field} = {value} (was: {old_val})")
                        row[field] = value
                        changed = True
                        price_fixes_applied += 1

                # Check if launch price was filled
                if card_data.get("price_usd_launch") and row.get("price_usd_launch", "").strip() == "null":
                    launch_prices_filled += 1

        # Recalculate derived fields for ALL rows
        old_derived = (
            row.get("cost_per_gb_vram_new_usd", ""),
            row.get("cost_per_gb_vram_used_usd", ""),
            row.get("fp32_per_dollar_new", ""),
            row.get("fp32_per_dollar_used", ""),
        )
        recalc_derived(row)
        new_derived = (
            row.get("cost_per_gb_vram_new_usd", ""),
            row.get("cost_per_gb_vram_used_usd", ""),
            row.get("fp32_per_dollar_new", ""),
            row.get("fp32_per_dollar_used", ""),
        )
        if old_derived != new_derived:
            derived_recalculated += 1
            changed = True

        if changed:
            row["last_modified"] = now
            rows_changed += 1

    # --- Step 2: Add missing cards ---
    if missing_targets:
        print()
        print(f"ADDING {len(missing_targets)} missing cards to the database:")
        print()

        # Determine insertion order: add professional cards, then datacenter
        cards_to_add = []
        for card in NEW_CARDS:
            if card["gpu_name"] in missing_targets:
                cards_to_add.append(card)

        for card_data in cards_to_add:
            # Create a full row with all fieldnames, defaulting to "null"
            new_row = {}
            for field in fieldnames:
                new_row[field] = card_data.get(field, "null")

            # Calculate derived fields
            recalc_derived(new_row)
            new_row["last_modified"] = now

            rows.append(new_row)
            cards_added += 1
            launch_prices_filled += 1
            derived_recalculated += 1
            print(f"  ADDED {card_data['gpu_name']}")

            vram = card_data.get("vram_gb", "null")
            fp32 = card_data.get("fp32_tflops", "null")
            price_new = card_data.get("price_usd_new_current", "null")
            price_launch = card_data.get("price_usd_launch", "null")
            print(f"    vram={vram}GB, fp32={fp32} TFLOPS, launch=${price_launch}, new=${price_new}")
            print(f"    cost/gb_new={new_row['cost_per_gb_vram_new_usd']}, "
                  f"fp32/$_new={new_row['fp32_per_dollar_new']}")

    # Write back
    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Print summary
    print()
    print("-" * 70)
    print("SUMMARY")
    print("-" * 70)
    print(f"Total rows before: {len(rows) - cards_added}")
    print(f"Total rows after:  {len(rows)}")
    print()
    print(f"Target cards already in CSV: {len(found_targets)}")
    print(f"Cards added: {cards_added}")
    print(f"Price field fixes applied: {price_fixes_applied}")
    print(f"Launch MSRPs filled: {launch_prices_filled}")
    print(f"Derived fields recalculated: {derived_recalculated}")
    print(f"Total rows changed: {rows_changed + cards_added}")
    print()

    # Print final prices for all target cards
    print("-" * 70)
    print("FINAL PRICES FOR ALL DATACENTER/PROFESSIONAL CARDS")
    print("-" * 70)
    for row in rows:
        if row["gpu_name"] in target_names:
            print(f"  {row['gpu_name']}:")
            print(f"    launch=${row['price_usd_launch']}, "
                  f"new=${row['price_usd_new_current']}, "
                  f"ebay_used={row['price_usd_ebay_used']}")
            print(f"    cost/gb_new={row['cost_per_gb_vram_new_usd']}, "
                  f"cost/gb_used={row['cost_per_gb_vram_used_usd']}")
            print(f"    fp32/$_new={row['fp32_per_dollar_new']}, "
                  f"fp32/$_used={row['fp32_per_dollar_used']}")
            print()

    print("=" * 70)


if __name__ == "__main__":
    main()
