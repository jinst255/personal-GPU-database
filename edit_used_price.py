#!/usr/bin/env python3
"""Simple interactive tool to edit `price_usd_ebay_used` by card number."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path


CSV_PATH = Path("gpu_database.csv")
PRICE_COLUMN = "price_usd_ebay_used"
NAME_COLUMN = "gpu_name"
LAST_MODIFIED_COLUMN = "last_modified"


def load_rows(csv_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row.")
        return reader.fieldnames, list(reader)


def save_rows(csv_path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_price_input(raw: str) -> str:
    text = raw.strip()
    if text == "":
        return ""
    value = float(text)
    if value < 0:
        raise ValueError("Price must be >= 0.")
    return str(round(value, 2))


def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH.resolve()}")

    fieldnames, rows = load_rows(CSV_PATH)

    for required in (NAME_COLUMN, PRICE_COLUMN):
        if required not in fieldnames:
            raise KeyError(f"Missing required column: {required}")

    print("\nCards:")
    for i, row in enumerate(rows, start=1):
        name = (row.get(NAME_COLUMN) or "").strip() or "<unnamed>"
        used_price = (row.get(PRICE_COLUMN) or "").strip() or "<empty>"
        print(f"{i:>4}. {name} | used price: {used_price}")

    while True:
        choice = input(f"\nEnter card number to edit (1-{len(rows)}), or q to quit: ").strip()
        if choice.lower() == "q":
            print("No changes made.")
            return
        if not choice.isdigit():
            print("Please enter a valid number.")
            continue

        index = int(choice)
        if not (1 <= index <= len(rows)):
            print("Number out of range.")
            continue
        break

    row = rows[index - 1]
    gpu_name = (row.get(NAME_COLUMN) or "").strip() or "<unnamed>"
    current_price = (row.get(PRICE_COLUMN) or "").strip() or "<empty>"

    print(f"\nSelected: {gpu_name}")
    print(f"Current used price: {current_price}")

    while True:
        new_raw = input("Enter new used price (blank to clear, q to cancel): ").strip()
        if new_raw.lower() == "q":
            print("Cancelled. No changes made.")
            return
        try:
            new_value = parse_price_input(new_raw)
            break
        except ValueError as exc:
            print(f"Invalid value: {exc}")

    row[PRICE_COLUMN] = new_value
    if LAST_MODIFIED_COLUMN in fieldnames:
        row[LAST_MODIFIED_COLUMN] = datetime.now().strftime("%Y-%m-%dT%H:%M")

    save_rows(CSV_PATH, fieldnames, rows)

    shown_new = new_value if new_value else "<empty>"
    print(f"Updated card #{index}: {gpu_name}")
    print(f"Old used price: {current_price}")
    print(f"New used price: {shown_new}")
    print(f"Saved to: {CSV_PATH.resolve()}")


if __name__ == "__main__":
    main()
