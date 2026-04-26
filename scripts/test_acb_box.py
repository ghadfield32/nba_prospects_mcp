#!/usr/bin/env python
"""Test ACB box score fetch."""

import pandas as pd

game_id = "17745"  # A 2017-18 game: Barcelona vs Kirolbet
url = f"https://www.acb.com/partido/estadisticas/id/{game_id}"
print(f"Fetching: {url}")

try:
    tables = pd.read_html(url, encoding="utf-8")
    print(f"Found {len(tables)} tables")

    # Look at table 1 (first team's player stats)
    table = tables[1]
    print(f"\nTable 1 columns: {list(table.columns)}")

    # Flatten multi-level columns
    if isinstance(table.columns, pd.MultiIndex):
        table.columns = [f"{a}_{b}" if b != a else a for a, b in table.columns]

    print(f"\nFlattened columns: {list(table.columns)}")
    print("\nFirst 5 rows:")
    print(table.head())

    # Try to identify key columns
    print("\nColumn value samples:")
    for col in table.columns[:15]:
        print(f"  {col}: {table[col].iloc[0]}")

except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()
