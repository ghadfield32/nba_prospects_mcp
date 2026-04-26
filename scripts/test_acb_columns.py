#!/usr/bin/env python
"""Debug ACB box score column structure."""

import sys

sys.path.insert(0, "src")

import pandas as pd

game_id = "17745"
url = f"https://www.acb.com/partido/estadisticas/id/{game_id}"
print(f"Fetching: {url}\n")

tables = pd.read_html(url, encoding="utf-8")
print(f"Found {len(tables)} tables\n")

# Look at table 1 structure
table = tables[1]
print(f"Original columns: {list(table.columns)}")
print()

# Get the first data row (not header)
first_row = table.iloc[0]
print("First row values by column index:")
for i, val in enumerate(first_row):
    print(f"  [{i:2}] = {repr(val)}")

# Try parsing without flattening first
print("\n\nRaw table head:")
print(table.head())
