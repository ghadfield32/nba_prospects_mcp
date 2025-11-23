#!/usr/bin/env python3
"""Check Espoirs season labeling vs actual game dates"""

from datetime import date

import pandas as pd

df = pd.read_parquet("data/raw/lnb/lnb_game_index.parquet")

print("=" * 70)
print("  ESPOIRS SEASON LABELING CHECK")
print("=" * 70)

for comp in ["Espoirs ELITE", "Espoirs PROB"]:
    espoirs = df[df["competition"] == comp]

    if len(espoirs) == 0:
        continue

    print(f"\n{comp}:")
    print(f"Total games: {len(espoirs)}")
    print("\nBy season:")
    print(espoirs.groupby("season").size())

    print("\nDate ranges per season:")
    for season in sorted(espoirs["season"].unique()):
        games = espoirs[espoirs["season"] == season]
        print(f"\n  {season}:")
        print(f"    Games: {len(games)}")
        print(f'    Date range: {games["game_date"].min()} -> {games["game_date"].max()}')

        # Check if dates make sense for the season label
        # 2023-2024 season should have games from ~Sep 2023 to May 2024
        # 2024-2025 season should have games from ~Sep 2024 to May 2025
        sample_dates = games["game_date"].head(3).tolist()
        print(f'    Sample dates: {", ".join(sample_dates)}')

        # Count past vs future
        past = games[pd.to_datetime(games["game_date"]).dt.date <= date.today()]
        future = games[pd.to_datetime(games["game_date"]).dt.date > date.today()]
        print(f"    Past: {len(past)} | Future: {len(future)}")

print(f'\n{"="*70}')
print("Current date:", date.today())
